"""Evaluate actual YOLO boxes + ResNet on original annotated images, including misses."""
import argparse
import hashlib
import json
from pathlib import Path

from trashsmart.training.detection_metrics import read_annotations, match_objects, summarize_images


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="YOLO dataset root with images/labels per split")
    parser.add_argument("--classes", nargs="+", required=True, help="Verified material names in annotation ID order")
    parser.add_argument("--split", choices=("valid", "test"), default="valid")
    parser.add_argument("--resnet", required=True)
    parser.add_argument("--yolo")
    parser.add_argument("--output", required=True)
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.6, help="YOLO NMS IoU")
    parser.add_argument("--match-iou", type=float, default=0.5, help="Evaluation box matching IoU")
    parser.add_argument("--material-threshold", type=float, default=0.5)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--imgsz", type=int, help="Override the API YOLO image size for validation experiments")
    parser.add_argument("--tta", action="store_true", help="YOLO test-time augmentation")
    args = parser.parse_args()
    if not all(0 <= v <= 1 for v in (args.conf, args.iou, args.material_threshold)) or not 0 < args.match_iou <= 1:
        parser.error("Thresholds must be in [0,1], matching IoU must be in (0,1]")
    if args.threads < 1:
        parser.error("Threads must be positive")
    if args.imgsz is not None and args.imgsz < 32:
        parser.error("YOLO image size must be >= 32")
    import cv2
    import numpy as np
    import torch
    from ultralytics import YOLO
    from trashsmart.shared.classes import CLASS_NAMES, validate_class_order
    from trashsmart.shared.model import load_resnet_checkpoint
    from trashsmart.shared.paths import YOLO_MODEL_PATH
    from trashsmart.shared.preprocessing import preprocess_resnet_crop
    from trashsmart.pipeline.config import YOLO_IMG_SIZE
    from trashsmart.shared.resnet_config import FIX_LOW_LIGHT, FIX_MOTION_BLUR
    image_size = args.imgsz or YOLO_IMG_SIZE
    validate_class_order(args.classes)
    torch.set_num_threads(args.threads)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    source, output = Path(args.source).resolve(), Path(args.output)
    if output.exists():
        raise FileExistsError(f"Choose a new report path: {output}")
    yolo_path, resnet_path = Path(args.yolo or YOLO_MODEL_PATH).resolve(), Path(args.resnet).resolve()
    yolo, resnet = YOLO(str(yolo_path)), load_resnet_checkpoint(resnet_path, len(CLASS_NAMES), device)
    files = sorted(p for p in (source / args.split / "images").iterdir()
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"})
    if not files:
        raise ValueError("No evaluation images")
    if len({p.stem for p in files}) != len(files):
        raise ValueError("Ambiguous annotation mapping: duplicate image stems")
    records = []
    for i, path in enumerate(files):
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot decode {path}")
        h, w = image.shape[:2]
        label_path = source / args.split / "labels" / (path.stem + ".txt")
        truth = read_annotations(label_path.read_text(encoding="utf-8-sig"), w, h, len(CLASS_NAMES))
        result = yolo(image, imgsz=image_size, conf=args.conf, iou=args.iou,
                      device=str(device), augment=args.tta, agnostic_nms=True, verbose=False)[0]
        predictions, crops = [], []
        if result.boxes is not None:
            for box, score in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist()):
                x1, y1, x2, y2 = map(int, box)
                x1, y1 = max(0, min(x1, w-1)), max(0, min(y1, h-1))
                x2, y2 = max(0, min(x2, w)), max(0, min(y2, h))
                if x2 <= x1 or y2 <= y1:
                    continue
                crops.append(preprocess_resnet_crop(image[y1:y2, x1:x2]))
                predictions.append(dict(box=[x1, y1, x2, y2], confidence=score))
        if crops:
            # Bound classifier memory for crowded images.
            scores, labels = [], []
            with torch.inference_mode():
                for start in range(0, len(crops), 16):
                    probabilities = resnet(torch.stack(crops[start:start+16]).to(device)).softmax(1)
                    if not torch.isfinite(probabilities).all():
                        raise FloatingPointError(f"Non-finite classifier output: {path}")
                    batch_scores, batch_labels = probabilities.max(1)
                    scores.extend(batch_scores.cpu().tolist())
                    labels.extend(batch_labels.cpu().tolist())
            for obj, score, label in zip(predictions, scores, labels):
                obj.update(label=label if score >= args.material_threshold else -1,
                           raw_label=label, material_confidence=score)
        matches, missed, extra = match_objects(truth, predictions, args.match_iou)
        records.append(dict(image=str(path), truth=truth, predictions=predictions,
                            matches=matches, missed=missed, false_positives=extra))
        if (i+1) % 25 == 0:
            print(f"Evaluated {i+1}/{len(files)} images", flush=True)
    report = dict(settings=vars(args), classes=list(CLASS_NAMES), images=len(files),
                  imgsz=image_size, device=str(device),
                  enhancement=dict(low_light=FIX_LOW_LIGHT, motion_blur=FIX_MOTION_BLUR),
                  checkpoints={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (yolo_path, resnet_path)},
                  matching="confidence-ordered one-to-one boxes, material scored after matching; not COCO mAP",
                  **summarize_images(records, CLASS_NAMES), records=records)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["totals"], indent=2), flush=True)
    print(f"Report: {output}", flush=True)


if __name__ == "__main__":
    main()
