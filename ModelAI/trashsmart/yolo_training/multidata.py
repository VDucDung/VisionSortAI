"""Run matched YOLO11n/YOLOv8n experiments on HAUI, TACO and UAVVaste."""

import argparse
import csv
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from trashsmart.yolo_training.benchmark import sha256, verify_completed_run, verify_snapshot, write_json


QUALITY_METRICS = ("precision", "recall", "f1", "map50", "map50_95")


def comparison_rows(dataset, report):
    models = {row["name"]: row for row in report["results"] if row["role"] == "controlled"}
    if set(models) != {"yolo11n", "yolov8n"}:
        raise ValueError("Each dataset requires both controlled architectures")
    rows = []
    for name, model in models.items():
        point = model["fixed_confidence"]
        rows.append(dict(
            dataset=dataset, model=name,
            precision=point["precision"], recall=point["recall"], f1=point["f1"],
            map50=model["map50"], map50_95=model["map50_95"],
            true_positives=point["true_positives"],
            false_positives=point["predictions"] - point["true_positives"],
            false_negatives=point["objects"] - point["true_positives"],
            parameters=model["parameters"], checkpoint_mb=model["checkpoint_mb"],
            inference_ms=model["speed_ms_per_image"]["inference"],
            checkpoint=model["checkpoint"], checkpoint_sha256=model["checkpoint_sha256"],
        ))
    return rows


def summarize(rows):
    summaries = []
    for dataset in ("haui", "taco", "uavvaste"):
        models = {row["model"]: row for row in rows if row["dataset"] == dataset}
        if set(models) != {"yolo11n", "yolov8n"}:
            continue
        differences = {}
        for metric in QUALITY_METRICS:
            value = models["yolo11n"][metric]
            baseline = models["yolov8n"][metric]
            differences[metric] = dict(
                yolo11n=value, yolov8n=baseline,
                difference_percentage_points=100 * (value - baseline),
                relative_change_percent=100 * (value / baseline - 1) if baseline else None,
                yolo11n_higher=value > baseline,
            )
        summaries.append(dict(
            dataset=dataset, metrics=differences,
            yolo11n_higher_on_all_five=all(item["yolo11n_higher"] for item in differences.values()),
        ))
    return summaries


def collect_results(root, plan):
    if set(plan["datasets"]) != {"haui", "taco", "uavvaste"} or len(plan["datasets"]) != 3:
        raise ValueError("The comparison requires all three distinct source datasets")
    rows = []
    datasets = {}
    for dataset in plan["datasets"]:
        experiment = root / dataset
        protocol = json.loads((experiment / "protocol.json").read_text(encoding="utf-8"))
        if protocol["status"] != "complete":
            raise ValueError(f"Incomplete experiment: {dataset}")
        for setting in ("epochs", "imgsz", "batch", "threads", "seed", "device", "recipe"):
            if protocol["settings"][setting] != plan[setting]:
                raise ValueError(f"Experiment settings differ from the study plan: {dataset}: {setting}")
        verify_snapshot(experiment / "dataset", protocol["dataset_sha256"])
        report = json.loads((experiment / "comparison.json").read_text(encoding="utf-8"))
        if report["dataset_sha256"] != protocol["dataset_sha256"]:
            raise ValueError("Reported dataset differs from the frozen protocol")
        for name in ("yolo11n", "yolov8n"):
            verify_completed_run(experiment / name, plan["epochs"])
        for row in comparison_rows(dataset, report):
            if sha256(row["checkpoint"]) != row["checkpoint_sha256"]:
                raise ValueError("Evaluated checkpoint changed")
            rows.append(row)
        datasets[dataset] = dict(counts=report["counts"], dataset_sha256=report["dataset_sha256"],
                                 recipe=protocol["training_recipe"], environment=report["environment"],
                                 execution_interruptions=report.get("execution_interruptions"))
    output = dict(study_plan=plan, datasets=datasets, results=rows, comparison=summarize(rows))
    write_json(root / "comparison_three_datasets.json", output)
    with (root / "comparison_three_datasets.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output


def command(root, dataset, arguments):
    log_path = root / (dataset + "-pipeline.log")
    with log_path.open("a", encoding="utf-8") as log:
        subprocess.run(
            [sys.executable, "-u", "-m", "trashsmart.yolo_training.benchmark", *arguments],
            stdout=log, stderr=subprocess.STDOUT, check=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("outputs/yolo-three-datasets-20261115"))
    parser.add_argument("--wait-haui", action="store_true", help="Wait for the separately started HAUI run")
    parser.add_argument("--collect-only", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    plan = json.loads((root / "study_plan.json").read_text(encoding="utf-8"))
    state = dict(status="running", pid=os.getpid(), dataset=None, stage=None)
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

    def status(dataset, stage):
        state.update(dataset=dataset, stage=stage)
        write_json(root / "study_status.json", state)
        print(f"{dataset}: {stage}", flush=True)

    try:
        if not args.collect_only:
            for dataset in plan["datasets"]:
                experiment = root / dataset
                protocol_path = experiment / "protocol.json"
                if dataset == "haui" and args.wait_haui:
                    status(dataset, "waiting_for_active_training")
                    while not protocol_path.is_file() or json.loads(protocol_path.read_text())["status"] != "complete":
                        time.sleep(10)
                    continue
                source = root / "datasets" / dataset
                if not protocol_path.is_file():
                    status(dataset, "waiting_for_prepared_data")
                    while not (source / "data_audit.json").is_file():
                        time.sleep(10)
                    audit = json.loads((source / "data_audit.json").read_text())
                    if audit["exact_pixel_cross_split"]:
                        raise ValueError(f"Exact duplicate leakage in {dataset}")
                    verify_snapshot(source, audit["sha256"])
                    status(dataset, "preparing_experiment")
                    command(root, dataset, [
                        "--source", str(source), "--output", str(experiment),
                        "--epochs", str(plan["epochs"]), "--imgsz", str(plan["imgsz"]),
                        "--batch", str(plan["batch"]), "--threads", str(plan["threads"]),
                        "--seed", str(plan["seed"]), "--device", plan["device"],
                        "--recipe", plan["recipe"], "--stage", "prepare",
                    ])
                protocol = json.loads(protocol_path.read_text())
                if protocol["status"] == "complete":
                    continue
                for model, name in (("yolo11", "yolo11n"), ("yolov8", "yolov8n")):
                    if (experiment / name).exists():
                        verify_completed_run(experiment / name, plan["epochs"])
                        continue
                    status(dataset, "training_" + name)
                    command(root, dataset, ["--output", str(experiment), "--stage", "train", "--model", model])
                status(dataset, "evaluating_frozen_checkpoints")
                command(root, dataset, ["--output", str(experiment), "--stage", "evaluate"])
        status("all", "verifying_and_collecting")
        collect_results(root, plan)
        state.update(status="complete", stage="complete")
        write_json(root / "study_status.json", state)
        print(f"Saved: {root / 'comparison_three_datasets.json'}", flush=True)
    except Exception as error:
        state.update(status="failed", error=str(error))
        write_json(root / "study_status.json", state)
        raise
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    main()
