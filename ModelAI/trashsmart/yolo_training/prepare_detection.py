"""Create a clean single-class detection snapshot without modifying source data."""
import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from trashsmart.training.detection_metrics import read_annotations


def normalize_annotations(text):
    # Validate IDs 0..3 and geometry before conversion. Existing boxes retain
    # their coordinates; polygons use their enclosing rectangle, as YOLO detect does.
    read_annotations(text, 1, 1, 4)
    rows, classes, polygons = [], Counter(), 0
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split()
        classes[int(parts[0])] += 1
        values = list(map(float, parts[1:]))
        if len(parts) != 5:
            xs, ys = values[::2], values[1::2]
            left, right, top, bottom = min(xs), max(xs), min(ys), max(ys)
            values = [(left+right)/2, (top+bottom)/2, right-left, bottom-top]
            polygons += 1
        rows.append("0 " + " ".join(f"{value:.10g}" for value in values))
    return "\n".join(rows) + ("\n" if rows else ""), classes, polygons


def prepare(source, output):
    from PIL import Image
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Source and snapshot must be separate directories")
    if output.exists():
        raise FileExistsError(output)
    plan, counts, converted_mixed = [], {}, []
    for split in ("train", "valid", "test"):
        folder = source / split / "images"
        files = sorted(p for p in folder.iterdir() if p.suffix.lower() in
                       {".jpg", ".jpeg", ".png", ".webp", ".bmp"})
        if not files or len({p.stem for p in files}) != len(files):
            raise ValueError(f"Empty split or duplicate image stems: {split}")
        summary = dict(images=len(files), objects=0, polygon_rows_converted=0, material_ids=Counter())
        for image in files:
            with Image.open(image) as header:
                header.verify()
            label = source / split / "labels" / (image.stem + ".txt")
            text = label.read_text(encoding="utf-8-sig")
            normalized, classes, polygons = normalize_annotations(text)
            summary["objects"] += sum(classes.values())
            summary["material_ids"].update(classes)
            summary["polygon_rows_converted"] += polygons
            if polygons and any(len(line.split()) == 5 for line in text.splitlines() if line.strip()):
                converted_mixed.append(str(image.relative_to(source)))
            plan.append((image, Path(split) / "images" / image.name,
                         Path(split) / "labels" / label.name, normalized))
        counts[split] = summary
    for split in counts:
        (output / split / "images").mkdir(parents=True)
        (output / split / "labels").mkdir()
    for source_image, image, label, text in plan:
        shutil.copy2(source_image, output / image)
        (output / label).write_text(text, encoding="utf-8")
    config = dict(path=output.as_posix(), train="train/images", val="valid/images",
                  test="test/images", nc=1, names=["item"])
    # JSON is a YAML subset and avoids platform-specific escaping of Windows paths.
    (output / "data.yaml").write_text(json.dumps(config, indent=2), encoding="utf-8")
    manifest = dict(source=str(source), counts=counts, converted_mixed_images=converted_mixed,
                    scope="Single-class object detection; all material IDs become 0",
                    geometry="Existing boxes preserved; polygons converted to enclosing boxes",
                    split_policy="Original train/valid/test preserved; no additional samples",
                    source_policy="Source images, labels and YAML unchanged")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
