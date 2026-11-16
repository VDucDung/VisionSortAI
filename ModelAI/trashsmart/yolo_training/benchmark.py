"""Reproducible YOLO11n vs YOLOv8n experiment; never publishes API weights.

Run `python -m trashsmart.yolo_training.benchmark --help` from ModelAI.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(pending, path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_snapshot(root):
    """Fingerprint all bytes, check labels, exact pixels and near duplicates.

    dHash is only a review signal, not proof that two images show one object.
    No split or label is changed by this audit.
    """
    from PIL import Image, ImageOps
    from trashsmart.training.detection_metrics import read_annotations

    root = Path(root)
    fingerprint, pixels, signatures = hashlib.sha256(), {}, []
    counts, records, exact = {}, [], []
    for split in ("train", "valid", "test"):
        folder = root / split / "images"
        images = sorted(p for p in folder.iterdir() if p.suffix.lower() in
                        {".jpg", ".jpeg", ".png", ".webp", ".bmp"})
        if not images:
            raise ValueError(f"Empty split: {split}")
        counts[split] = dict(images=len(images), objects=0)
        if len({p.stem for p in images}) != len(images):
            raise ValueError(f"Duplicate image stems in {split}")
        for image in images:
            label = root / split / "labels" / (image.stem + ".txt")
            text = label.read_text(encoding="utf-8-sig")
            objects = read_annotations(text, 1, 1, 1)
            if any(len(line.split()) != 5 for line in text.splitlines() if line.strip()):
                raise ValueError("Normalize polygons before benchmarking")
            counts[split]["objects"] += len(objects)
            record = dict(split=split, image=image.relative_to(root).as_posix(),
                          image_sha256=sha256(image), label_sha256=sha256(label))
            fingerprint.update(json.dumps(record, sort_keys=True).encode())
            records.append(record)
            with Image.open(image) as source:
                rgb = ImageOps.exif_transpose(source).convert("RGB")
                key = hashlib.sha256(str(rgb.size).encode() + rgb.tobytes()).hexdigest()
                small = rgb.convert("L").resize((9, 8)).tobytes()
                signature = sum((small[y*9+x] > small[y*9+x+1]) << (y*8+x)
                                for y in range(8) for x in range(8))
                signatures.append((split, record["image"], signature))
            for old_split, old_path in pixels.get(key, []):
                if old_split != split:
                    exact.append([old_path, record["image"]])
            pixels.setdefault(key, []).append((split, record["image"]))
    near = []
    for index, (split, path, signature) in enumerate(signatures):
        for other_split, other_path, other_signature in signatures[index+1:]:
            distance = (signature ^ other_signature).bit_count()
            if split != other_split and distance <= 4:
                near.append(dict(images=[path, other_path], dhash_distance=distance))
    return dict(sha256=fingerprint.hexdigest(), counts=counts, files=records,
                exact_pixel_cross_split=exact, near_duplicate_candidates=near,
                near_duplicate_policy="64-bit dHash distance <=4; review signals only; no automatic removal",
                test_history="The original 182-image test split has appeared in earlier project evaluations; not a newly collected holdout.")


def verify_snapshot(root, expected):
    """Recheck all image/label bytes and YAML routing without repeating image decoding."""
    root = Path(root).resolve()
    config = json.loads((root / "data.yaml").read_text(encoding="utf-8"))
    if config != dict(path=root.as_posix(), train="train/images", val="valid/images",
                      test="test/images", nc=1, names=["item"]):
        raise ValueError("Snapshot YAML routing or class definition changed")
    records = []
    for split in ("train", "valid", "test"):
        images = sorted(p for p in (root/split/"images").iterdir() if p.suffix.lower() in
                        {".jpg", ".jpeg", ".png", ".webp", ".bmp"})
        for image in images:
            label = root/split/"labels"/(image.stem+".txt")
            records.append(dict(split=split, image=image.relative_to(root).as_posix(),
                                image_sha256=sha256(image), label_sha256=sha256(label)))
    digest = hashlib.sha256()
    for record in records:
        digest.update(json.dumps(record, sort_keys=True).encode())
    if digest.hexdigest() != expected:
        raise ValueError("Dataset differs from the frozen snapshot")


def training_options(args):
    """An identical explicit training recipe for both architectures."""
    recipe = dict(epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                device=args.device, workers=0, seed=args.seed, deterministic=True,
                optimizer="AdamW", lr0=.001, lrf=.01, momentum=.937,
                weight_decay=.0005, warmup_epochs=3, warmup_bias_lr=0.0,
                patience=args.epochs+1, single_cls=True, pretrained=True,
                resume=False, freeze=None, amp=False, cache="ram",
                cos_lr=True, close_mosaic=min(5, args.epochs),
                mosaic=1.0, mixup=0.0, copy_paste=0.0,
                degrees=0.0, translate=.1, scale=.5, fliplr=.5, flipud=0.0,
                hsv_h=.015, hsv_s=.7, hsv_v=.4,
                conf=.001, iou=.7, augment=False,
                plots=True, save=True, save_period=5, exist_ok=False)
    if getattr(args, "recipe", "baseline") == "accuracy":
        recipe.update(
            lr0=.0005, cls=1.0, box=7.5, dfl=1.5,
            mosaic=.5, close_mosaic=min(10, args.epochs),
            scale=.3, hsv_s=.4, hsv_v=.3,
        )
    return recipe


def select_winner(rows):
    """Historical deployment weights are never ranked as a controlled training run."""
    controlled = [r for r in rows if r["role"] == "controlled"]
    if len(controlled) != 2:
        raise ValueError("Need exactly two controlled test results")
    ordered = sorted(controlled, key=lambda r: r["map50_95"], reverse=True)
    gap = ordered[0]["map50_95"] - ordered[1]["map50_95"]
    return dict(metric="test mAP50-95", winner=ordered[0]["name"] if gap > 1e-12 else "tie",
                difference_percentage_points=100*gap,
                limitation="One seed and finite training budget; see protocol.test_history for prior test exposure. No claim of statistical significance or general superiority.")


def verify_completed_run(directory, expected_epochs):
    with (Path(directory) / "results.csv").open(encoding="utf-8-sig", newline="") as stream:
        history = list(csv.DictReader(stream))
    epochs = [int(row["epoch"]) for row in history]
    if epochs != list(range(1, expected_epochs + 1)):
        raise ValueError(f"Incomplete or inconsistent training history at {directory}: {epochs}; expected 1..{expected_epochs}")
    return dict(completed_epochs=len(epochs), last_epoch=epochs[-1])


def verify_resume_state(checkpoint, history, recipe):
    epochs = [int(row["epoch"]) for row in history]
    if not epochs or epochs != list(range(1, len(epochs) + 1)) or len(epochs) >= recipe["epochs"]:
        raise ValueError("Resume requires an incomplete contiguous epoch history")
    if checkpoint.get("epoch", -1) + 1 != len(epochs) or checkpoint.get("optimizer") is None:
        raise ValueError("Resume checkpoint epoch/optimizer differs from its history")
    for key, value in recipe.items():
        if key != "resume" and checkpoint.get("train_args", {}).get(key) != value:
            raise ValueError(f"Resume checkpoint recipe changed: {key}")
    return len(epochs)


def evaluate(checkpoint, name, role, args, output):
    import torch
    from ultralytics import YOLO
    from trashsmart.yolo_training.search_accuracy import capture_validator_class, metrics_from_counts

    model = YOLO(str(checkpoint))
    parameters = sum(p.numel() for p in model.model.parameters())
    model.add_callback("on_val_start", lambda validator: torch.set_num_threads(args.threads))
    metrics = model.val(validator=capture_validator_class(args.conf),
                        data=str(output / "dataset" / "data.yaml"), split="test",
                        imgsz=args.imgsz, batch=args.batch, device=args.device,
                        workers=0, single_cls=True, conf=.001, iou=.7,
                        augment=False, plots=True, project=str(output / "evaluation"),
                        name=name, exist_ok=False, verbose=False)
    values = dict(precision_max_f1=float(metrics.box.mp), recall_max_f1=float(metrics.box.mr),
                  map50=float(metrics.box.map50), map50_95=float(metrics.box.map))
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in values.values()):
        raise ValueError("Non-finite or out-of-range evaluation metrics")
    counts = metrics.deployment_counts
    point = metrics_from_counts(counts["correct"], counts["predictions"], counts["objects"], args.conf)
    return dict(name=name, role=role, checkpoint=str(Path(checkpoint).resolve()),
                checkpoint_sha256=sha256(checkpoint), checkpoint_mb=Path(checkpoint).stat().st_size/1e6,
                parameters=parameters,
                split="test", **values, fixed_confidence=point,
                speed_ms_per_image=metrics.speed,
                speed_scope="Ultralytics test validation batch latency on this device; not single-image latency or web end-to-end latency")


def export_results(output, rows):
    fields = ["name", "role", "precision_fixed", "recall_fixed", "f1_fixed",
              "precision_max_f1", "recall_max_f1", "map50", "map50_95",
              "parameters", "checkpoint_mb", "inference_ms"]
    with (output / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({**{k: row[k] for k in fields if k in row},
                             "precision_fixed": row["fixed_confidence"]["precision"],
                             "recall_fixed": row["fixed_confidence"]["recall"],
                             "f1_fixed": row["fixed_confidence"]["f1"],
                             "inference_ms": row["speed_ms_per_image"]["inference"]})
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for row in rows:
        if row["role"] == "controlled":
            with (output / row["name"] / "results.csv").open(encoding="utf-8-sig") as stream:
                history = list(csv.DictReader(stream))
            epochs = [int(h["epoch"]) for h in history]
            axes[0].plot(epochs, [float(h["metrics/mAP50-95(B)"])*100 for h in history], label=row["name"])
            axes[1].plot(epochs, [float(h["train/box_loss"]) for h in history], label=row["name"])
    axes[0].set(title="Validation mAP50-95", xlabel="Epoch", ylabel="mAP (%)")
    axes[1].set(title="Training box loss", xlabel="Epoch", ylabel="Loss")
    for axis in axes:
        axis.grid(alpha=.25)
        axis.legend()
    figure.savefig(output / "training_comparison.png", dpi=180)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Original data-yolo directory")
    parser.add_argument("--output", type=Path, default=Path("outputs/yolo11-vs-yolov8"))
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--conf", type=float, default=.25)
    parser.add_argument("--recipe", choices=("baseline", "accuracy"), default="baseline",
                        help="Shared training recipe for both architectures")
    parser.add_argument("--yolo11", type=Path, default=Path("yolo11n.pt"))
    parser.add_argument("--yolov8", type=Path, default=Path("yolov8n.pt"))
    parser.add_argument("--existing", type=Path, default=Path("trashsmart/models/best_new.pt"))
    parser.add_argument("--stage", choices=("all", "prepare", "train", "evaluate"), default="all")
    parser.add_argument("--model", choices=("both", "yolo11", "yolov8"), default="both",
                        help="Select one architecture for --stage train; other stages require both")
    parser.add_argument("--recover-preparation", action="store_true",
                        help="Finish a failed preparation with its verified snapshot; never overwrites a protocol")
    parser.add_argument("--resume-run", action="store_true",
                        help="Resume one interrupted training run with its original optimizer and frozen recipe")
    args = parser.parse_args()
    if args.resume_run and (args.stage != "train" or args.model == "both"):
        parser.error("--resume-run requires --stage train and a single --model")
    if args.model != "both" and args.stage != "train":
        parser.error("A single --model is supported with --stage train")
    if min(args.epochs, args.batch, args.threads) < 1 or args.imgsz < 32 or args.imgsz % 32 or not 0 < args.conf < 1:
        parser.error("Positive epochs/batch/threads, image size multiple of 32 and confidence in (0,1) required")
    output = args.output.resolve()
    protocol_path = output / "protocol.json"
    if args.stage in ("all", "prepare"):
        recovering = args.recover_preparation and args.stage == "prepare" and not protocol_path.exists()
        if output.exists() and not recovering:
            raise FileExistsError(f"Choose a new output directory: {output}")
        from trashsmart.yolo_training.prepare_detection import prepare
        if args.source is None:
            from trashsmart.yolo_training.config import DATASET_DIR
            args.source = DATASET_DIR
        for path in (args.yolo11, args.yolov8, args.existing):
            if not path.is_file():
                raise FileNotFoundError(path)
        if recovering:
            audit = json.loads((output / "data_audit.json").read_text(encoding="utf-8"))
            verify_snapshot(output / "dataset", audit["sha256"])
        else:
            prepare(args.source, output / "dataset")
            audit = audit_snapshot(output / "dataset")
            source_audit = args.source / "data_audit.json"
            if source_audit.is_file():
                original_audit = json.loads(source_audit.read_text(encoding="utf-8"))
                verify_snapshot(args.source, original_audit["sha256"])
                if original_audit["sha256"] != audit["sha256"]:
                    raise ValueError("Prepared data differs from the previously audited source snapshot")
                audit["test_history"] = original_audit["test_history"]
            provenance = args.source / "source.json"
            if provenance.is_file():
                shutil.copy2(provenance, output / "source.json")
            write_json(output / "data_audit.json", audit)
        if audit["exact_pixel_cross_split"]:
            raise ValueError("Exact duplicate leakage found; review data_audit.json before training")
        import torch
        import ultralytics
        from ultralytics import YOLO
        for name, checkpoint in (("yolo11n", args.yolo11), ("yolov8n", args.yolov8)):
            model = YOLO(str(checkpoint))
            if len(model.names) != 80:
                raise ValueError("Controlled training must start from the original 80-class COCO pretrained weights")
            model_yaml = str(model.model.yaml.get("yaml_file") or model.ckpt.get("train_args", {}).get("model", "")).lower()
            if (name == "yolo11n" and "yolo11n" not in model_yaml) or (name == "yolov8n" and "yolov8n" not in model_yaml):
                raise ValueError(f"Architecture mismatch: {name}: {model_yaml}")
            target = output / "initial" / (name + ".pt")
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(checkpoint, target)
        shutil.copy2(args.existing, output / "initial" / "existing_yolo11.pt")
        protocol = dict(created_at=datetime.now(timezone.utc).isoformat(),
                        status="prepared", settings=vars(args).copy(), training_recipe=training_options(args),
                        dataset_sha256=audit["sha256"], counts=audit["counts"],
                        initial_sha256={p.name: sha256(p) for p in (output/"initial").glob("*.pt")},
                        environment=dict(python=platform.python_version(), torch=torch.__version__,
                                         ultralytics=ultralytics.__version__, platform=platform.platform(),
                                         cuda_available=torch.cuda.is_available(), cpu_count=os.cpu_count()),
                        checkpoint_selection="Highest validation mAP50-95; no test-based tuning",
                        comparison_scope="Single-class detection using the frozen dataset label mapping; not material classification",
                        test_history=audit["test_history"],
                        seed_limitation="One seed; report observed differences, not statistical significance")
        protocol["settings"] = {k: str(v) if isinstance(v, Path) else v for k, v in protocol["settings"].items()}
        write_json(protocol_path, protocol)
    else:
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        # Separate stages always replay the frozen recipe, not CLI defaults.
        for key in ("epochs", "imgsz", "batch", "threads", "seed", "device", "conf"):
            setattr(args, key, protocol["settings"][key])
        verify_snapshot(output / "dataset", protocol["dataset_sha256"])
    if args.stage == "prepare":
        print(f"Prepared: {protocol_path}")
        return
    import torch
    from ultralytics import YOLO
    torch.set_num_threads(args.threads)
    if args.stage in ("all", "train"):
        protocol["status"] = "training"
        protocol["training_pid"] = os.getpid()
        write_json(protocol_path, protocol)
        names = ("yolo11n", "yolov8n") if args.model == "both" else (("yolo11n",) if args.model == "yolo11" else ("yolov8n",))
        for name in names:
            if (output / name).exists() and not args.resume_run:
                raise FileExistsError(f"Do not overwrite previous run: {output / name}")
            initial = output / "initial" / (name + ".pt")
            if sha256(initial) != protocol["initial_sha256"][initial.name]:
                raise ValueError("Initial checkpoint changed")
            prior_epochs, prior_seconds = 0, 0
            model = YOLO(str(output / name / "weights/last.pt" if args.resume_run else initial))
            if args.resume_run:
                with (output / name / "results.csv").open(encoding="utf-8-sig", newline="") as stream:
                    history = list(csv.DictReader(stream))
                prior_epochs = verify_resume_state(model.ckpt, history, protocol["training_recipe"])
                prior_seconds = float(history[-1]["time"])
                evidence = output / ("resume_evidence_" + name + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
                evidence.mkdir()
                for filename in ("results.csv", "args.yaml"):
                    shutil.copy2(output / name / filename, evidence / filename)
                shutil.copy2(output / name / "weights/last.pt", evidence / "last.pt")
                interruptions_path = output / "execution_interruptions.json"
                interruptions = json.loads(interruptions_path.read_text(encoding="utf-8-sig")) if interruptions_path.exists() else dict(interrupted_models=[], events=[])
                if name not in interruptions["interrupted_models"]:
                    interruptions["interrupted_models"].append(name)
                interruptions["events"].append(dict(type="checkpoint_resume", model=name,
                    recorded_at=datetime.now(timezone.utc).isoformat(), completed_epochs=prior_epochs,
                    checkpoint_sha256=sha256(evidence / "last.pt"), evidence=str(evidence),
                    scope="Process stopped without a traceback. Resume original optimizer and recipe; repeat the incomplete epoch. RNG continuation is not guaranteed bitwise equivalent to an uninterrupted run."))
                write_json(interruptions_path, interruptions)
            def training_started(trainer):
                torch.set_num_threads(args.threads)
                write_json(output / "progress.json", dict(status="training", model=name,
                           epoch=prior_epochs, epochs=args.epochs, elapsed_seconds=prior_seconds))
            model.add_callback("on_train_start", training_started)
            model.add_callback("on_val_start", lambda validator: torch.set_num_threads(args.threads))
            started = time.monotonic()
            def progress(trainer):
                write_json(output / "progress.json", dict(status="training", model=name,
                           epoch=min(trainer.epoch+1, args.epochs), epochs=args.epochs,
                           elapsed_seconds=prior_seconds+time.monotonic()-started,
                           metrics={k: float(v) for k, v in trainer.metrics.items()}))
            model.add_callback("on_fit_epoch_end", progress)
            print(f"TRAIN {name}: {args.epochs} epochs, imgsz={args.imgsz}", flush=True)
            recipe = dict(protocol["training_recipe"], resume=args.resume_run)
            model.train(data=str(output / "dataset" / "data.yaml"),
                        project=str(output), name=name, **recipe)
            protocol.setdefault("training_seconds", {})[name] = prior_seconds+time.monotonic()-started
            write_json(protocol_path, protocol)
        protocol["status"] = "trained" if all((output/n/"weights/best.pt").is_file() for n in ("yolo11n", "yolov8n")) else "partially_trained"
        write_json(protocol_path, protocol)
    if args.stage == "train":
        return
    import psutil
    import ultralytics
    protocol["evaluation_environment"] = dict(
        python=platform.python_version(), torch=torch.__version__,
        ultralytics=ultralytics.__version__, processor=platform.processor(),
        cpu_count=os.cpu_count(), physical_cores=psutil.cpu_count(logical=False),
        memory_bytes=psutil.virtual_memory().total, device=args.device,
        torch_threads=args.threads)
    # Verify all training/data artifacts before ever opening the test split.
    verify_snapshot(output / "dataset", protocol["dataset_sha256"])
    checkpoints = [(name, output/name/"weights/best.pt", "controlled") for name in ("yolo11n", "yolov8n")]
    checkpoints.append(("existing_yolo11", output/"initial/existing_yolo11.pt", "historical_reference"))
    completed = {name: verify_completed_run(output/name, args.epochs) for name in ("yolo11n", "yolov8n")}
    for filename, expected_hash in protocol["initial_sha256"].items():
        if sha256(output/"initial"/filename) != expected_hash:
            raise ValueError(f"Frozen initial/reference checkpoint changed: {filename}")
    for _, checkpoint, _ in checkpoints:
        if not checkpoint.is_file():
            raise FileNotFoundError(checkpoint)
    rows = []
    for name, checkpoint, role in checkpoints:
        rows.append(evaluate(checkpoint, name, role, args, output))
        if rows[-1]["fixed_confidence"]["objects"] != protocol["counts"]["test"]["objects"]:
            raise ValueError("Evaluator ground-truth object count differs from the audited test snapshot")
        write_json(output / "evaluation_partial.json", rows)
    report = dict(protocol=str(protocol_path), dataset_sha256=protocol["dataset_sha256"],
                  settings={k: protocol["settings"][k] for k in ("imgsz", "epochs", "batch", "threads", "seed", "conf", "device")},
                  counts=protocol["counts"], training_completion=completed, environment=protocol["evaluation_environment"],
                  results=rows, conclusion=select_winner(rows))
    interruptions = output / "execution_interruptions.json"
    if interruptions.is_file():
        report["execution_interruptions"] = json.loads(interruptions.read_text(encoding="utf-8-sig"))
        protocol["execution_interruptions"] = report["execution_interruptions"]
    write_json(output / "comparison.json", report)
    export_results(output, rows)
    protocol["status"] = "complete"
    write_json(protocol_path, protocol)
    write_json(output / "progress.json", dict(status="complete", report=str(output/"comparison.json")))
    print(json.dumps(report["conclusion"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
