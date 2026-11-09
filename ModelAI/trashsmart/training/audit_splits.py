"""Find cross-split duplicate RGB images and candidate Roboflow source-name overlap."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def audit(source, layout="yolo"):
    from PIL import Image
    source = Path(source).resolve()
    hashes, names, counts = defaultdict(list), defaultdict(list), {}
    for split in ("train", "valid", "test"):
        root = source / split / "images" if layout == "yolo" else source / split
        if not root.is_dir():
            raise FileNotFoundError(root)
        files = sorted(p for p in root.rglob("*") if p.suffix.lower() in
                       {".jpg", ".jpeg", ".png", ".bmp", ".webp"})
        if not files:
            raise ValueError(f"Empty split: {root}")
        counts[split] = len(files)
        for path in files:
            with Image.open(path) as image:
                rgb = image.convert("RGB")
                digest = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
            record = dict(split=split, path=str(path.relative_to(source)))
            hashes[digest].append(record)
            names[path.stem.split(".rf.")[0]].append(record)
    cross = lambda groups: [records for records in groups.values()
                             if len({r["split"] for r in records}) > 1]
    return dict(source=str(source), layout=layout, counts=counts,
                exact_pixel_overlap=cross(hashes), source_name_candidates=cross(names),
                limitation="Name overlap requires review; no resized/near-duplicate detection or session identity audit")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--layout", choices=("yolo", "imagefolder"), default="yolo")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    report = audit(args.source, args.layout)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in
                      ("exact_pixel_overlap", "source_name_candidates")}, indent=2))
    print(f"Exact overlap groups: {len(report['exact_pixel_overlap'])}; "
          f"name candidates: {len(report['source_name_candidates'])}")


if __name__ == "__main__":
    main()
