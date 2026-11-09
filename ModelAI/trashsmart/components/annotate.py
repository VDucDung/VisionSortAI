"""Loopback-only annotation tool. All photos and writes stay on this machine."""
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .data import EXTENSIONS, contained, read_records, write_records, validate, material_notes
from .intake import load_intake, photo_allowed, check_record_intake


def review_queues(root, allowed_files):
    """Queues only select existing photos; never supply labels, groups or splits."""
    root=Path(root).resolve()
    allowed=set(allowed_files)
    queues=[];errors=[]
    for file in sorted((root/'02_annotations/review-queues').glob('*.json')):
        try:
            if file.stat().st_size>2*1024*1024:
                raise ValueError('Review queue too large')
            value=json.loads(file.read_text(encoding='utf8'))
            if not isinstance(value,dict) or not isinstance(value.get('files'),list) or not isinstance(value.get('title'),str):
                raise ValueError('Invalid review queue')
            if len(value['files'])>10000 or len(value['title'])>100:
                raise ValueError('Review queue limit exceeded')
            names=[]
            for image in value['files']:
                if not isinstance(image,str) or image not in allowed:
                    raise ValueError('Queue references a missing or disallowed photo')
                path=contained(root,image)
                if not photo_allowed(root,path) or not path.is_file():
                    raise ValueError('Queue references a non-photo path')
                if image not in names:names.append(image)
            queues.append({'id':file.stem,'title':value['title'],'files':names})
        except (ValueError,TypeError,OSError,KeyError) as error:
            errors.append({'queue':file.name,'error':str(error)})
    return queues,errors


def make_server(root, port):
    root = Path(root).resolve()
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def send_data(self, status, body, kind="application/json"):
            if kind == "application/json":
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", kind + ("; charset=utf-8" if kind.startswith("text/") else ""))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def allowed(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.allowed():
                return self.send_data(403, {"error": "Loopback host required"})
            url = urlparse(self.path)
            try:
                if url.path == "/":
                    page = Path(__file__).with_name("annotator.html").read_text(encoding="utf-8").replace("__TOKEN__", token)
                    return self.send_data(200, page.encode("utf-8"), "text/html")
                if url.path == "/api/files":
                    intake = load_intake(root)
                    public = [p.relative_to(root).as_posix() for p in (root / "03_public/images").rglob("*") if p.is_file() and photo_allowed(root,p)]
                    files=sorted(intake['files']+public)
                    queues,queue_errors=review_queues(root,files)
                    return self.send_data(200, {"files": files, "notes": intake["notes"],
                                                "reviewQueues":queues,"reviewQueueErrors":queue_errors,
                                                "imageIndex": intake["imageIndex"], "intakeAudit": intake["audit"]})
                name = parse_qs(url.query).get("image", [""])[0]
                path = contained(root, name)
                if not photo_allowed(root, path):
                    raise ValueError("Only dataset photos are accessible")
                if url.path == "/api/record":
                    record = next((r for r in read_records(root) if r["image"] == name), None)
                    if record is None:
                        from .proposals import find_proposal
                        record = find_proposal(root, name)
                    return self.send_data(200, record)
                if url.path == "/image":
                    from PIL import Image, ImageOps
                    import io
                    with Image.open(path) as image:
                        out = io.BytesIO()
                        ImageOps.exif_transpose(image).convert("RGB").save(out, "JPEG", quality=95)
                    return self.send_data(200, out.getvalue(), "image/jpeg")
                return self.send_data(404, {"error": "Not found"})
            except (ValueError, KeyError, OSError) as e:
                return self.send_data(400, {"error": str(e)})

        def do_POST(self):
            if not self.allowed() or self.headers.get("X-Annotation-Token") != token or self.path != "/api/record":
                return self.send_data(403, {"error": "Invalid local session"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 262144:
                    raise ValueError("Invalid annotation size")
                record = json.loads(self.rfile.read(size))
                photo = contained(root, record["image"])
                if not photo_allowed(root, photo):
                    raise ValueError("Only dataset photos can be annotated")
                validate(record, root)
                check_record_intake(record, root, load_intake(root))
                if record.get("proposalOnly") and record.get("annotationReviewed") is True:
                    record["proposalOnly"] = False
                    record["reviewedFromProposal"] = True
                records = read_records(root)
                records = [r for r in records if r["image"] != record["image"]] + [record]
                write_records(root, records)
                return self.send_data(200, {"saved": True})
            except (ValueError, KeyError, TypeError, OSError) as e:
                return self.send_data(400, {"error": str(e)})

    return HTTPServer(("127.0.0.1", port), Handler)


def serve(root, port):
    server = make_server(root, port)
    print(f"Annotation tool: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
