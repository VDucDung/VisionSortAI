"""Sequential CPU training with strict validation/test gates and automatic local publication."""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

from trashsmart.yolo_training.train_accuracy import write_json_atomic, copy_checkpoint, precision_recall_score
from trashsmart.yolo_training.pr90_policy import sha256, strict_target_met, publication_allowed


def now():
    return datetime.now(timezone(timedelta(hours=7))).isoformat()


def stage_plan(continuation=False, head_epochs=8, finetune_epochs=60, polish_epochs=15):
    if continuation:
        return [("finetune", finetune_epochs, 0, .00005, .15, 3, .8),
                ("polish", polish_epochs, 0, .00002, 0.0, 0, .2)]
    return [("head", head_epochs, 10, .001, .5, 2, .15),
            ("finetune", finetune_epochs, 0, .0001, .3, 5, .70),
            ("polish", polish_epochs, 0, .00002, 0.0, 0, .15)]


def dataset_fingerprint(data, require_test=True):
    """Fingerprint image/label contents; cache files and training outputs are excluded."""
    import yaml
    config = yaml.safe_load(data.read_text(encoding="utf-8"))
    root = Path(config["path"]).resolve()
    folders = []
    digest = hashlib.sha256(data.read_bytes())
    image_hashes = {}
    for split in ("train", "val", "test"):
        if split == "test" and not require_test and not config.get(split):
            continue
        folder = Path(config[split])
        folder = (root / folder).resolve() if not folder.is_absolute() else folder.resolve()
        if folder in folders or folder.name != "images":
            raise ValueError("Prepared data must use distinct train/valid/test images directories")
        folders.append(folder)
        images = sorted(path for path in folder.iterdir() if path.suffix.lower() in
                        {".jpg", ".jpeg", ".png", ".bmp", ".webp"})
        if not images:
            raise ValueError(f"Empty split: {split}")
        for image in images:
            value = sha256(image)
            if value in image_hashes and image_hashes[value] != split:
                raise ValueError("Exact image duplicate across splits; audit dataset before training")
            image_hashes[value] = split
            label = folder.parent / "labels" / (image.stem + ".txt")
            digest.update(f"{split}/{image.name}:{value}:{sha256(label)}\n".encode())
    return digest.hexdigest()


def evaluate(path, data, output, threads, batch, split="val", confidence=None):
    """Full AP plus rematched fixed-confidence counts; confidence chosen only on validation."""
    import torch
    from ultralytics import YOLO
    from trashsmart.yolo_training.search_accuracy import (
        capture_validator_class, best_balanced_point, metrics_from_counts,
    )
    model = YOLO(str(path))
    if len(model.names) != 1:
        raise ValueError("Publication candidate must have exactly one localization class")
    model.add_callback("on_val_start", lambda validator: torch.set_num_threads(threads))
    options = dict(data=str(data), imgsz=640, batch=batch, workers=0, device="cpu",
                   single_cls=True, split=split, conf=.001, iou=.7, augment=False,
                   plots=False, verbose=False, project=str(output), name=split)
    metrics = model.val(validator=capture_validator_class(confidence), **options)
    if confidence is None:
        if split != "val":
            raise ValueError("Test confidence must be fixed before reading test results")
        stats = metrics.operating_stats
        confidence = best_balanced_point(stats["conf"].tolist(), stats["tp"][:, 0].tolist(),
                                         len(stats["target_cls"]))["confidence"]
        # Recompute IoU matching after confidence filtering in a second validation pass.
        metrics = model.val(validator=capture_validator_class(confidence), **options)
    counts = metrics.deployment_counts
    report = dict(split=split, checkpoint=str(path), checkpoint_sha256=sha256(path), data=str(data),
                  imgsz=640, tta=False, nms_iou=.7, precision_max_f1=float(metrics.box.mp),
                  recall_max_f1=float(metrics.box.mr), map50=float(metrics.box.map50),
                  map50_95=float(metrics.box.map),
                  operating_point=metrics_from_counts(counts["correct"], counts["predictions"],
                                                       counts["objects"], confidence), speed=metrics.speed)
    write_json_atomic(output / f"{split}_metrics.json", report)
    return report


