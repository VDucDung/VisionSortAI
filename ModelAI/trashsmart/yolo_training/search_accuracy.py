"""Compare YOLO checkpoints/resolutions on validation and select a measured operating point."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def capture_validator_class(deployment_confidence=None):
    """Keep native AP matching stats for exact deployment-threshold scoring."""
    import numpy as np
    from ultralytics.models.yolo.detect.val import DetectionValidator

    class CaptureValidator(DetectionValidator):
        def update_metrics(self, preds, batch):
            if deployment_confidence is not None:
                if not hasattr(self, "deployment_counts"):
                    self.deployment_counts = dict(correct=0, predictions=0, objects=0)
                for index, pred in enumerate(preds):
                    prepared = self._prepare_batch(index, batch)
                    pred = self._prepare_pred(pred)
                    mask = pred["conf"] >= deployment_confidence
                    filtered = {key: value[mask] for key, value in pred.items()}
                    # Re-match after confidence filtering: a removed low-confidence
                    # box must not retain an IoU match against an accepted box.
                    correct = int(self._process_batch(filtered, prepared)["tp"][:, 0].sum())
                    self.deployment_counts["correct"] += correct
                    self.deployment_counts["predictions"] += int(mask.sum())
                    self.deployment_counts["objects"] += len(prepared["cls"])
            return super().update_metrics(preds, batch)

        def get_stats(self):
            self.metrics.operating_stats = {k: np.concatenate(v, 0) for k, v in self.metrics.stats.items()}
            if deployment_confidence is not None:
                self.metrics.deployment_counts = self.deployment_counts
            return super().get_stats()

    return CaptureValidator


def operating_metrics(confidence, true_positive, objects, threshold):
    selected = [(score, tp) for score, tp in zip(confidence, true_positive) if score >= threshold]
    correct = sum(int(tp) for _, tp in selected)
    return metrics_from_counts(correct, len(selected), objects, threshold)


def metrics_from_counts(correct, predictions, objects, threshold):
    precision = correct / predictions if predictions else 0.0
    recall = correct / objects if objects else 0.0
    return dict(confidence=float(threshold), precision=precision, recall=recall,
                f1=2 * precision * recall / (precision + recall) if precision + recall else 0.0,
                true_positives=correct, predictions=predictions, objects=objects)


def stable_threshold(confidence, selected_score):
    """Pick inside the equivalent score interval, avoiding > versus >= at its boundary."""
    lower = max((float(score) for score in confidence if score < selected_score), default=.001)
    return (lower + selected_score) / 2 if lower < selected_score else selected_score


def choose_operating_point(confidence, true_positive, objects, target_recall=.9, min_precision=.9):
    """Highest threshold meeting both constraints, including all predictions tied at a score."""
    if objects <= 0:
        raise ValueError("Validation must contain annotated objects")
    if len(confidence) != len(true_positive):
        raise ValueError("Prediction stats have different lengths")
    if not 0 < target_recall <= 1 or not 0 <= min_precision <= 1:
        raise ValueError("Invalid precision/recall targets")
    if not all(math.isfinite(float(score)) and 0 <= score <= 1 for score in confidence):
        raise ValueError("Invalid prediction confidence")
    rows = sorted(zip(confidence, true_positive), key=lambda row: row[0], reverse=True)
    correct, fallback = 0, None
    for i, (score, tp) in enumerate(rows):
        correct += int(tp)
        if i + 1 < len(rows) and score == rows[i+1][0]:
            continue
        precision, recall = correct / (i+1), correct / objects
        point = dict(confidence=float(score), precision=precision, recall=recall,
                     f1=2*precision*recall/(precision+recall) if precision+recall else 0.0,
                     true_positives=correct, predictions=i+1, objects=objects)
        if precision >= min_precision:
            if fallback is None or (recall, precision) > (fallback["recall"], fallback["precision"]):
                fallback = point
            if recall >= target_recall:
                return dict(target_met=True, point=point)
    return dict(target_met=False, point=fallback)


def best_balanced_point(confidence, true_positive, objects):
    """Maximize the weaker of precision/recall, without relaxing either target."""
    if objects <= 0 or len(confidence) != len(true_positive):
        raise ValueError("Invalid validation counts")
    rows = sorted(zip(confidence, true_positive), key=lambda row: row[0], reverse=True)
    correct, best = 0, None
    for index, (score, tp) in enumerate(rows):
        correct += int(tp)
        if index + 1 < len(rows) and score == rows[index + 1][0]:
            continue
        point = metrics_from_counts(correct, index+1, objects, score)
        key = (min(point["precision"], point["recall"]), point["f1"])
        if best is None or key > best[0]:
            best = key, point
    if best is None:
        return metrics_from_counts(0, 0, objects, .5)
    point = best[1]
    point["confidence"] = stable_threshold(confidence, point["confidence"])
    return point


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints", nargs="+", required=True)
    parser.add_argument("--data", help="YOLO data.yaml; uses project configuration by default")
    parser.add_argument("--imgsz", nargs="+", type=int, default=[640])
    parser.add_argument("--tta", choices=("off", "on", "both"), default="off")
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", required=True, help="New experiment directory")
    parser.add_argument("--target-recall", type=float, default=.9)
    parser.add_argument("--target-map50", type=float, default=.9)
    parser.add_argument("--min-precision", type=float, default=.9)
    parser.add_argument("--nms-iou", type=float, default=.7)
    args = parser.parse_args()
    if min(args.imgsz) < 32 or min(args.batch, args.threads) < 1:
        parser.error("Image size >=32, batch and threads must be positive")
    if not all(math.isfinite(v) and 0 < v <= 1 for v in
               (args.target_recall, args.target_map50, args.nms_iou)) or not 0 <= args.min_precision <= 1:
        parser.error("Invalid targets or thresholds")
    import numpy as np
    import torch
    from ultralytics import YOLO
    from trashsmart.yolo_training.config import DATA_YAML_PATH

    CaptureValidator = capture_validator_class()

    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError(f"Choose a new experiment directory: {output}")
    paths = [Path(p).resolve() for p in args.checkpoints]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    data = Path(args.data or DATA_YAML_PATH).resolve()
    if not data.is_file():
        raise FileNotFoundError(data)
    output.mkdir(parents=True)
    torch.set_num_threads(args.threads)
    report = dict(split="val", data=str(data), settings=vars(args),
                  scope="single-class object detection; Recall measured at IoU 0.5",
                  summary_recall="Ultralytics Recall at its max-F1 operating point",
                  target_recall="Exact validation TP/GT at the chosen confidence, with precision floor",
                  trials=[])
    tta_values = [False, True] if args.tta == "both" else [args.tta == "on"]
    for path in paths:
        for image_size in args.imgsz:
            for tta in tta_values:
                index = len(report["trials"])
                print(f"TRIAL {index}: {path}; imgsz={image_size}; TTA={tta}", flush=True)
                model = YOLO(str(path))
                # CPU device selection resets Torch threads inside Ultralytics.
                model.add_callback("on_val_start", lambda validator: torch.set_num_threads(args.threads))
                metrics = model.val(
                    validator=CaptureValidator, data=str(data), single_cls=True, split="val",
                    imgsz=image_size, batch=args.batch, workers=0, device=args.device,
                    conf=.001, iou=args.nms_iou, augment=tta, plots=False, save=False,
                    project=str(output / "trials"), name=f"trial-{index:02d}", exist_ok=False,
                    verbose=False)
                stats = metrics.operating_stats
                scores = stats["conf"].tolist()
                tp = stats["tp"][:, 0].tolist()
                objects = len(stats["target_cls"])
                point = choose_operating_point(scores, tp, objects, args.target_recall, args.min_precision)
                values = dict(map50=float(metrics.box.map50), map50_95=float(metrics.box.map),
                              precision_max_f1=float(metrics.box.mp), recall_max_f1=float(metrics.box.mr))
                if not all(math.isfinite(v) and 0 <= v <= 1 for v in values.values()):
                    raise ValueError("Invalid validation metrics")
                trial = dict(checkpoint=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             imgsz=image_size, tta=tta, nms_iou=args.nms_iou, metrics=values,
                             operating_point=point,
                             both_targets_met=values["map50"] >= args.target_map50 and point["target_met"],
                             summary_targets_met=values["map50"] >= args.target_map50 and
                                                 values["recall_max_f1"] >= args.target_recall and
                                                 values["precision_max_f1"] >= args.min_precision,
                             fixed_thresholds=[operating_metrics(scores, tp, objects, threshold)
                                               for threshold in (.05, .1, .15, .2, .25, .35, .5)],
                             speed=metrics.speed, effective_torch_threads=torch.get_num_threads())
                report["trials"].append(trial)
                (output / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                np.savez_compressed(output / f"trial-{index:02d}-stats.npz",
                                    confidence=np.asarray(scores), tp=np.asarray(tp), objects=objects)
                print(json.dumps(trial, indent=2), flush=True)
    print(f"Results: {output / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
