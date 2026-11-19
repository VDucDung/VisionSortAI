"""Matched Original/CBAM/EIoU/Improved YOLO11n experiments on three frozen datasets."""
import argparse
import csv
import ctypes
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from trashsmart.yolo_training.benchmark import (
    evaluate, sha256, training_options, verify_completed_run, verify_resume_state, verify_snapshot, write_json,
)


DATASETS = ("haui", "taco", "uavvaste")
FACTORS = dict(original=dict(cbam=False, eiou=False), cbam=dict(cbam=True, eiou=False),
               eiou=dict(cbam=False, eiou=True), improved=dict(cbam=True, eiou=True))
METRICS = ("precision", "recall", "f1", "map50", "map50_95")


def prepare(root, source):
    if root.exists():
        raise FileExistsError("Choose a new study directory; existing plans are not overwritten")
    import torch
    import ultralytics
    plan = dict(created_utc=datetime.now(timezone.utc).isoformat(), datasets=list(DATASETS), variants=FACTORS,
                epochs=30, imgsz=640, batch=8, threads=4, device="cpu", seed=42, recipe="accuracy",
                original_definition="Unmodified YOLO11n architecture and CIoU regression, trained on the target dataset; not zero-shot COCO inference.",
                improved_definition="Same YOLO11n plus paper CBAM at neck outputs P3/P4/P5 and EIoU regression (equation 7); DFL, classification and assignment unchanged.",
                comparison="Four new runs per dataset from the same original COCO checkpoint and same original detector tensors. No historical run substitutes for a new baseline.",
                checkpoint_selection="Highest validation mAP50-95 within the same 30 epochs",
                evaluation=dict(confidence=.25, matching_iou=.5, nms_iou=.7, ap_confidence=.001, tta=False),
                limits="One seed. All three test splits have appeared in the earlier architecture comparison. No claim of a fresh holdout, global optimum, guaranteed improvement, or new invention of CBAM/EIoU.",
                sources=[dict(method="CBAM", url="https://www.ecva.net/papers/eccv_2018/papers_ECCV/html/Sanghyun_Woo_Convolutional_Block_Attention_ECCV_2018_paper.php", doi="10.1007/978-3-030-01234-2_1", use="Channel then spatial attention, equations 2-3, reduction 16 and kernel 7"),
                         dict(method="EIoU", url="https://arxiv.org/abs/2101.08158", doi="10.1016/j.neucom.2022.07.042", use="Equation 7 only; not Focal-EIoU"),
                         dict(method="Related waste-detection application", url="https://doi.org/10.1109/ICITRI67507.2025.11232874", use="Related-work context from publisher abstract; not an exact replication of inaccessible full text")],
                environment=dict(python=platform.python_version(), torch=torch.__version__, ultralytics=ultralytics.__version__))
    recipe = training_options(SimpleNamespace(**plan))
    root.mkdir(parents=True)
    initial = root / "initial/yolo11n.pt"
    initial.parent.mkdir()
    shutil.copy2(Path("yolo11n.pt"), initial)
    from ultralytics import YOLO
    model = YOLO(str(initial))
    if len(model.names) != 80 or "yolo11n" not in str(model.model.yaml["yaml_file"]):
        raise ValueError("Require original YOLO11n COCO pretrained checkpoint")
    plan["initial_sha256"] = sha256(initial)
    plan["training_recipe"] = recipe
    plan["implementation_sha256"] = {name: sha256(Path(__file__).with_name(name))
                                      for name in ("improvements.py", "ablation.py")}
    for dataset in DATASETS:
        source_experiment = source / dataset
        original_protocol = json.loads((source_experiment / "protocol.json").read_text(encoding="utf-8"))
        verify_snapshot(source_experiment / "dataset", original_protocol["dataset_sha256"])
        destination = root / dataset
        destination.mkdir()
        from trashsmart.yolo_training.prepare_detection import prepare as copy_snapshot
        copy_snapshot(source_experiment / "dataset", destination / "dataset")
        verify_snapshot(destination / "dataset", original_protocol["dataset_sha256"])
        shutil.copy2(source_experiment / "data_audit.json", destination / "data_audit.json")
        if (source_experiment / "source.json").exists():
            shutil.copy2(source_experiment / "source.json", destination / "source.json")
        write_json(destination / "protocol.json", dict(
            status="prepared", settings={key: plan[key] for key in ("epochs", "imgsz", "batch", "threads", "seed", "device", "recipe")},
            dataset_sha256=original_protocol["dataset_sha256"], counts=original_protocol["counts"],
            test_history=plan["limits"], training_recipe=recipe,
        ))
    selection = json.loads((source / "sample_selection.json").read_text(encoding="utf-8"))
    for dataset, sample in selection["datasets"].items():
        for key, split in (("image", "images"), ("label", "labels")):
            sample[key] = str(root / dataset / "dataset/test" / split / Path(sample[key]).name)
        if sha256(sample["image"]) != sample["image_sha256"] or sha256(sample["label"]) != sample["label_sha256"]:
            raise ValueError("Preselected sample changed")
    selection["policy"] = "Preserve the predeclared examples from the earlier study; no selection based on new variant predictions."
    write_json(root / "sample_selection.json", selection)
    write_json(root / "study_plan.json", plan)
    print(f"Prepared: {root}", flush=True)


