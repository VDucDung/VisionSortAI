"""Wait for all measured experiments, then build plots, examples and reviewed-document inputs."""

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_status(path, stage, **details):
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(dict(pid=os.getpid(), stage=stage, **details), indent=2), encoding="utf-8")
    pending.replace(path)


def run(command, cwd, log, env=None):
    with log.open("a", encoding="utf-8") as stream:
        subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)


def comparison_chart(report, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    datasets = ["haui", "taco", "uavvaste"]
    names = ["HAUI", "TACO v0.2", "UAVVaste"]
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for axis, metric, title in zip(axes, ["map50_95", "f1"], ["Test mAP50-95", "Test F1 at confidence 0.25"]):
        for index, (model, color) in enumerate([("yolo11n", "#28608F"), ("yolov8n", "#C77328")]):
            values = [100 * next(row[metric] for row in report["results"]
                                 if row["dataset"] == dataset and row["model"] == model)
                      for dataset in datasets]
            positions = [position + (index - .5) * .36 for position in range(3)]
            bars = axis.bar(positions, values, width=.34, label="YOLO11n" if index == 0 else "YOLOv8n", color=color)
            axis.bar_label(bars, fmt="%.2f", fontsize=9, padding=3)
        axis.set(xticks=range(3), xticklabels=names, ylabel="%", title=title, ylim=(0, 105))
        axis.set_yticks(range(0, 101, 20))
        axis.grid(axis="y", alpha=.2)
        axis.set_axisbelow(True)
        axis.legend()
    figure.savefig(output, dpi=180)
    plt.close(figure)


def predict_examples(root, model_root, report):
    selection = json.loads((root / "sample_selection.json").read_text(encoding="utf-8"))
    for dataset in ["haui", "taco", "uavvaste"]:
        sample = selection["datasets"][dataset]
        if file_hash(Path(sample["image"])) != sample["image_sha256"]:
            raise ValueError("Preselected image changed")
        target = root / dataset / "sample_prediction"
        prediction_path = target / "predictions.json"
        if not prediction_path.is_file():
            process = subprocess.run([
                sys.executable, "-X", "utf8", "-u", "-m", "trashsmart.yolo_training.predict_compare",
                "--experiment", str(root / dataset), "--model", "both", "--image", sample["image"],
                "--conf", ".25", "--iou", ".7", "--output", str(target),
            ], cwd=model_root, capture_output=True, encoding="utf-8", check=True)
            actual = Path(process.stdout.rsplit("Saved: ", 1)[1].strip()).resolve()
            if not actual.is_relative_to(root):
                raise ValueError("Unexpected prediction output directory")
            if actual != target:
                target.mkdir(exist_ok=True)
                for filename in ["yolo11.jpg", "yolov8.jpg", "side_by_side.jpg", "predictions.json"]:
                    shutil.copy2(actual / filename, target / filename)
        prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
        expected = {row["model"]: row["checkpoint_sha256"] for row in report["results"]
                    if row["dataset"] == dataset}
        if prediction["image_sha256"] != sample["image_sha256"]:
            raise ValueError("Demo image differs from the preselected image")
        for model in prediction["models"]:
            name = {"yolo11": "yolo11n", "yolov8": "yolov8n"}[model["name"]]
            if model["weights_sha256"] != expected[name]:
                raise ValueError("Demo weights differ from the evaluated weights")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=Path("outputs/yolo-three-datasets-20261115"))
    args = parser.parse_args()
    root = args.study.resolve()
    model_root = root.parents[1]
    state_path = root / "finish_status.json"
    log = root / "finish_pipeline.log"
    document_python = Path("C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
    old_qa = model_root / "outputs/yolo11-vs-yolov8-doc-qa"
    office = model_root / ".tools/libreoffice-render/program/soffice.exe"
    office_python = office.with_name("python.exe")
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        write_status(state_path, "waiting_for_six_completed_training_runs")
        while True:
            study = json.loads((root / "study_status.json").read_text(encoding="utf-8"))
            if study["status"] == "failed":
                raise RuntimeError(f"Training controller failed: {study}")
            if study["status"] == "complete":
                break
            time.sleep(10)
        write_status(state_path, "verifying_results_and_building_figures")
        run([sys.executable, "-m", "trashsmart.yolo_training.multidata", "--root", str(root), "--collect-only"],
            model_root, log)
        report = json.loads((root / "comparison_three_datasets.json").read_text(encoding="utf-8"))
        comparison_chart(report, root / "comparison_three_datasets.png")
        predict_examples(root, model_root, report)
        write_status(state_path, "updating_chapter_three")
        source = model_root / "outputs/yolo11-vs-yolov8/documents/De_an_Vu_Duc_Dung_cap_nhat_chuong_3.docx"
        documents = root / "documents"
        run([str(document_python), "-X", "utf8", "scripts/update_multidata_chapter.py",
             "--source", str(source), "--study", str(root), "--output", str(documents)], model_root, log)
        qa = root / "document_qa"
        qa.mkdir(exist_ok=True)
        env = os.environ.copy()
        poppler = "C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin"
        env["PATH"] = str(office.parent) + os.pathsep + poppler + os.pathsep + env.get("PATH", "")
        for document in sorted(documents.glob("*.docx")):
            write_status(state_path, "refreshing_fields_and_rendering", document=str(document))
            run([str(office_python), str(old_qa / "refresh_fields.py"), str(document),
                 "--office", str(office), "--profile", str(qa / ("fields-" + document.stem))], model_root, log)
            run([str(document_python), "-X", "utf8", str(old_qa / "render_docx.py"), str(document),
                 "--output_dir", str(qa / document.stem), "--emit_pdf", "--dpi", "120"], model_root, log, env)
        write_status(state_path, "ready_for_visual_review", documents=[str(path) for path in documents.glob("*.docx")])
    except Exception as error:
        write_status(state_path, "failed", error=str(error))
        raise
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    main()
