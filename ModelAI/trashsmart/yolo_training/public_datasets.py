"""Download official waste-detection archives and prepare grouped YOLO splits."""

import argparse
import hashlib
import io
import json
import math
import random
import re
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

from trashsmart.yolo_training.benchmark import audit_snapshot, sha256, write_json


SOURCES = {
    "taco": {
        "record": "3354286",
        "filename": "TACO.zip",
        "md5": "5c674548402b142d5a27a1f7b6a653f3",
        "bytes": 1110286487,
        "repository": "https://github.com/pedropro/TACO",
    },
    "uavvaste": {
        "record": "8214061",
        "filename": "UAVVasteDataset.zip",
        "md5": "1575c32c04bdf944047563e4a1786c2a",
        "bytes": 3010727259,
        "repository": "https://github.com/PUTvision/UAVVaste",
    },
}


def md5_file(path):
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_archive(dataset, folder):
    source = SOURCES[dataset]
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / source["filename"]
    if archive.is_file():
        if archive.stat().st_size != source["bytes"] or md5_file(archive) != source["md5"]:
            raise ValueError(f"Archive checksum mismatch: {archive}")
        return archive

    pending = archive.with_suffix(".zip.part")
    url = f"https://zenodo.org/api/records/{source['record']}/files/{source['filename']}/content"
    for attempt in range(5):
        offset = pending.stat().st_size if pending.exists() else 0
        if offset == source["bytes"]:
            break
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                if offset and response.status != 206:
                    raise ValueError("The server did not honor the download resume offset")
                if response.status == 206:
                    content_range = response.headers.get("Content-Range", "")
                    if not content_range.startswith(f"bytes {offset}-"):
                        raise ValueError(f"Unexpected download range: {content_range}")
                last_progress = time.monotonic()
                with pending.open("ab" if offset else "wb") as stream:
                    while block := response.read(4 * 1024 * 1024):
                        stream.write(block)
                        offset += len(block)
                        if time.monotonic() - last_progress >= 20:
                            print(f"{dataset}: downloaded {offset / source['bytes']:.1%}", flush=True)
                            last_progress = time.monotonic()
            if offset == source["bytes"]:
                break
        except (OSError, TimeoutError) as error:
            print(f"{dataset}: download attempt {attempt + 1} failed: {error}", flush=True)
            if attempt == 4:
                raise
            time.sleep(2)
    if pending.stat().st_size != source["bytes"] or md5_file(pending) != source["md5"]:
        raise ValueError(f"Archive checksum mismatch: {pending}")
    pending.replace(archive)
    print(f"{dataset}: official archive MD5 verified", flush=True)
    return archive


def capture_group(dataset, filename):
    path = Path(filename)
    if dataset == "taco":
        return path.parent.as_posix()
    name = path.name.lower()
    match = re.match(r"(batch_(?:[a-z]+)?\d+)_img_", name)
    if match:
        return match.group(1)
    if name.startswith("gopr"):
        return "gopro_photos"
    if name.startswith("dji"):
        return "dji_photos"
    return name.split("_")[0]


def split_groups(groups, seed):
    """Keep each acquisition group together with a deterministic 70/15/15 allocation."""
    names = sorted(groups)
    random.Random(seed).shuffle(names)
    names.sort(key=lambda name: len(groups[name]), reverse=True)
    total = sum(len(images) for images in groups.values())
    targets = {"train": .70 * total, "valid": .15 * total, "test": .15 * total}
    counts = dict.fromkeys(targets, 0)
    assignment = {}
    for name in names:
        split = max(targets, key=lambda key: targets[key] - counts[key])
        assignment[name] = split
        counts[split] += len(groups[name])
    if min(counts.values()) == 0:
        raise ValueError("Acquisition groups do not support three nonempty splits")
    return assignment


