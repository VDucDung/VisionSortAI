"""Offline bottle-box proposals for manual review; never component/material truth."""
import hashlib
import json
import time
from pathlib import Path

from .data import contained, validate
from .intake import load_intake


def propose_bottles(root, weights, output, batch=4, image_size=512, threads=4, limit=0):
    import numpy as np
    import torch
    from PIL import Image, ImageOps
    from ultralytics import YOLO
    root, output = Path(root).resolve(), Path(output).resolve()
    weights = Path(weights).resolve()
    if not weights.is_file():
        raise ValueError("Use a local official COCO detector checkpoint; no automatic download")
    if output.exists() or output.with_suffix(".report.json").exists():
        raise ValueError("Proposal output exists; choose a new version")
    if batch < 1 or threads < 1:
        raise ValueError("batch and threads must be positive")
    intake = load_intake(root)
    if intake["audit"]["errors"] or intake["audit"]["missingFiles"] or intake["audit"]["groupSplitConflicts"]:
        raise ValueError("Resolve intake audit errors before proposing boxes")
    torch.set_num_threads(threads)
    model = YOLO(str(weights))
    bottle_ids = [i for i, name in model.names.items() if name == "bottle"]
    if len(bottle_ids) != 1:
        raise ValueError("Expected one COCO bottle class; do not use the old four-material detector")
    paths = [p for p in intake["files"] if not intake["imageIndex"].get(p, {}).get("excludeFromBottleTraining")]
    aliases, duplicate_keys = {}, {}
    audit_file = root / "intake-audit.json"
    if audit_file.exists():
        audit = json.loads(audit_file.read_text(encoding="utf-8"))
        priority = {"test": 0, "val": 1, "train": 2, None: 3}
        for group in audit.get("exactDuplicateGroups", []):
            eligible = [i for i in group["images"] if i["image"] in intake["imageIndex"] and not intake["imageIndex"][i["image"]]["excludeFromBottleTraining"]]
            if not eligible:
                continue
            selected = min(eligible, key=lambda i: (priority.get(i["split"], 3), i["image"]))["image"]
            for image in eligible:
                duplicate_keys[image["image"]] = group["sha256"]
                if image["image"] != selected:
                    aliases[image["image"]] = selected
    paths = [p for p in paths if p not in aliases]
    if limit:
        paths = paths[:limit]
    started = time.monotonic()
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".partial.jsonl")
    if partial.exists():
        raise ValueError("Partial output exists; inspect it before starting a new job")
    records, errors, no_detections = 0, [], []
    with partial.open("x", encoding="utf-8") as stream:
        for start in range(0, len(paths), batch):
            names, images = [], []
            for name in paths[start:start+batch]:
                try:
                    with Image.open(contained(root, name)) as image:
                        images.append(np.asarray(ImageOps.exif_transpose(image).convert("RGB"))[:, :, ::-1].copy())
                    names.append(name)
                except (OSError, ValueError) as error:
                    errors.append({"image": name, "error": str(error)})
            if not images:
                continue
            results = model.predict(images, classes=bottle_ids, device="cpu", conf=.25, imgsz=image_size,
                                    max_det=10, agnostic_nms=False, verbose=False)
            for name, result, image in zip(names, results, images):
                h, w = image.shape[:2]
                bottles = []
                if result.boxes is not None:
                    for box in result.boxes:
                        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                        bbox = [max(0,x1), max(0,y1), min(w,x2), min(h,y2)]
                        if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
                            continue
                        bottles.append({"id": f"bottle-{len(bottles)+1}", "bbox": bbox,
                                        "proposalConfidence": round(float(box.conf.item()), 5),
                                        "partsExhaustive": False, "components": []})
                if not bottles:
                    no_detections.append(name)
                    continue  # Absence of a COCO prediction is not proof of absence.
                meta = intake["imageIndex"].get(name, {})
                record = {"schemaVersion":1,"source":"user-model-proposal","image":name,
                          "groupId":meta.get("groupId") or Path(name).stem,"split":meta.get("split"),
                          "annotationReviewed":False,"proposalOnly":True,"bottles":bottles,
                          "reviewNote":"COCO bottle box proposal only. Confirm bottle scope/boxes, add visible components and verify materials. Do not infer material from folder."}
                validate(record, root)
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                records += 1
            stream.flush()
            if start % (batch * 25) == 0:
                print(json.dumps({"processed": min(start+batch,len(paths)),"total":len(paths),"candidateImages":records,"seconds":round(time.monotonic()-started,1)}),flush=True)
    partial.replace(output)
    report = {"proposalFile":str(output),"modelSha256":hashlib.sha256(weights.read_bytes()).hexdigest(),
              "modelClasses": {str(i):model.names[i] for i in bottle_ids}, "photosProcessed":len(paths),
              "candidateImages":records,"notDetectedNeedsReview":no_detections,"readErrors":errors,
              "exactDuplicateAliases":aliases,"deduplicationPolicy":"one exact copy; test then val then train priority; original CSV/splits preserved",
              "seconds":round(time.monotonic()-started,2),"annotationReviewed":False,"componentMaterialLabelsCreated":0,
              "masterAnnotationsModified":False,"note":"Screening proposals only. Unmatched photos still need review; no candidate becomes training truth automatically."}
    output.with_suffix(".report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    annotation_root = root / "02_annotations"
    if output.is_relative_to(annotation_root):
        pointer = annotation_root / "proposals.active.json"
        temporary = pointer.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"file": output.relative_to(annotation_root).as_posix(), "reviewed": False}), encoding="utf-8")
        temporary.replace(pointer)
    return report


def find_proposal(root, image):
    annotation_root = Path(root) / "02_annotations"
    pointer = annotation_root / "proposals.active.json"
    file = annotation_root / "user-bottle-proposals-v1.jsonl"
    if pointer.exists():
        name = json.loads(pointer.read_text(encoding="utf-8"))["file"]
        file = contained(annotation_root, name)
        if file.suffix != ".jsonl":
            raise ValueError("Proposal pointer must reference a JSONL annotation file")
    if file.exists():
        with file.open(encoding="utf-8") as stream:
            for line in stream:
                record = json.loads(line)
                if record["image"] == image:
                    from .scope_review import apply_review
                    return apply_review(root,record)
    fallback=annotation_root/'user-bottle-proposals-v1.jsonl'
    if file!=fallback and fallback.exists():
        with fallback.open(encoding='utf8') as stream:
            for line in stream:
                record=json.loads(line)
                if record['image']==image:
                    from .scope_review import apply_review
                    return apply_review(root,record)
    return None