def publish(candidate, validation, test, active, expected_active_sha, root, run):
    digest = sha256(candidate)
    if not publication_allowed(validation, test, digest):
        return dict(status="not_published", reason="Precision/Recall/mAP50 target or identical-settings gate failed")
    if sha256(active) != expected_active_sha:
        return dict(status="not_published", reason="Active model changed since job started")
    env_path = root / ".env"
    if not env_path.is_file():
        return dict(status="not_published", reason="Missing local .env; weights and configuration retained")
    backup = run / "backup" / "best_new.pt"
    backup.parent.mkdir(parents=True, exist_ok=True)
    copy_checkpoint(active, backup)
    original_env = env_path.read_text(encoding="utf-8-sig")
    updated = original_env
    configuration = dict(YOLO_IMG_SIZE=640, YOLO_TTA=0, YOLO_IOU_THRESHOLD=.7,
                         YOLO_AGNOSTIC_NMS=1, YOLO_CONF_THRESHOLD=validation["operating_point"]["confidence"])
    for key, value in configuration.items():
        pattern = r"(?m)^(?:export[ \t]+)?" + re.escape(key) + r"[ \t]*=.*$"
        line = key + "=" + str(value)
        updated = re.sub(pattern, line, updated) if re.search(pattern, updated) else updated.rstrip()+"\n"+line+"\n"
    env_pending = root / ".env.pr90.pending"
    if env_pending.exists():
        raise FileExistsError(env_pending)
    env_pending.write_text(updated, encoding="utf-8")
    try:
        copy_checkpoint(candidate, active)
        os.replace(env_pending, env_path)
    except Exception:
        copy_checkpoint(backup, active)
        if env_pending.exists():
            env_pending.unlink()
        raise
    return dict(status="published", checkpoint=str(active), sha256=digest, backup=str(backup),
                configuration=configuration, restart_api_required=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretrained", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--hours", type=float, default=8)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--head-epochs", type=int, default=8)
    parser.add_argument("--finetune-epochs", type=int, default=60)
    parser.add_argument("--polish-epochs", type=int, default=15)
    parser.add_argument("--continuation", action="store_true",
                        help="Continue a single-class checkpoint without repeating COCO head training")
    parser.add_argument("--smoke", action="store_true", help="No publication or test access; tiny pipeline check")
    args = parser.parse_args()
    if not math.isfinite(args.hours) or args.hours <= 0 or min(args.threads, args.batch,
            args.head_epochs, args.finetune_epochs, args.polish_epochs) < 1:
        parser.error("Hours/threads/batch/epochs must be finite and positive")
    root = Path(__file__).resolve().parents[2]
    run, data, pretrained = args.run_dir.resolve(), args.data.resolve(), args.pretrained.resolve()
    if run.exists():
        raise FileExistsError(f"Choose a new run directory: {run}")
    if not data.is_file() or not pretrained.is_file():
        raise FileNotFoundError("Data and pretrained checkpoint must exist")
    from trashsmart.shared.paths import YOLO_MODEL_PATH
    run.mkdir(parents=True)
    state = dict(status="starting", started_at=now(), pid=os.getpid(), settings={
        **vars(args), "pretrained": str(pretrained), "data": str(data), "run_dir": str(run)},
        objective="Precision >=90% AND Recall >=90%, native summary AND one fixed deployed confidence; mAP50 >=90%",
        active_model_sha256=sha256(YOLO_MODEL_PATH), pretrained_sha256=sha256(pretrained),
        stages=[], candidates=[], test_selection_policy="validation only; test evaluated once on final selected candidate",
        optimizer_resume="Stage transitions start a fresh optimizer; full per-epoch checkpoints are retained")
    def save():
        state["updated_at"] = now()
        write_json_atomic(run / "progress.json", state)
    save()
    awake = None
    if os.name == "nt":
        import ctypes
        awake = ctypes.windll.kernel32.SetThreadExecutionState
        awake(0x80000001)  # Process-scoped system-awake request; display may sleep/lock normally.
    deadline = time.monotonic() + args.hours * 3600
    process = None
    try:
        state["dataset_fingerprint"] = dataset_fingerprint(data, require_test=not args.smoke)
        state["expected_training_end_at"] = (datetime.now(timezone(timedelta(hours=7))) + timedelta(hours=args.hours)).isoformat()
        save()
        stages = stage_plan(args.continuation, args.head_epochs, args.finetune_epochs, args.polish_epochs)
        source = pretrained
        best_s, best_s_score = None, None
        if args.continuation:
            state.update(status="validating", current_stage="continuation_baseline")
            save()
            baseline_dir = run / "continuation_baseline"
            baseline_dir.mkdir()
            baseline = evaluate(source, data, baseline_dir, args.threads, args.batch*2)
            state["continuation_baseline"] = baseline
            best_s = source
            best_s_score = precision_recall_score(baseline["precision_max_f1"],
                                                 baseline["recall_max_f1"], baseline["map50"])
            save()
        for name, epochs, freeze, lr, mosaic, close, fraction in stages:
            remaining = deadline-time.monotonic()
            reserve = 10*60 if not args.smoke else 0
            if remaining <= reserve:
                break
            minutes = min(args.hours*60*fraction, (remaining-reserve)/60)
            if name == "polish":
                minutes = (remaining-reserve)/60
            if args.smoke:
                minutes, epochs, close = 2, 1, 0
            stage_dir = run / name
            command = [sys.executable, "-u", "-m", "trashsmart.yolo_training.train_accuracy",
                "--model", str(source), "--data", str(data), "--run-dir", str(stage_dir),
                "--objective", "precision_recall", "--minutes", str(minutes), "--epochs", str(epochs),
                "--imgsz", "640", "--batch", str(args.batch), "--threads", str(args.threads),
                "--freeze", str(freeze), "--learning-rate", str(lr), "--mosaic", str(mosaic),
                "--close-mosaic", str(close), "--warmup-epochs", "1", "--patience", "12"]
            state.update(status="training", current_stage=name, elapsed_seconds=args.hours*3600-remaining)
            save()
            stage_log = run / f"{name}.log"
            with stage_log.open("w", encoding="utf-8") as stream:
                process = subprocess.Popen(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                state["worker_pid"] = process.pid
                save()
                while process.poll() is None:
                    selection_path = stage_dir / "selection.json"
                    if selection_path.is_file():
                        try:
                            selection = json.loads(selection_path.read_text(encoding="utf-8"))
                            state["current_progress"] = {key: selection.get(key) for key in
                                ("last_epoch", "active_epoch", "last_metrics", "selected_metrics", "selected_epoch", "elapsed_training_seconds")}
                            save()
                        except (OSError, ValueError):
                            pass
                    time.sleep(10)
            if process.returncode:
                raise RuntimeError(f"{name} failed with code {process.returncode}; see {stage_log}")
            selection = json.loads((stage_dir / "selection.json").read_text(encoding="utf-8"))
            source = stage_dir / "best_precision_recall.pt"
            # COCO warm-start can retain the original 80-class baseline. Continue
            # with the trained single-class checkpoint in that case, never publish it blindly.
            from ultralytics import YOLO
            if len(YOLO(str(source)).names) != 1:
                source = stage_dir / "training/weights/best.pt"
            stage_evaluation_dir = stage_dir / "selection_evaluation"
            stage_evaluation_dir.mkdir()
            # Compare serialized weights consistently, including a fresh COCO
            # head that may have retained its 80-class baseline inside the worker.
            stage_metrics = evaluate(source, data, stage_evaluation_dir, args.threads, args.batch*2)
            stage_score = precision_recall_score(stage_metrics["precision_max_f1"],
                                               stage_metrics["recall_max_f1"], stage_metrics["map50"])
            if best_s_score is None or stage_score > best_s_score:
                best_s, best_s_score = source, stage_score
            source = best_s
            state["stages"].append(dict(name=name, selection=selection, evaluation=stage_metrics, checkpoint=str(source)))
            save()
            if name == "polish" and selection.get("buffer_stopping") and strict_target_met(stage_metrics, .94):
                break
            if args.smoke:
                break
        if best_s is None:
            raise RuntimeError("No training stage completed")
        if dataset_fingerprint(data, require_test=not args.smoke) != state["dataset_fingerprint"]:
            raise RuntimeError("Dataset contents changed during training; no test or publication performed")
        state.update(status="validating", current_stage="final_validation")
        save()
        candidate = run / "candidate.pt"
        copy_checkpoint(best_s, candidate)
        from ultralytics.utils.torch_utils import strip_optimizer
        strip_optimizer(candidate)
        validation_dir = run / "evaluation"
        validation_dir.mkdir()
        validation = evaluate(candidate, data, validation_dir, args.threads, args.batch*2)
        state["validation"] = validation
        save()
        if args.smoke:
            state["status"] = "smoke_complete"
            state["publication"] = dict(status="disabled_for_smoke")
        elif not strict_target_met(validation):
            state["status"] = "complete_target_not_met"
            state["publication"] = dict(status="not_published", reason="Validation Precision/Recall target not met; test not read")
        else:
            state["status"] = "testing"
            save()
            test = evaluate(candidate, data, validation_dir, args.threads, args.batch*2, split="test",
                            confidence=validation["operating_point"]["confidence"])
            state["test"] = test
            if dataset_fingerprint(data) != state["dataset_fingerprint"]:
                raise RuntimeError("Dataset changed during final evaluation; publication cancelled")
            state["publication"] = publish(candidate, validation, test, YOLO_MODEL_PATH,
                                           state["active_model_sha256"], root, run)
            state["status"] = "complete_target_met" if publication_allowed(validation, test, sha256(candidate)) else "complete_target_not_met"
        state["finished_at"] = now()
        save()
        print(json.dumps({key: state.get(key) for key in ("status", "validation", "test", "publication")}, indent=2), flush=True)
    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        state.update(status="failed", error=traceback.format_exc(), finished_at=now())
        save()
        raise
    finally:
        if awake:
            awake(0x80000000)


if __name__ == "__main__":
    main()
