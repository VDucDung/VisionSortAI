"""Convert YOLO detection boxes into ImageFolder crops, preserving splits."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

from PIL import Image


def prepare_dataset(source, destination, classes):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination == source or source in destination.parents or destination in source.parents:
        raise ValueError("Source and output datasets must be separate directories.")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Output must be empty: {destination}")
    if len(classes) != len(set(classes)) or not classes:
        raise ValueError("Classes must be unique, in YOLO ID order.")
    if any(Path(name).name != name or name in (".", "..") for name in classes):
        raise ValueError("Class names must be simple directory names.")
    plan, records, counts = [], [], {}
    for split in ("train", "valid", "test"):
        image_dir, label_dir = source / split / "images", source / split / "labels"
        if not image_dir.is_dir() or not label_dir.is_dir():
            raise FileNotFoundError(f"Missing images or labels in {source / split}")
        images = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in
                        (".jpg", ".jpeg", ".png", ".bmp", ".webp"))
        if not images or len({p.stem for p in images}) != len(images):
            raise ValueError(f"Empty split or duplicate image stems: {split}")
        counts[split] = Counter()
        for path in images:
            label = label_dir / (path.stem + ".txt")
            if not label.is_file():
                raise FileNotFoundError(f"Missing annotation: {label}")
            boxes = []
            with Image.open(path) as image:
                width, height = image.size
                image.verify()
            for index, line in enumerate(label.read_text(encoding="utf-8-sig").splitlines()):
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) != 5 and (len(parts) < 7 or len(parts) % 2 != 1):
                    raise ValueError(f"Expected YOLO box or polygon: {label}:{index + 1}")
                class_id = int(parts[0])
                coordinates = list(map(float, parts[1:]))
                if not 0 <= class_id < len(classes) or not all(
                    math.isfinite(v) and 0 <= v <= 1 for v in coordinates
                ):
                    raise ValueError(f"Invalid class or coordinates: {label}:{index + 1}")
                if len(parts) == 5:
                    x, y, w, h = coordinates
                    left, top, right, bottom = x - w / 2, y - h / 2, x + w / 2, y + h / 2
                else:
                    xs, ys = coordinates[::2], coordinates[1::2]
                    left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
                if right <= left or bottom <= top:
                    raise ValueError(f"Zero-size annotation: {label}:{index + 1}")
                box = (max(0, math.floor(left * width)),
                       max(0, math.floor(top * height)),
                       min(width, math.ceil(right * width)),
                       min(height, math.ceil(bottom * height)))
                if box[2] <= box[0] or box[3] <= box[1]:
                    raise ValueError(f"Empty crop: {label}:{index + 1}")
                relative = Path(split) / classes[class_id] / f"{path.stem}__box{index:03d}.jpg"
                boxes.append((box, relative))
                counts[split][classes[class_id]] += 1
                records.append({"image": str(path.relative_to(source)),
                                "label_line": index + 1, "class_id": class_id,
                                "box_xyxy": box, "crop": relative.as_posix()})
            plan.append((path, boxes))
        if set(counts[split]) != set(classes):
            raise ValueError(f"Split {split} does not contain every class: {counts[split]}")
    for split in counts:
        for name in classes:
            (destination / split / name).mkdir(parents=True, exist_ok=True)
    for path, boxes in plan:
        with Image.open(path) as image:
            image = image.convert("RGB")
            for box, relative in boxes:
                image.crop(box).save(destination / relative, quality=95)
    manifest = {"source": str(source), "classes": list(classes), "counts": counts,
                "source_images": len(plan), "crop_count": len(records), "records": records}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"images": len(plan), "crops": len(records), "counts": counts}, indent=2))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--classes", nargs="+", required=True, help="Names in YOLO class ID order")
    args = parser.parse_args()
    prepare_dataset(args.source, args.output, args.classes)


if __name__ == "__main__":
    main()
