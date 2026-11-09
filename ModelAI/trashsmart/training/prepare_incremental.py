"""Mix additional material images into old training data; keep held-out splits intact."""
import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from PIL import Image

CLASSES = ("glass", "metal", "paper", "plastic")
FOLDER_MAP = {"giay": "paper", "kim loai": "metal", "nhua": "plastic", "thuy tinh": "glass"}
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def image_digest(path):
    with Image.open(path) as image:
        image = image.convert("RGB")
        return hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()


def prepare_incremental(old_dataset, additional, output):
    old_dataset, additional, output = (Path(p).resolve() for p in (old_dataset, additional, output))
    for source in (old_dataset, additional):
        if source == output or source in output.parents or output in source.parents:
            raise ValueError("Output and input datasets must be separate directories.")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite: {output}")
    known, existing, counts = {}, [], {}
    for split in ("train", "valid", "test"):
        counts[split] = Counter()
        for name in CLASSES:
            folder = old_dataset / split / name
            files = sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTENSIONS)
            if not files:
                raise ValueError(f"Missing class images: {folder}")
            for path in files:
                digest = image_digest(path)
                known.setdefault(digest, []).append((split, name))
                existing.append((path, path.relative_to(old_dataset)))
                counts[split][name] += 1
    # Also exclude new copies of the full source images behind held-out crops.
    original_manifest = old_dataset / "manifest.json"
    if original_manifest.is_file():
        manifest = json.loads(original_manifest.read_text(encoding="utf-8"))
        originals = {r["image"] for r in manifest.get("records", [])
                     if r["image"].replace("\\", "/").split("/")[0] in ("valid", "test")}
        for relative in sorted(originals):
            path = Path(manifest["source"]) / relative
            if not path.is_file():
                raise FileNotFoundError(f"Cannot audit held-out source image: {path}")
            known.setdefault(image_digest(path), []).append(("held-out original", None))
    if {p.name for p in additional.iterdir() if p.is_dir()} != set(FOLDER_MAP):
        raise ValueError(f"Expected additional class folders: {list(FOLDER_MAP)}")
    added, skipped = [], []
    for folder_name, name in FOLDER_MAP.items():
        for path in sorted((additional / folder_name).iterdir()):
            if path.suffix.lower() not in EXTENSIONS:
                continue
            digest = image_digest(path)
            if digest in known:
                labels = {label for _, label in known[digest] if label is not None}
                if labels and name not in labels:
                    raise ValueError(f"Duplicate image has conflicting material labels: {path}")
                skipped.append({"source": str(path), "reason": "duplicate decoded pixels",
                                "matches": known[digest]})
                continue
            known[digest] = [("new train", name)]
            relative = Path("train") / name / f"additional_{digest}.png"
            if (old_dataset / relative).exists():
                raise FileExistsError(relative)
            added.append({"source": str(path), "class": name, "sha256_pixels": digest,
                          "output": relative.as_posix()})
            counts["train"][name] += 1
    if not added:
        raise ValueError("No unique additional images remain after duplicate checks.")
    for path, relative in existing:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for record in added:
        with Image.open(record["source"]) as image:
            image.convert("RGB").save(output / record["output"])
    result = {"old_dataset": str(old_dataset), "additional_source": str(additional),
              "class_names": CLASSES, "folder_mapping": FOLDER_MAP, "counts": counts,
              "added": added, "skipped": skipped,
              "validation_and_test": "unchanged; no additional images added to held-out splits",
              "duplicate_check": "exact decoded RGB pixels, including held-out originals when available"}
    (output / "incremental_manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"counts": counts, "added": len(added), "skipped": len(skipped)}, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-dataset", required=True)
    parser.add_argument("--additional", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    prepare_incremental(args.old_dataset, args.additional, args.output)


if __name__ == "__main__":
    main()
