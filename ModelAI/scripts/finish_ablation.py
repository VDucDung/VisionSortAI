"""Build genuine ablation plots and Word inputs after all measured results are complete."""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from trashsmart.yolo_training.benchmark import sha256, write_json


DATASETS = ("haui", "taco", "uavvaste")
VARIANTS = ("original", "cbam", "eiou", "improved")


def figures(root, report):
    import csv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    folder = root / "figures"
    folder.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    for axis, metric, title in zip(axes, ("map50_95", "f1"), ("Test mAP50-95", "Test F1 at confidence 0.25")):
        for index, variant in enumerate(("original", "improved")):
            values = [next(r[metric] * 100 for r in report["results"] if r["dataset"] == d and r["variant"] == variant) for d in DATASETS]
            bars = axis.bar([n + (index - .5) * .36 for n in range(3)], values, width=.34,
                            label=variant.title(), color=("#7A8793", "#22638E")[index])
            axis.bar_label(bars, fmt="%.2f", fontsize=9, padding=3)
        axis.set(xticks=range(3), xticklabels=("HAUI", "TACO v0.2", "UAVVaste"), ylim=(0, 105), ylabel="%", title=title)
        axis.grid(axis="y", alpha=.2); axis.set_axisbelow(True); axis.legend()
    fig.savefig(folder / "quality.png", dpi=180); plt.close(fig)
    fig, axes = plt.subplots(3, 2, figsize=(11, 10), layout="constrained")
    for i, dataset in enumerate(DATASETS):
        for variant, color in zip(VARIANTS, ("#666666", "#D78425", "#239A82", "#22638E")):
            history = list(csv.DictReader((root / dataset / variant / "results.csv").open(encoding="utf-8-sig")))
            epochs = [int(row["epoch"]) for row in history]
            axes[i, 0].plot(epochs, [100 * float(row["metrics/mAP50-95(B)"]) for row in history], color=color, label=variant)
            axes[i, 1].plot(epochs, [float(row["train/box_loss"]) for row in history], color=color, label=variant)
        for j in range(2):
            axes[i, j].set(title=dataset.upper() + (" validation mAP50-95" if j == 0 else " training box loss"), xlabel="Epoch")
            axes[i, j].grid(alpha=.2); axes[i, j].legend(fontsize=8)
    fig.savefig(folder / "training.png", dpi=180); plt.close(fig)
    architecture_figure(folder)


