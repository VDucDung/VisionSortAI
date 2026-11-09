"""Time-limited CPU fine-tuning; retain the baseline unless balanced mAP50/Recall improves."""
import argparse
import json
import math
import shutil
import hashlib
import os
import time
from pathlib import Path


def balanced_score(map50, recall):
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (map50, recall)):
        raise ValueError("Invalid validation mAP50/Recall")
    return min(map50, recall), (map50 + recall) / 2


def precision_recall_score(precision, recall, map50):
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (precision, recall, map50)):
        raise ValueError("Invalid validation Precision/Recall/mAP50")
    f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
    return min(precision, recall), f1, map50


def write_json_atomic(path, value):
    path = Path(path)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(pending, path)


def copy_checkpoint(source, target):
    target = Path(target)
    pending = target.with_name(target.name + ".pending")
    shutil.copy2(source, pending)
    os.replace(pending, target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path, help="Existing local checkpoint")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--minutes", type=float, default=30, help="Training-loop time cap; excludes final validation")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=.00005)
    parser.add_argument("--freeze", type=int, default=10, help="Frozen early layers to limit CPU work")
    parser.add_argument("--objective", choices=("precision_recall", "map50_recall"), default="precision_recall")
    parser.add_argument("--mosaic", type=float, default=0.0)
    parser.add_argument("--close-mosaic", type=int, default=0)
    parser.add_argument("--warmup-epochs", type=float, default=.5)
    parser.add_argument("--patience", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--stop-buffer", type=float, default=.94)
    parser.add_argument("--stop-streak", type=int, default=3)
    args = parser.parse_args()
    if min(args.epochs, args.batch, args.threads) < 1 or args.imgsz < 32 or args.freeze < 0:
        parser.error("Invalid epochs/batch/threads/image size/freeze")
    if not all(math.isfinite(v) and v > 0 for v in (args.minutes, args.learning_rate)):
        parser.error("Time and learning rate must be finite and positive")
    if not 0 <= args.mosaic <= 1 or args.close_mosaic < 0 or args.warmup_epochs < 0 or min(args.patience, args.stop_streak) < 1 or not .9 <= args.stop_buffer <= 1:
        parser.error("Invalid augmentation or stopping settings")
    if not args.model.is_file():
        raise FileNotFoundError(args.model)
    output = args.run_dir.resolve()
    if output.exists():
        raise FileExistsError(f"Choose a new run directory: {output}")
    import torch
    from ultralytics import YOLO
    from trashsmart.yolo_training.config import DATA_YAML_PATH
    data = (args.data or DATA_YAML_PATH).resolve()
    if not data.is_file():
        raise FileNotFoundError(data)
    torch.set_num_threads(args.threads)
    output.mkdir(parents=True)
    validation = dict(data=str(data), single_cls=True, split="val", imgsz=args.imgsz,
                      # DetectionTrainer evaluates with twice the training batch.
                      batch=args.batch * 2, workers=0, device="cpu", conf=.001, iou=.7,
                      augment=False, plots=False, project=str(output), name="baseline_val")
    baseline_model = YOLO(str(args.model))
    baseline_model.add_callback("on_val_start", lambda validator: torch.set_num_threads(args.threads))
    baseline = baseline_model.val(**validation)
    def score_metrics(precision, recall, map50):
        return (precision_recall_score(precision, recall, map50) if args.objective == "precision_recall"
                else balanced_score(map50, recall))
    best_score = score_metrics(float(baseline.box.mp), float(baseline.box.mr), float(baseline.box.map50))
    champion = output / ("best_precision_recall.pt" if args.objective == "precision_recall" else "best_map50_recall.pt")
    copy_checkpoint(args.model, champion)
    decision = dict(settings={**vars(args), "model": str(args.model.resolve()),
                              "data": str(data), "run_dir": str(output)},
                    starting_sha256=hashlib.sha256(args.model.read_bytes()).hexdigest(),
                    validation_batch=args.batch * 2,
                    selection=("maximize min(validation Precision, Recall), then F1 and mAP50" if args.objective == "precision_recall"
                               else "maximize min(validation mAP50, Recall), then their mean"),
                    baseline=dict(precision=float(baseline.box.mp), map50=float(baseline.box.map50), recall=float(baseline.box.mr)),
                    selected_epoch="baseline", selected_metrics=None,
                    status="training", pid=os.getpid(), last_epoch=0,
                    note="No test access; no API publication. Compare chosen weights with search_accuracy before deployment.")
    def write_decision():
        write_json_atomic(output / "selection.json", decision)
    write_decision()

    streak = 0
    unimproved = 0
    def select_epoch(trainer):
        nonlocal best_score, streak, unimproved
        values = trainer.metrics
        map50, recall = float(values["metrics/mAP50(B)"]), float(values["metrics/recall(B)"])
        precision = float(values["metrics/precision(B)"])
        score = score_metrics(precision, recall, map50)
        metrics = dict(precision=precision, recall=recall, map50=map50)
        decision.update(last_epoch=trainer.epoch+1, last_metrics=metrics)
        copy_checkpoint(trainer.last, output / "resume_last.pt")
        if score > best_score and Path(trainer.last).is_file():
            copy_checkpoint(trainer.last, champion)
            best_score = score
            decision.update(selected_epoch=trainer.epoch + 1,
                            selected_metrics=metrics)
            unimproved = 0
        else:
            unimproved += 1
        streak = streak+1 if min(precision, recall) >= args.stop_buffer else 0
        if args.objective == "precision_recall" and streak >= args.stop_streak:
            trainer.stop = True
            decision["buffer_stopping"] = True
        if args.objective == "precision_recall" and unimproved >= args.patience:
            trainer.stop = True
            decision["pr_patience_stopping"] = True
        write_decision()
    last_progress = 0.0
    def progress_batch(trainer):
        nonlocal last_progress
        if time.monotonic() - last_progress >= 30:
            decision.update(active_epoch=trainer.epoch+1, elapsed_training_seconds=time.time()-trainer.train_time_start)
            write_decision()
            last_progress = time.monotonic()
    def limit_epochs(trainer):
        # This also runs after final_eval, whose metrics may belong to best.pt
        # rather than last.pt. Selection must run only at the save event above.
        trainer.stop |= trainer.epoch + 1 >= args.epochs

    model = YOLO(str(args.model))
    model.add_callback("on_train_start", lambda trainer: torch.set_num_threads(args.threads))
    model.add_callback("on_val_start", lambda validator: torch.set_num_threads(args.threads))
    model.add_callback("on_model_save", select_epoch)
    model.add_callback("on_train_batch_end", progress_batch)
    model.add_callback("on_fit_epoch_end", limit_epochs)
    model.train(data=str(data), single_cls=True, device="cpu", workers=0,
                project=str(output), name="training", exist_ok=False,
                epochs=args.epochs, time=args.minutes / 60, batch=args.batch,
                imgsz=args.imgsz, optimizer="AdamW", lr0=args.learning_rate,
                lrf=.1, cos_lr=True, warmup_epochs=args.warmup_epochs, warmup_bias_lr=0.0,
                weight_decay=.0005, freeze=args.freeze,
                patience=max(args.patience, args.epochs+1) if args.objective == "precision_recall" else args.patience,
                mosaic=args.mosaic, close_mosaic=args.close_mosaic, mixup=0.0, degrees=5,
                translate=.05, scale=.25, fliplr=.5, flipud=0.0,
                hsv_h=.015, hsv_s=.3, hsv_v=.25, seed=args.seed,
                cache=False, amp=False, plots=True, save=True, save_period=5, resume=False)
    decision["status"] = "complete"
    write_decision()
    print(f"Selected weights: {champion}", flush=True)


if __name__ == "__main__":
    main()