def annotation_box(annotation):
    """Use the enclosing rectangle of the source instance polygons in pixel coordinates."""
    polygons = annotation.get("segmentation")
    if not isinstance(polygons, list) or not polygons:
        raise ValueError(f"Polygon annotation required: {annotation['id']}")
    if any(len(ring) < 6 or len(ring) % 2 for ring in polygons):
        raise ValueError(f"Invalid polygon: {annotation['id']}")
    xs = [float(x) for ring in polygons for x in ring[::2]]
    ys = [float(y) for ring in polygons for y in ring[1::2]]
    if not all(math.isfinite(value) for value in xs + ys):
        raise ValueError(f"Non-finite polygon: {annotation['id']}")
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def prepare(dataset, archive, output, seed):
    from PIL import Image, ImageOps

    if (output / "data_audit.json").is_file():
        from trashsmart.yolo_training.benchmark import verify_snapshot
        audit = json.loads((output / "data_audit.json").read_text(encoding="utf-8"))
        verify_snapshot(output, audit["sha256"])
        if audit["exact_pixel_cross_split"]:
            raise ValueError("Exact duplicate leakage needs review before training")
        print(f"{dataset}: prepared snapshot verified", flush=True)
        return
    preparation = dict(dataset=dataset, archive_md5=SOURCES[dataset]["md5"], seed=seed,
                       max_long_side=1280, jpeg_quality=95,
                       box_policy="source_polygon_envelope")
    state_path = output / "preparation.json"
    if output.exists():
        if not state_path.is_file() or json.loads(state_path.read_text()) != preparation:
            raise FileExistsError(f"Existing preparation has different settings: {output}")
    else:
        output.mkdir(parents=True)
        write_json(state_path, preparation)

    with zipfile.ZipFile(archive) as source_zip:
        annotation_files = [name for name in source_zip.namelist()
                            if name.endswith("annotations.json") and "__MACOSX" not in name]
        if annotation_files:
            depth = min(name.count("/") for name in annotation_files)
            annotation_files = [name for name in annotation_files if name.count("/") == depth]
        if len(annotation_files) != 1:
            raise ValueError(f"Expected one annotation file: {annotation_files}")
        annotation_bytes = source_zip.read(annotation_files[0])
        annotations = json.loads(annotation_bytes)
        image_members = {name for name in source_zip.namelist()
                         if Path(name).suffix.lower() in {".jpg", ".jpeg", ".png"}}
        by_name = defaultdict(list)
        for member in image_members:
            by_name[Path(member).name].append(member)
        labels = defaultdict(list)
        category_ids = {category["id"] for category in annotations["categories"]}
        for annotation in annotations["annotations"]:
            if annotation.get("iscrowd", 0):
                raise ValueError("Crowd annotations require a separate evaluation policy")
            if annotation["category_id"] not in category_ids:
                raise ValueError("Unknown category ID")
            labels[annotation["image_id"]].append(annotation)

        groups = defaultdict(list)
        for image in annotations["images"]:
            groups[capture_group(dataset, image["file_name"])].append(image["id"])
        assignment = split_groups(groups, seed)
        records = []
        for image in annotations["images"]:
            filename = image["file_name"].replace("\\", "/")
            matches = [name for name in by_name[Path(filename).name]
                       if name.endswith(filename)]
            if len(matches) != 1:
                raise ValueError(f"Ambiguous or missing image: {filename}: {matches}")
            payload = source_zip.read(matches[0])
            with Image.open(io.BytesIO(payload)) as source_image:
                expected_size = (image["width"], image["height"])
                orientation = source_image.getexif().get(274, 1)
                oriented = ImageOps.exif_transpose(source_image)
                if oriented.size == expected_size:
                    rgb = oriented.convert("RGB")
                    applied_orientation = orientation
                elif source_image.size == expected_size:
                    rgb = source_image.convert("RGB")
                    applied_orientation = 1
                else:
                    raise ValueError(f"Annotation/image dimensions differ: {filename}")
                # Match the COCO annotation coordinate system before resizing.
                # Both architectures use the same 1280-pixel-long-side snapshot.
                rgb.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
                group = capture_group(dataset, filename)
                split = assignment[group]
                stem = f"{dataset}_{image['id']:06d}"
                image_path = output / split / "images" / (stem + ".jpg")
                label_path = output / split / "labels" / (stem + ".txt")
                image_path.parent.mkdir(parents=True, exist_ok=True)
                label_path.parent.mkdir(parents=True, exist_ok=True)
                rgb.save(image_path, quality=95, subsampling=0)
            rows = []
            for annotation in labels[image["id"]]:
                x, y, width, height = annotation_box(annotation)
                if width <= 0 or height <= 0 or x < 0 or y < 0:
                    raise ValueError(f"Invalid box in annotation {annotation['id']}")
                if x + width > image["width"] + 1 or y + height > image["height"] + 1:
                    raise ValueError(f"Box outside image in annotation {annotation['id']}")
                right = min(x + width, image["width"])
                bottom = min(y + height, image["height"])
                values = ((x + right) / (2 * image["width"]),
                          (y + bottom) / (2 * image["height"]),
                          (right - x) / image["width"], (bottom - y) / image["height"])
                rows.append("0 " + " ".join(f"{value:.10g}" for value in values))
            label_path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
            records.append(dict(source_id=image["id"], source_filename=filename,
                                source_sha256=hashlib.sha256(payload).hexdigest(),
                                applied_exif_orientation=applied_orientation,
                                split=split, capture_group=group,
                                image=image_path.relative_to(output).as_posix(),
                                annotation_ids=[a["id"] for a in labels[image["id"]]]))

    config = dict(path=output.resolve().as_posix(), train="train/images", val="valid/images",
                  test="test/images", nc=1, names=["item"])
    write_json(output / "data.yaml", config)
    audit = audit_snapshot(output)
    audit["test_history"] = "Grouped public-data split created for this study before model evaluation."
    write_json(output / "source.json", dict(
        source=SOURCES[dataset], archive_sha256=sha256(archive),
        annotations_sha256=hashlib.sha256(annotation_bytes).hexdigest(),
        categories=annotations["categories"], records=records,
        image_policy="EXIF orientation aligned with COCO dimensions, full image retained, at most 1280-pixel long side, JPEG quality 95",
        label_policy="All original waste categories merged to item; rectangles enclosing the original source segmentation polygons normalized",
        annotation_geometry=[dict(id=a["id"], source_bbox=a["bbox"],
                                  polygon_envelope=list(annotation_box(a)))
                             for a in annotations["annotations"]],
        split_policy="70/15/15 target by acquisition groups, seed " + str(seed),
        groups=assignment,
    ))
    write_json(output / "data_audit.json", audit)
    if audit["exact_pixel_cross_split"]:
        raise ValueError("Exact duplicate leakage detected. Review data_audit.json before training.")
    print(f"{dataset}: {audit['counts']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=SOURCES, required=True)
    parser.add_argument("--root", type=Path, default=Path("outputs/yolo-three-datasets-20261115"))
    parser.add_argument("--stage", choices=("download", "prepare", "all"), default="all")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    archive = args.root / "downloads" / SOURCES[args.dataset]["filename"]
    if args.stage in ("download", "all"):
        archive = download_archive(args.dataset, args.root / "downloads")
    if args.stage in ("prepare", "all"):
        if md5_file(archive) != SOURCES[args.dataset]["md5"]:
            raise ValueError("Archive checksum mismatch")
        prepare(args.dataset, archive, args.root / "datasets" / args.dataset, args.seed)


if __name__ == "__main__":
    main()
