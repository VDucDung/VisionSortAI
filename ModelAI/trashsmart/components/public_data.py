"""Download official research annotations and only the requested bottle images."""
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from .data import read_records, write_records, validate

SPIN_URL = "https://joshmyersdean.github.io/spin/spin_coco.zip"
IMAGE_ZIP = "https://huggingface.co/datasets/turkeyju/PartImageNet/resolve/main/PartImageNet_Seg.zip"
DATASHEET = "https://raw.githubusercontent.com/joshmyersdean/spin-api/main/data_spec/datasheet.md"
HEADERS = {"User-Agent": "TrashSmart-Research/1.0"}


def download(url, file, max_bytes):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.exists():
        return
    temp = file.with_suffix(file.suffix + ".partial")
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=90) as response, temp.open("wb") as stream:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("Download exceeds expected size limit")
            stream.write(chunk)
    temp.replace(file)


class RemoteZipReader(io.RawIOBase):
    """HTTP byte ranges: do not download the multi-GB archive for 1 bottle."""
    def __init__(self, url):
        self.url, self.position = url, 0
        self.cache_start, self.cache = 0, b""
        request = urllib.request.Request(url, headers={**HEADERS, "Range": "bytes=0-0"})
        with urllib.request.urlopen(request, timeout=90) as response:
            value = response.headers.get("Content-Range", "")
            if response.status != 206 or not re.fullmatch(r"bytes 0-0/\d+", value):
                raise ValueError("Server does not support bounded range downloads; use manual image archive")
            self.size = int(value.split("/")[-1])

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if self.position < 0:
            raise ValueError("Negative archive offset")
        return self.position

    def tell(self):
        return self.position

    def read(self, size=-1):
        if size < 0:
            size = self.size - self.position
        size = min(size, self.size - self.position)
        if size <= 0:
            return b""
        if size > 32 * 1024 * 1024:
            raise ValueError("Unexpected large archive member")
        if self.cache_start <= self.position and self.position + size <= self.cache_start + len(self.cache):
            offset = self.position - self.cache_start
            self.position += size
            return self.cache[offset:offset+size]
        fetch_size = min(max(size, 128 * 1024), self.size - self.position)
        end = self.position + fetch_size - 1
        request = urllib.request.Request(self.url, headers={**HEADERS, "Range": f"bytes={self.position}-{end}"})
        with urllib.request.urlopen(request, timeout=90) as response:
            expected = f"bytes {self.position}-{end}/{self.size}"
            if response.status != 206 or response.headers.get("Content-Range") != expected:
                raise ValueError("Remote archive range mismatch")
            data = response.read(fetch_size + 1)
        if len(data) != fetch_size:
            raise ValueError("Incomplete remote archive range")
        self.cache_start, self.cache = self.position, data
        self.position += size
        return data[:size]


