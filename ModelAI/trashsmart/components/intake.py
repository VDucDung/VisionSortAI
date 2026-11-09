"""Read grouped user photos and CSV references without guessing component materials."""
import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path

from .data import EXTENSIONS, contained

USER_FOLDERS = ("images", "glass", "metal", "paper", "plastic", "needs_review")
FIELDS = ("group_id", "product_name", "body_material", "body_verified", "cap_material", "cap_verified",
          "label_material", "label_verified", "verification_basis", "notes")
MATERIAL_CODES = {"glass", "metal", "paper", "plastic", "unknown"}


def note_fields(text):
    result = {}
    for entry in (text or "").split(";"):
        if "=" in entry:
            key, value = entry.split("=", 1)
            if re.fullmatch(r"[a-zA-Z_]+", key.strip()):
                result[key.strip().lower()] = value.strip()
    return result


def photo_allowed(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    folders = [root / "01_user_photos" / name for name in USER_FOLDERS] + [root / "03_public/images"]
    return path.suffix.lower() in EXTENSIONS and any(path.is_relative_to(p) for p in folders)


def user_photos(root):
    root = Path(root).resolve()
    result = []
    for name in USER_FOLDERS:
        base = root / "01_user_photos" / name
        for file in base.rglob("*"):
            if file.is_file() and photo_allowed(root, file):
                result.append(file)
    return sorted(set(result))


def source_split(fields, file):
    raw = fields.get("source_split", "").lower()
    raw = "val" if raw == "valid" else raw
    prefix = re.match(r"^(train|valid|val|test)__", file.name, re.I)
    inferred = prefix.group(1).lower() if prefix else None
    inferred = "val" if inferred == "valid" else inferred
    if raw and raw not in {"train", "val", "test"}:
        raise ValueError("Invalid source_split in CSV")
    if raw and inferred and raw != inferred:
        raise ValueError("CSV source_split conflicts with filename prefix")
    return raw or inferred


def load_intake(root):
    root = Path(root).resolve()
    base = root / "01_user_photos"
    photos = user_photos(root)
    by_name, by_group = defaultdict(list), defaultdict(list)
    for photo in photos:
        by_name[photo.name].append(photo)
        group = re.sub(r"_(front|back|side|top|cap|label|body|view)\d*$", "", photo.stem)
        by_group[group].append(photo)
    index, notes, errors = {}, {}, []
    csv_file = base / "materials.csv"
    rows = []
    if csv_file.exists():
        try:
            with csv_file.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                if not reader.fieldnames or not set(FIELDS).issubset(reader.fieldnames):
                    raise ValueError("materials.csv is missing required columns")
                rows = list(reader)
        except (ValueError, OSError, UnicodeError, csv.Error) as error:
            errors.append({"row": 1, "error": str(error)})
    verified = Counter()
    missing_files, ambiguous, duplicate_refs, group_conflicts = [], [], [], []
    for line, row in enumerate(rows, start=2):
        try:
            if None in row or any(row.get(k) is None for k in FIELDS):
                raise ValueError("CSV row has missing or extra values")
            row = {k: (v or "").strip() for k, v in row.items()}
            group = row["group_id"]
            if not group:
                raise ValueError("group_id is required")
            for part in ("body", "cap", "label"):
                if row[part + "_material"] not in MATERIAL_CODES or row[part + "_verified"].lower() not in {"true", "false"}:
                    raise ValueError("Invalid material or verified flag")
                if row[part + "_verified"].lower() == "true":
                    if row[part + "_material"] == "unknown" or not row["verification_basis"]:
                        raise ValueError("Verified material requires a known class and evidence")
                    verified[part] += 1
            previous = notes.get(group)
            compare = [key for key in FIELDS if key not in {"notes", "product_name"}]
            if previous and any(previous[key] != row[key] for key in compare):
                group_conflicts.append({"row": line, "groupId": group})
                raise ValueError("Conflicting material information for one group_id")
            notes.setdefault(group, row)
            fields = note_fields(row["notes"])
            explicit = fields.get("image_path")
            selected = []
            if explicit:
                relative = explicit.replace("\\", "/")
                file = contained(root if relative.startswith("01_user_photos/") else base, relative)
                if not photo_allowed(root, file) or not file.is_relative_to(base):
                    raise ValueError("CSV image_path must stay inside an allowed user photo folder")
                if file.is_file():
                    selected = [file]
                else:
                    missing_files.append({"row": line, "groupId": group, "path": explicit})
            elif fields.get("image"):
                name = fields["image"]
                if Path(name).name != name or "\\" in name:
                    raise ValueError("Use image_path for a nested path; image must be a basename")
                if fields.get("folder"):
                    file = contained(base, fields["folder"] + "/" + name)
                    if not photo_allowed(root, file):
                        raise ValueError("CSV folder is not an allowed photo directory")
                    selected = [file] if file.is_file() else []
                else:
                    selected = by_name.get(name, [])
                if not selected:
                    missing_files.append({"row": line, "groupId": group, "path": name})
                elif len(selected) > 1:
                    ambiguous.append({"row": line, "groupId": group, "name": name})
                    raise ValueError("Ambiguous image basename; set image_path")
            else:
                # One CSV row can describe several angles of the same product.
                selected = by_group.get(group, [])
            for file in selected:
                key = file.relative_to(root).as_posix()
                if key in index:
                    duplicate_refs.append({"row": line, "image": key})
                    raise ValueError("Multiple CSV rows reference the same image")
                object_type = fields.get("object_type", "unknown").lower()
                excluded = fields.get("exclude_from_bottle_training", "").lower() == "true" or object_type not in {"unknown", "bottle"}
                index[key] = {"groupId": group, "split": source_split(fields, file), "csvRow": line,
                              "objectType": object_type, "excludeFromBottleTraining": excluded,
                              "needsReview": file.is_relative_to(base / "needs_review")}
        except (ValueError, OSError, KeyError, TypeError) as error:
            errors.append({"row": line, "groupId": row.get("group_id"), "error": str(error)})
    group_splits = defaultdict(set)
    from .scope_review import load_reviews
    scope_reviews,scope_errors=load_reviews(root)
    applied_scope=Counter()
    for key,item in index.items():
        review=scope_reviews.get(key)
        if review:
            item['scopeReview']=review['objectScope']
            item['rejectedBottleBoxes']=review.get('rejectedBottleBoxes',[])
            applied_scope[review['objectScope']]+=1
            if review['objectScope']=='not_bottle':item['excludeFromBottleTraining']=True
            if review['objectScope']=='uncertain':item['needsReview']=True
    from .dedup_policy import load_policy
    duplicate_aliases,duplicate_policy_errors=load_policy(root,index)
    for image,canonical in duplicate_aliases.items():
        index[image]['excludeFromBottleTraining']=True
        index[image]['duplicateOf']=canonical
    for item in index.values():
        if item["split"]:
            group_splits[item["groupId"]].add(item["split"])
    split_conflicts = [{"groupId": group, "splits": sorted(splits)} for group, splits in group_splits.items() if len(splits) > 1]
    folders = Counter(file.relative_to(base).parts[0] for file in photos)
    unreferenced = [file.relative_to(root).as_posix() for file in photos if file.relative_to(root).as_posix() not in index]
    audit = {"photoCount": len(photos), "photosByFolder": dict(folders), "csvRows": len(rows), "matchedPhotoCount": len(index),
             "verifiedRowsByPart": dict(verified), "sourceSplitCounts": dict(Counter(i["split"] or "unspecified" for i in index.values())),
             "excludedFromBottleTraining": sum(i["excludeFromBottleTraining"] for i in index.values()),
             "needsReviewPhotos": sum(i["needsReview"] for i in index.values()), "missingFiles": missing_files,
             "unreferencedImages": unreferenced, "ambiguousBasenames": ambiguous, "duplicateImageReferences": duplicate_refs,
             "groupSplitConflicts": split_conflicts, "errors": errors,
             "scopeReviewsApplied":dict(applied_scope),"scopeReviewErrors":scope_errors,
             "exactDuplicateAliasesExcluded":len(duplicate_aliases),"duplicatePolicyErrors":duplicate_policy_errors,
             "note": "Folders and dataset material labels do not verify component materials or supply component boxes."}
    return {"files": [file.relative_to(root).as_posix() for file in photos], "notes": notes, "imageIndex": index, "scopeReviews":scope_reviews, "audit": audit}


def check_record_intake(record, root, intake):
    root = Path(root).resolve()
    image = contained(root, record.get("image", "").replace("\\", "/")).relative_to(root).as_posix()
    if not image.startswith("01_user_photos/"):
        return
    if record.get("source") == "user-model-proposal" and record.get("annotationReviewed") is True:
        for bottle in record.get("bottles", []):
            if bottle.get("partsExhaustive") is True and not any(c.get("partType") == "body" for c in bottle.get("components", [])):
                raise ValueError("Add and review visible component boxes before accepting a bottle proposal as exhaustive")
    if intake["audit"]["errors"]:
        raise ValueError("Fix materials.csv errors reported by audit-intake before saving/exporting user annotations")
    item = intake["imageIndex"].get(image)
    if not item:
        split = source_split({}, Path(image))
        if split and record.get("split") != split:
            raise ValueError("Keep the source train/val/test split in the image filename")
        return
    if item["excludeFromBottleTraining"]:
        raise ValueError("Photo is outside bottle training scope according to CSV, visual review or duplicate policy")
    from .scope_review import rejected_box
    if any(rejected_box(b,item) for b in record.get('bottles',[])):
        raise ValueError("Remove the manually rejected non-bottle boxes before accepting this annotation")
    if item["split"] and record.get("split") != item["split"]:
        raise ValueError("Keep the source train/val/test split recorded in materials.csv")
    if any(c["groupId"] == item["groupId"] for c in intake["audit"]["groupSplitConflicts"]):
        raise ValueError("CSV group spans source splits; resolve it before annotation/export")


def audit_intake(root, hash_images=False):
    root = Path(root).resolve()
    intake = load_intake(root)
    audit = intake["audit"]
    if hash_images:
        hashes = defaultdict(list)
        for name in intake["files"]:
            try:
                with (root / name).open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                item = intake["imageIndex"].get(name, {})
                hashes[digest].append({"image": name, "groupId": item.get("groupId"), "split": item.get("split")})
            except OSError as error:
                audit["errors"].append({"image": name, "error": str(error)})
        duplicates = [{"sha256": digest, "images": images} for digest, images in hashes.items() if len(images) > 1]
        audit["exactDuplicateGroups"] = duplicates
        audit["crossSplitDuplicateGroups"] = [d for d in duplicates if len({i["split"] for i in d["images"] if i["split"]}) > 1]
        audit["hashCheck"] = "SHA256 exact bytes only; visually similar/re-encoded photos require separate review"
    return audit
