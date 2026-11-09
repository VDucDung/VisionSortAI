"""Validation-only error inventory for review; never edits annotations or selects on test."""
import argparse
import json
from pathlib import Path

from trashsmart.training.detection_metrics import read_annotations, match_objects, box_iou


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--conf", type=float, default=.29251672327518463)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    import yaml
    import torch
    from ultralytics import YOLO
    config = yaml.safe_load(args.data.read_text(encoding="utf-8"))
    folder = Path(config["path"]) / config["val"]
    model = YOLO(str(args.model))
    if len(model.names) != 1:
        raise ValueError("Expected single-class localization model")
    model.add_callback("on_predict_start", lambda predictor: torch.set_num_threads(4))
    totals = dict(images=0, objects=0, predictions=0, matched=0, missed=0,
                  false_positives=0, duplicate=0, localization=0, background_or_unlabeled=0)
    rows = []
    for result in model.predict(source=str(folder), stream=True, device="cpu", imgsz=640,
                                batch=4, conf=args.conf, iou=.7, agnostic_nms=True,
                                verbose=False, save=False):
        image = Path(result.path)
        height, width = result.orig_shape
        truth = read_annotations((folder.parent / "labels" / (image.stem + ".txt")).read_text(),
                                 width, height, 1)
        predictions = [dict(box=box, confidence=score) for box, score in
                       zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist())]
        matches, missed, extra = match_objects(truth, predictions)
        categories = []
        for index in extra:
            overlap = max((box_iou(predictions[index]["box"], obj["box"]) for obj in truth), default=0)
            category = "duplicate" if overlap >= .5 else "localization" if overlap >= .1 else "background_or_unlabeled"
            totals[category] += 1
            categories.append(dict(prediction=index, category=category, best_iou=overlap))
        for key, value in dict(images=1, objects=len(truth), predictions=len(predictions),
                               matched=len(matches), missed=len(missed), false_positives=len(extra)).items():
            totals[key] += value
        if missed or extra:
            rows.append(dict(image=str(image), truth=truth, predictions=predictions,
                             missed=missed, false_positives=categories))
    rows.sort(key=lambda row: len(row["missed"])+len(row["false_positives"]), reverse=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(split="val", confidence=args.conf,
        matching="confidence-ordered IoU>=0.5; diagnostic only, native metrics remain authoritative",
        totals=totals, errors=rows), indent=2), encoding="utf-8")
    print(json.dumps(totals), flush=True)


if __name__ == "__main__":
    main()