def architecture_figure(folder):
    """Render the factual method diagram without requiring any accuracy measurements."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    fig, axis = plt.subplots(figsize=(11, 4.8))
    axis.set(xlim=(0, 11), ylim=(0, 4.8)); axis.axis("off")
    for y, title, boxes in [(3.3, "YOLO11n Original", ["Input", "Backbone", "Neck P3/P4/P5", "Detect"]),
                             (1.3, "YOLO11n Improved", ["Input", "Backbone", "Neck + 3 CBAM", "Detect"])]:
        axis.text(.2, y + .9, title, fontsize=13, weight="bold")
        for i, label in enumerate(boxes):
            x = .2 + i * 2.7
            axis.add_patch(FancyBboxPatch((x, y), 2.3, .65, boxstyle="round,pad=.06", facecolor="#EAF0F5", edgecolor="#526477"))
            axis.text(x + 1.15, y + .325, label, ha="center", va="center", fontsize=11)
            if i < 3: axis.annotate("", xy=(x + 2.65, y + .325), xytext=(x + 2.35, y + .325), arrowprops=dict(arrowstyle="->"))
        axis.text(.3, y - .4, "Training regression: " + ("CIoU + unchanged DFL" if y > 2 else "EIoU + unchanged DFL"), fontsize=11)
    axis.text(.2, .1, "Same COCO initialization, target data, seed and training budget; loss replacement affects training.", fontsize=10)
    fig.savefig(folder / "architecture.png", dpi=180, bbox_inches="tight"); plt.close(fig)


def examples(root, model_root, report):
    from PIL import Image
    selection = json.loads((root / "sample_selection.json").read_text())
    for dataset in DATASETS:
        sample = selection["datasets"][dataset]
        if sha256(sample["image"]) != sample["image_sha256"]:
            raise ValueError("Predeclared sample changed")
        panels = []
        for variant in ("original", "improved"):
            destination = root / dataset / "sample_prediction" / variant
            if not (destination / "predictions.json").exists():
                process = subprocess.run([sys.executable, "-X", "utf8", "-m", "trashsmart.yolo_training.ablation",
                    "--root", str(root), "--stage", "predict", "--dataset", dataset, "--variant", variant,
                    "--image", sample["image"], "--output", str(destination)], cwd=model_root,
                    capture_output=True, encoding="utf-8", check=True)
                actual = Path(process.stdout.rsplit("Saved: ", 1)[1].strip()).resolve()
                if actual != destination:
                    raise ValueError("Incomplete previous prediction directory; inspect and recover it before retrying")
            prediction = json.loads((destination / "predictions.json").read_text())
            expected = next(r["checkpoint_sha256"] for r in report["results"] if r["dataset"] == dataset and r["variant"] == variant)
            if prediction["image_sha256"] != sample["image_sha256"] or prediction["models"][0]["weights_sha256"] != expected:
                raise ValueError("Example image or checkpoint differs from measured artifacts")
            with Image.open(destination / "yolo11_panel.jpg") as panel: panels.append(panel.copy())
        combined = Image.new("RGB", (sum(p.width for p in panels), max(p.height for p in panels)), "white")
        combined.paste(panels[0], (0, 0)); combined.paste(panels[1], (panels[0].width, 0))
        combined.save(root / dataset / "sample_prediction/side_by_side.jpg")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, default=Path("outputs/yolo11-original-improved-20261116"))
    args = parser.parse_args()
    root = args.study.resolve(); model_root = root.parents[1]
    status_path = root / "finish_status.json"
    if os.name == "nt": ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    def state(stage, **details): write_json(status_path, dict(pid=os.getpid(), stage=stage, **details))
    def command(arguments, env=None):
        with (root / "finish_pipeline.log").open("a", encoding="utf-8") as log:
            subprocess.run(arguments, cwd=model_root, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    try:
        state("waiting_for_twelve_real_runs")
        while True:
            study = json.loads((root / "study_status.json").read_text())
            if study["status"] == "failed": raise RuntimeError("Training controller failed; inspect study_status.json")
            if study["status"] == "complete": break
            time.sleep(10)
        state("verifying_results_and_building_figures")
        command([sys.executable, "-m", "trashsmart.yolo_training.ablation", "--root", str(root), "--stage", "collect"])
        report = json.loads((root / "comparison_original_improved.json").read_text())
        figures(root, report); examples(root, model_root, report)
        state("rewriting_chapter_three")
        python = "C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
        source = model_root / "outputs/yolo-three-datasets-20261115/documents/De_an_Vu_Duc_Dung_so_sanh_3_bo_du_lieu.docx"
        documents = root / "documents"
        command([python, "-X", "utf8", "scripts/update_ablation_chapter.py", "--source", str(source), "--study", str(root), "--output", str(documents)])
        old = model_root / "outputs/yolo11-vs-yolov8-doc-qa"
        office = model_root / ".tools/libreoffice-render/program/soffice.exe"
        env = os.environ.copy()
        env["PATH"] = str(office.parent) + ";C:/Users/ADMIN/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin;" + env.get("PATH", "")
        for document in sorted(documents.glob("*.docx")):
            state("refreshing_fields_and_rendering", document=str(document))
            qa = root / "document_qa"; qa.mkdir(exist_ok=True)
            command([str(office.with_name("python.exe")), str(old / "refresh_fields.py"), str(document), "--office", str(office),
                     "--profile", str(qa / ("fields-" + uuid.uuid4().hex[:8]))], env)
            command([python, "-X", "utf8", str(old / "render_docx.py"), str(document), "--output_dir", str(qa / document.stem), "--emit_pdf", "--dpi", "120"], env)
        state("ready_for_visual_review", documents=[str(p) for p in documents.glob("*.docx")])
    except Exception as error:
        state("failed", error=str(error)); raise
    finally:
        if os.name == "nt": ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__": main()