def train(root, dataset, variant, resume=False):
    import torch
    from ultralytics import YOLO
    from trashsmart.yolo_training.improvements import TRAINERS
    plan = json.loads((root / "study_plan.json").read_text(encoding="utf-8"))
    experiment = root / dataset
    protocol = json.loads((experiment / "protocol.json").read_text(encoding="utf-8"))
    verify_snapshot(experiment / "dataset", protocol["dataset_sha256"])
    initial = root / "initial/yolo11n.pt"
    if sha256(initial) != plan["initial_sha256"]:
        raise ValueError("Initial checkpoint changed")
    directory = experiment / variant
    if directory.exists() and not resume:
        raise FileExistsError(directory)
    model = YOLO(str(directory / "weights/last.pt" if resume else initial))
    prior = 0
    if resume:
        history = list(csv.DictReader((directory / "results.csv").open(encoding="utf-8-sig")))
        prior = verify_resume_state(model.ckpt, history, plan["training_recipe"])
        evidence = experiment / ("resume_" + variant + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        evidence.mkdir()
        shutil.copy2(directory / "weights/last.pt", evidence / "last.pt")
        shutil.copy2(directory / "results.csv", evidence / "results.csv")
        write_json(evidence / "event.json", dict(completed_epochs=prior, checkpoint_sha256=sha256(evidence / "last.pt"),
            limitation="Optimizer and recipe restored; interrupted epoch repeated; RNG continuity with an uninterrupted run is not guaranteed."))
    def started(trainer):
        torch.set_num_threads(plan["threads"])
        if getattr(trainer.model, "ablation_factors", None) != FACTORS[variant]:
            raise ValueError("Checkpoint/model improvement factors differ from the assigned variant")
        initialization = json.loads((directory / "initialization.json").read_text())
        original = experiment / "original/initialization.json"
        if original.exists() and initialization["common_initial_sha256"] != json.loads(original.read_text())["common_initial_sha256"]:
            raise ValueError("Original detector tensor initialization differs between ablations")
        write_json(experiment / "progress.json", dict(status="training", variant=variant, epoch=prior, epochs=plan["epochs"]))
    def progress(trainer):
        write_json(experiment / "progress.json", dict(status="training", variant=variant,
            epoch=min(trainer.epoch + 1, plan["epochs"]), epochs=plan["epochs"],
            metrics={key: float(value) for key, value in trainer.metrics.items()}))
    model.add_callback("on_train_start", started)
    model.add_callback("on_val_start", lambda validator: torch.set_num_threads(plan["threads"]))
    model.add_callback("on_fit_epoch_end", progress)
    started_at = time.monotonic()
    model.train(trainer=TRAINERS[variant], data=str(experiment / "dataset/data.yaml"),
                project=str(experiment), name=variant, **dict(plan["training_recipe"], resume=resume))
    completion = verify_completed_run(directory, plan["epochs"])
    write_json(directory / "completion.json", dict(**completion, resumed=resume,
        current_session_seconds=time.monotonic() - started_at, checkpoint_sha256=sha256(directory / "weights/best.pt")))


def verify_all_runs(root, plan):
    for dataset in DATASETS:
        protocol = json.loads((root / dataset / "protocol.json").read_text())
        verify_snapshot(root / dataset / "dataset", protocol["dataset_sha256"])
        initializations = []
        for variant in FACTORS:
            run = root / dataset / variant
            verify_completed_run(run, plan["epochs"])
            initialization = json.loads((run / "initialization.json").read_text())
            if initialization["factors"] != FACTORS[variant]:
                raise ValueError("Wrong ablation factors")
            initializations.append(initialization["common_initial_sha256"])
            completion = json.loads((run / "completion.json").read_text())
            if completion["checkpoint_sha256"] != sha256(run / "weights/best.pt"):
                raise ValueError("Completed checkpoint changed")
        if len(set(initializations)) != 1:
            raise ValueError("Unequal original initial tensors")


def evaluate_variant(root, dataset, variant):
    plan = json.loads((root / "study_plan.json").read_text())
    # Test is opened only after all twelve training runs have passed verification.
    verify_all_runs(root, plan)
    experiment = root / dataset
    settings = SimpleNamespace(**{key: plan[key] for key in ("threads", "imgsz", "batch", "device")}, conf=.25)
    checkpoint = experiment / variant / "weights/best.pt"
    result = evaluate(checkpoint, variant, "same_architecture_ablation", settings, experiment)
    protocol = json.loads((experiment / "protocol.json").read_text())
    if result["fixed_confidence"]["objects"] != protocol["counts"]["test"]["objects"]:
        raise ValueError("Test ground truth count differs from the frozen protocol")
    result.update(dataset=dataset, variant=variant, factors=FACTORS[variant])
    import psutil
    battery = psutil.sensors_battery()
    frequency = psutil.cpu_freq()
    result["evaluation_environment"] = dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
        device=plan["device"], torch_threads=plan["threads"],
        cpu_frequency_mhz=frequency.current if frequency else None,
        power_plugged=battery.power_plugged if battery else None,
        battery_percent=battery.percent if battery else None,
        memory_percent=psutil.virtual_memory().percent, software=plan["environment"])
    target = experiment / variant / "test_results.json"
    if target.exists():
        target = experiment / "rechecks" / (variant + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    write_json(target, result)
    print(variant + ": " + "; ".join(f"{key}={100 * (result[key] if key.startswith('map') else result['fixed_confidence'][key]):.4f}%" for key in METRICS), flush=True)
    print(f"Saved: {target}", flush=True)


def collect(root):
    plan = json.loads((root / "study_plan.json").read_text())
    verify_all_runs(root, plan)
    rows, differences = [], []
    for dataset in DATASETS:
        for variant, factors in FACTORS.items():
            run = root / dataset / variant
            result = json.loads((run / "test_results.json").read_text())
            if result["checkpoint_sha256"] != sha256(run / "weights/best.pt"):
                raise ValueError("Evaluation checkpoint changed")
            point = result["fixed_confidence"]
            rows.append(dict(dataset=dataset, variant=variant, cbam=factors["cbam"], eiou=factors["eiou"], pretrained=True,
                **{key: point[key] for key in ("precision", "recall", "f1")},
                **{key: result[key] for key in ("map50", "map50_95", "parameters", "checkpoint_mb", "checkpoint_sha256")},
                true_positives=point["true_positives"], false_positives=point["predictions"] - point["true_positives"],
                false_negatives=point["objects"] - point["true_positives"], inference_ms=result["speed_ms_per_image"]["inference"]))
        models = {row["variant"]: row for row in rows if row["dataset"] == dataset}
        differences.append(dict(dataset=dataset,
            difference_percentage_points={key: 100 * (models["improved"][key] - models["original"][key]) for key in METRICS},
            improved_higher_on_all_five=all(models["improved"][key] > models["original"][key] for key in METRICS)))
    interruptions = {}
    for dataset in DATASETS:
        for variant in FACTORS:
            path = root / dataset / variant / "execution_interruptions.json"
            if path.exists():
                interruptions[dataset + "/" + variant] = json.loads(path.read_text(encoding="utf-8"))
    report = dict(study_plan=plan, results=rows, original_vs_improved=differences,
                  execution_interruptions=interruptions)
    write_json(root / "comparison_original_improved.json", report)
    with (root / "comparison_original_improved.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return report


def run(root):
    state_path = root / "study_status.json"
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    def command(stage, dataset, variant, extra=()):
        write_json(state_path, dict(status="running", pid=os.getpid(), stage=stage, dataset=dataset, variant=variant))
        with (root / f"{dataset}-{variant}-{stage}.log").open("a", encoding="utf-8") as stream:
            subprocess.run([sys.executable, "-X", "utf8", "-u", "-m", "trashsmart.yolo_training.ablation",
                "--root", str(root), "--stage", stage, "--dataset", dataset, "--variant", variant, *extra],
                stdout=stream, stderr=subprocess.STDOUT, check=True)
    try:
        plan = json.loads((root / "study_plan.json").read_text())
        for dataset in DATASETS:
            for variant in FACTORS:
                directory = root / dataset / variant
                if (directory / "completion.json").exists():
                    verify_completed_run(directory, plan["epochs"])
                    continue
                command("train", dataset, variant)
        verify_all_runs(root, plan)
        for dataset in DATASETS:
            for variant in FACTORS:
                if not (root / dataset / variant / "test_results.json").exists():
                    command("evaluate", dataset, variant)
        collect(root)
        write_json(state_path, dict(status="complete", pid=os.getpid(), stage="measured_results_complete"))
    except Exception as error:
        write_json(state_path, dict(status="failed", pid=os.getpid(), stage="failed", error=str(error)))
        raise
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("outputs/yolo11-original-improved-20261116"))
    parser.add_argument("--source-root", type=Path, default=Path("outputs/yolo-three-datasets-20261115"))
    parser.add_argument("--stage", choices=("prepare", "run", "train", "evaluate", "collect", "predict"), default="run")
    parser.add_argument("--dataset", choices=DATASETS, default="haui")
    parser.add_argument("--variant", choices=FACTORS, default="improved")
    parser.add_argument("--resume-run", action="store_true")
    parser.add_argument("--image", type=Path, help="For predict: omit to select an image interactively")
    parser.add_argument("--output", type=Path, help="For predict: output image directory")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.stage == "prepare": prepare(root, args.source_root.resolve())
    elif args.stage == "train": train(root, args.dataset, args.variant, args.resume_run)
    elif args.stage == "evaluate": evaluate_variant(root, args.dataset, args.variant)
    elif args.stage == "collect": collect(root)
    elif args.stage == "predict":
        display = {"original": "YOLO11n Original", "cbam": "YOLO11n + CBAM", "eiou": "YOLO11n + EIoU", "improved": "YOLO11n Improved"}[args.variant]
        command = [sys.executable, "-m", "trashsmart.yolo_training.predict_compare", "--experiment", str(root / args.dataset),
                   "--weights", str(root / args.dataset / args.variant / "weights/best.pt"), "--model", "yolo11",
                   "--display-name", display, "--output", str(args.output or root / args.dataset / "manual_predictions" / args.variant)]
        if args.image: command.extend(["--image", str(args.image)])
        if args.show: command.append("--show")
        subprocess.run(command, check=True)
    else: run(root)


if __name__ == "__main__":
    main()
