"""Evaluate the same best_new.pt checkpoint used by the API."""
import argparse
import hashlib
import json
from pathlib import Path
from ultralytics import YOLO
from trashsmart.shared.paths import YOLO_MODEL_PATH
from trashsmart.yolo_training.config import DATA_YAML_PATH, IMG_SIZE, BATCH_SIZE, DEVICE
from trashsmart.yolo_training.search_accuracy import capture_validator_class, metrics_from_counts
from trashsmart.pipeline.config import CONF_THRESHOLD, YOLO_IOU_THRESHOLD, YOLO_TTA


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("val", "test"), default="val")
    parser.add_argument("--model", type=Path, default=YOLO_MODEL_PATH)
    parser.add_argument("--data", type=Path, default=DATA_YAML_PATH)
    parser.add_argument("--imgsz", type=int, default=IMG_SIZE)
    parser.add_argument("--batch", type=int, default=BATCH_SIZE)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--conf", type=float, default=CONF_THRESHOLD, help="Deployment confidence; AP still uses conf=0.001")
    parser.add_argument("--iou", type=float, default=YOLO_IOU_THRESHOLD, help="NMS IoU")
    parser.add_argument("--tta", action=argparse.BooleanOptionalAction, default=YOLO_TTA)
    parser.add_argument("--output", type=Path, help="New JSON report path")
    args = parser.parse_args()
    if args.imgsz < 32 or min(args.batch, args.threads) < 1 or not (0 <= args.conf <= 1 and 0 < args.iou <= 1):
        parser.error("Invalid image size, batch, threads or confidence/IoU")
    if not args.model.is_file():
        raise FileNotFoundError(args.model)
    if not args.data.is_file():
        raise FileNotFoundError(args.data)
    if args.output and args.output.exists():
        raise FileExistsError(args.output)
    import torch
    torch.set_num_threads(args.threads)
    print(f"Evaluating: {args.model}")
    model = YOLO(str(args.model))
    model.add_callback("on_val_start", lambda validator: torch.set_num_threads(args.threads))
    metrics = model.val(
        validator=capture_validator_class(args.conf),
        data=str(args.data), imgsz=args.imgsz, batch=args.batch, workers=0,
        device=DEVICE, single_cls=True, split=args.split, conf=.001,
        iou=args.iou, augment=args.tta, plots=False,
    )
    print(f"Precision (max-F1): {metrics.box.mp:.4%}")
    print(f"Recall (max-F1): {metrics.box.mr:.4%}")
    print(f"mAP50: {metrics.box.map50:.4%}")
    print(f"mAP50-95: {metrics.box.map:.4%}")
    counts = metrics.deployment_counts
    point = metrics_from_counts(counts["correct"], counts["predictions"], counts["objects"], args.conf)
    print(f"At deployed conf={args.conf:.6f}: Precision={point['precision']:.4%}; Recall={point['recall']:.4%}")
    if args.output:
        report = dict(split=args.split, checkpoint=str(args.model.resolve()),
                      checkpoint_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                      data=str(args.data.resolve()), imgsz=args.imgsz, tta=args.tta, nms_iou=args.iou,
                      map50=float(metrics.box.map50), map50_95=float(metrics.box.map),
                      precision_max_f1=float(metrics.box.mp), recall_max_f1=float(metrics.box.mr),
                      operating_point=point, speed=metrics.speed)
        report["operating_point_matching"] = "Native IoU matching recomputed after deployment confidence filter"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