def fetch_public(root, limit=0):
    root = Path(root)
    public = root / "03_public"
    metadata = public / "spin_metadata"
    metadata.mkdir(parents=True, exist_ok=True)
    archive = public / "spin_coco.zip"
    download(SPIN_URL, archive, 40 * 1024 * 1024)
    download(DATASHEET, metadata / "datasheet.md", 100000)
    with zipfile.ZipFile(archive) as stream:
        for entry in stream.infolist():
            # Extract only the nine named JSONs; archive paths are never trusted.
            name = Path(entry.filename).name
            if re.fullmatch(r"spin_(train|val|test)_(wholes|parts|subparts)\.json", name):
                (metadata / name).write_bytes(stream.read(entry))
    candidates, counts = [], Counter()
    image_counts = {}
    for split in ("train", "val", "test"):
        data = json.loads((metadata / f"spin_{split}_subparts.json").read_text(encoding="utf-8"))
        categories = {c["id"]: c["name"] for c in data["categories"] if c["name"].startswith("Bottle-")}
        ids = {a["image_id"] for a in data["annotations"] if a["category_id"] in categories}
        image_counts[split] = len(ids)
        for annotation in data["annotations"]:
            if annotation["category_id"] in categories:
                counts[split + "/" + categories[annotation["category_id"]]] += 1
        candidates.extend({"split": split, **image} for image in data["images"] if image["id"] in ids)
    downloaded, error = [], None
    # Early pilot versions could select mask PNGs sharing the photo basename.
    # Quarantine only the exact files listed by that pilot's provenance report.
    previous_report = public / "source-report.json"
    if previous_report.exists():
        previous = json.loads(previous_report.read_text(encoding="utf-8"))
        for relative in previous.get("downloadedImages", []):
            old = (root / relative).resolve()
            if old.is_relative_to((public / "images").resolve()) and old.suffix.lower() == ".png" and old.is_file():
                target = public / "quarantine" / "masks" / old.parent.name / old.name
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    old.rename(target)
    if limit:
        try:
            # Interleave official splits, so a pilot can exercise all three.
            by_split = {s: [c for c in candidates if c["split"] == s] for s in ("train", "val", "test")}
            selected = []
            for i in range(max(map(len, by_split.values()))):
                for split in by_split:
                    if i < len(by_split[split]):
                        selected.append(by_split[split][i])
            with RemoteZipReader(IMAGE_ZIP) as remote, zipfile.ZipFile(remote) as image_archive:
                members = {(n.split('/')[2], Path(n).stem): n for n in image_archive.namelist()
                           if re.fullmatch(r"PartImageNet/images/(train|val|test)/[^/]+\.(JPEG|JPG|jpeg|jpg)", n)}
                for c in selected[:limit]:
                    stem = Path(c["file_name"]).stem
                    member = members.get((c["split"], stem))
                    if not member:
                        continue
                    destination = public / "images" / c["split"] / (stem + Path(member).suffix.lower())
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if not destination.exists():
                        if image_archive.getinfo(member).file_size > 20 * 1024 * 1024:
                            raise ValueError("Unexpected large source photo")
                        content = image_archive.read(member)
                        from PIL import Image
                        with Image.open(io.BytesIO(content)) as photo:
                            photo.verify()
                        destination.write_bytes(content)
                    downloaded.append(destination.relative_to(root).as_posix())
                    print(f"Downloaded bottle {len(downloaded)}/{min(limit,len(selected))}: {stem}", flush=True)
        except (ValueError, OSError, zipfile.BadZipFile) as exception:
            error = str(exception)
    report = {"source": "SPIN / PartImageNet Seg", "annotationsUrl": SPIN_URL, "imagesUrl": IMAGE_ZIP,
              "datasheetUrl": DATASHEET, "archiveSha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "bottleImagesBySplit": image_counts, "subpartCounts": dict(counts), "downloadedImages": downloaded,
              "imageDownloadError": error, "materialLabelsAvailable": False,
              "note": "SPIN supplies part geometry, not verified glass/metal/paper/plastic labels. ImageNet/PartImageNet image terms also apply."}
    (public / "source-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def xyxy(bbox, width, height):
    x, y, w, h = bbox
    return [max(0, int(x)), max(0, int(y)), min(width, int(x+w+.999)), min(height, int(y+h+.999))]


def import_spin(root):
    root = Path(root)
    public = root / "03_public"
    records = [r for r in read_records(root) if r.get("source") != "SPIN"]
    existing = {r["image"]: r for r in read_records(root) if r.get("source") == "SPIN"}
    imported, skipped = 0, []
    for split in ("train", "val", "test"):
        levels = {level: json.loads((public / "spin_metadata" / f"spin_{split}_{level}.json").read_text(encoding="utf-8")) for level in ("wholes", "parts", "subparts")}
        grouped = {}
        for level, data in levels.items():
            grouped[level] = defaultdict(list)
            for annotation in data["annotations"]:
                grouped[level][annotation["image_id"]].append(annotation)
        categories = {level: {c["id"]: c["name"] for c in data["categories"]} for level, data in levels.items()}
        for info in levels["subparts"]["images"]:
            files = list((public / "images" / split).glob(Path(info["file_name"]).stem + ".*"))
            if not files:
                continue
            name = files[0].relative_to(root).as_posix()
            if name in existing:
                records.append(existing[name])  # Keep manual reviews and verified materials.
                continue
            image_id, width, height = info["id"], info["width"], info["height"]
            wholes = grouped["wholes"][image_id]
            bodies = [a for a in grouped["parts"][image_id] if categories["parts"][a["category_id"]] == "Bottle Body"]
            if len(wholes) != 1 or len(bodies) != 1:
                skipped.append(name)
                continue
            parent = xyxy(wholes[0]["bbox"], width, height)
            components = [{"id": "body", "partType": "body", "bbox": xyxy(bodies[0]["bbox"], width, height),
                           "material": "unknown", "materialVerified": False, "verificationBasis": ""}]
            for annotation in grouped["subparts"][image_id]:
                label = categories["subparts"][annotation["category_id"]]
                kind = {"Bottle-Body-Label": "label", "Bottle-Mouth-Cap": "cap"}.get(label)
                if kind:
                    components.append({"id": str(annotation["id"]), "partType": kind,
                                       "bbox": xyxy(annotation["bbox"], width, height), "material": "unknown", "materialVerified": False, "verificationBasis": ""})
            # Clip minor source rounding to the annotated parent; review before export.
            for c in components:
                c["bbox"] = [max(parent[0], c["bbox"][0]), max(parent[1], c["bbox"][1]), min(parent[2], c["bbox"][2]), min(parent[3], c["bbox"][3])]
            candidate = {"schemaVersion": 1, "source": "SPIN", "image": name, "groupId": "spin:" + Path(info["file_name"]).stem,
                            "split": split, "annotationReviewed": False, "bottles": [{"id": "bottle-1", "bbox": parent, "partsExhaustive": False, "components": components}],
                            "reviewNote": "Review cap/body/label mapping, completeness, and product group. Source has no verified recycling material labels."}
            try:
                validate(candidate, root)
            except (ValueError, OSError, KeyError, TypeError):
                skipped.append(name)
                continue
            records.append(candidate)
            imported += 1
    write_records(root, records)
    return {"importedCandidates": imported, "keptExisting": len(existing), "skippedAmbiguous": skipped,
            "readyForTraining": False, "reason": "Review geometry and completeness before export; verify materials separately"}
