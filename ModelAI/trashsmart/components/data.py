"""Validated, portable annotations and leakage-aware exports for bottle parts."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps
from . import PARTS, MATERIALS

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def contained(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Path escapes dataset directory")
    return path


def read_records(root):
    file = Path(root) / "02_annotations" / "annotations.jsonl"
    return [json.loads(line) for line in file.read_text(encoding="utf-8-sig").splitlines() if line.strip()] if file.exists() else []


def write_records(root, records):
    file = Path(root) / "02_annotations" / "annotations.jsonl"
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    temporary.replace(file)


def box(value, width, height):
    if not isinstance(value, list) or len(value) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value):
        raise ValueError("bbox must contain four finite pixel coordinates")
    x1, y1, x2, y2 = value
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError("bbox is empty or outside image")
    return value


def validate(record, root):
    if record.get("exampleOnly"):
        raise ValueError("Illustrations cannot be used for training")
    if not record.get("groupId") or not isinstance(record["groupId"], str):
        raise ValueError("groupId must identify the physical bottle/product group")
    if record.get("split") not in (None, "train", "val", "test"):
        raise ValueError("Invalid split")
    image_path = contained(root, record["image"])
    if image_path.suffix.lower() not in EXTENSIONS:
        raise ValueError("Only JPEG, PNG, WebP images are accepted")
    with Image.open(image_path) as raw:
        image = ImageOps.exif_transpose(raw).convert("RGB")
        width, height = image.size
    ids = set()
    for bottle in record["bottles"]:
        if not bottle.get("id") or bottle["id"] in ids:
            raise ValueError("Each bottle needs a unique id")
        ids.add(bottle["id"])
        bx1, by1, bx2, by2 = box(bottle["bbox"], width, height)
        component_ids = set()
        for c in bottle["components"]:
            if not c.get("id") or c["id"] in component_ids or c.get("partType") not in PARTS:
                raise ValueError("Invalid component id/type")
            component_ids.add(c["id"])
            cx1, cy1, cx2, cy2 = box(c["bbox"], width, height)
            if not (bx1 <= cx1 < cx2 <= bx2 and by1 <= cy1 < cy2 <= by2):
                raise ValueError("Component must be inside its parent bottle bbox")
            if c.get("material") not in (*MATERIALS, "unknown"):
                raise ValueError("Invalid material")
            if c.get("materialVerified") is True and (c["material"] == "unknown" or not c.get("verificationBasis", "").strip()):
                raise ValueError("Verified material requires a known class and evidence")
    return image


def split_for(group, seed="trashsmart-components-v1"):
    n = int(hashlib.sha256((seed + ":" + group).encode()).hexdigest()[:8], 16) % 100
    return "train" if n < 70 else "val" if n < 85 else "test"


def inventory(root):
    root = Path(root)
    records = read_records(root)
    reviewed = Counter()
    pending = Counter()
    verified = Counter()
    errors, hashes = [], {}
    for i, r in enumerate(records):
        try:
            validate(r, root)
            digest = hashlib.sha256(contained(root, r["image"]).read_bytes()).hexdigest()
            if digest in hashes and hashes[digest] != r["groupId"]:
                raise ValueError("Duplicate image assigned to different groups")
            hashes[digest] = r["groupId"]
            if r.get("annotationReviewed") is True:
                for b in r["bottles"]:
                    for c in b["components"]:
                        reviewed[c["partType"]] += 1
                        if c.get("materialVerified") is True:
                            verified[c["partType"] + "/" + c["material"]] += 1
            else:
                for b in r["bottles"]:
                    pending.update(c["partType"] for c in b["components"])
        except (ValueError, KeyError, OSError, TypeError) as e:
            errors.append({"record": i, "image": r.get("image"), "error": str(e)})
    from .intake import load_intake
    intake = load_intake(root)
    public_photos = [p for p in (root / "03_public/images").rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS]
    return {"userPhotos": len(intake["files"]), "userIntake": intake["audit"], "publicPhotos": len(public_photos), "annotationRecords": len(records), "reviewedParts": dict(reviewed), "pendingReviewParts": dict(pending),
            "verifiedMaterials": dict(verified), "errors": errors,
            "missingPartTypes": [p for p in PARTS if not reviewed[p]],
            "missingMaterialClasses": [m for m in MATERIALS if not sum(v for k, v in verified.items() if k.endswith("/" + m))]}


def export(root, output, include_partial_materials=False):
    """Never overwrite an existing export; abort on leakage or unreviewed-only data."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Export output exists; choose a new directory")
    records = read_records(root)
    from .intake import load_intake, check_record_intake
    intake = load_intake(root)
    eligible, groups, hashes, names = [], {}, {}, set()
    for r in records:
        image = validate(r, root)
        if r.get("annotationReviewed") is not True:
            continue
        check_record_intake(r, root, intake)
        if r["image"] in names:
            raise ValueError("Duplicate annotation record for image")
        names.add(r["image"])
        split = r.get("split") or split_for(r["groupId"])
        if r["groupId"] in groups and groups[r["groupId"]] != split:
            raise ValueError("Same group occurs in multiple splits")
        groups[r["groupId"]] = split
        digest = hashlib.sha256(contained(root, r["image"]).read_bytes()).hexdigest()
        if digest in hashes:
            raise ValueError("Duplicate image: remove duplicate records before export")
        hashes[digest] = split
        eligible.append((r, image, split, digest))
    if not eligible:
        raise ValueError("No reviewed annotations. Add images and review boxes first")
    summary = Counter()
    manifest = []
    material_manifest = []
    for r, image, split, digest in eligible:
        for bi, bottle in enumerate(r["bottles"]):
            detector_eligible = bottle.get("partsExhaustive") is True
            if not detector_eligible and not include_partial_materials:
                continue
            bx1, by1, bx2, by2 = map(int, bottle["bbox"])
            bw, bh = bx2 - bx1, by2 - by1
            if bw < 2 or bh < 2:
                raise ValueError("Bottle crop too small")
            stem = f"{digest[:20]}_{bi}"
            img_file = output / "detector" / "images" / split / (stem + ".jpg")
            label_file = output / "detector" / "labels" / split / (stem + ".txt")
            if detector_eligible:
                img_file.parent.mkdir(parents=True, exist_ok=True)
                label_file.parent.mkdir(parents=True, exist_ok=True)
                image.crop((bx1, by1, bx2, by2)).save(img_file, quality=95)
            labels = []
            for ci, c in enumerate(bottle["components"]):
                x1, y1, x2, y2 = c["bbox"]
                if detector_eligible:
                    labels.append(f"{PARTS.index(c['partType'])} {((x1+x2)/2-bx1)/bw:.8f} {((y1+y2)/2-by1)/bh:.8f} {(x2-x1)/bw:.8f} {(y2-y1)/bh:.8f}")
                    summary[f"detector/{split}/{c['partType']}"] += 1
                if c.get("materialVerified") is True:
                    crop_file = output / "material" / split / c["material"] / (stem + f"_{ci}.jpg")
                    crop_file.parent.mkdir(parents=True, exist_ok=True)
                    image.crop(tuple(map(int, c["bbox"]))).save(crop_file, quality=95)
                    summary[f"material/{split}/{c['material']}"] += 1
                    material_manifest.append({"crop":crop_file.relative_to(output).as_posix(),"source":r['image'],
                        "sourceSha256":digest,"groupId":r['groupId'],"split":split,"bottleId":bottle['id'],
                        "componentId":c['id'],"partType":c['partType'],"bbox":c['bbox'],"material":c['material'],
                        "verificationBasis":c['verificationBasis'],
                        "verificationSource":c.get('materialVerificationSource','annotation-record'),
                        "materialConfirmationSha256":c.get('materialConfirmationSha256'),
                        "detectorAnnotationExhaustive":detector_eligible})
            if detector_eligible:
                label_file.write_text("\n".join(labels) + ("\n" if labels else ""), encoding="utf-8")
                manifest.append({"crop": stem, "source": r["image"], "sourceSha256": digest, "groupId": r["groupId"], "split": split})
    if not manifest and not material_manifest:
        raise ValueError("No bottles marked partsExhaustive=true")
    for split in ("train", "val", "test"):
        for kind in ("images", "labels"):
            (output / "detector" / kind / split).mkdir(parents=True, exist_ok=True)
        for material in MATERIALS:
            (output / "material" / split / material).mkdir(parents=True, exist_ok=True)
    detector = output / "detector"
    # JSON is valid YAML and preserves Windows paths without escaping errors.
    (detector / "data.yaml").write_text(json.dumps({"path": str(detector), "train": "images/train", "val": "images/val", "test": "images/test", "names": dict(enumerate(PARTS))}, indent=2), encoding="utf-8")
    report = {"schemaVersion": 1, "trainingScope": "bottle-components", "counts": dict(summary), "groups": groups,
              "manifest": manifest, "materialManifest":material_manifest,
              "includePartialMaterials":bool(include_partial_materials),
              "sourceAnnotationsSha256": hashlib.sha256((root / '02_annotations/annotations.jsonl').read_bytes()).hexdigest()}
    (output / "dataset-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def material_notes(root):
    file = Path(root) / "01_user_photos" / "materials.csv"
    if not file.exists():
        return {}
    with file.open(encoding="utf-8-sig", newline="") as stream:
        return {r["group_id"].strip(): r for r in csv.DictReader(stream) if r.get("group_id", "").strip()}
