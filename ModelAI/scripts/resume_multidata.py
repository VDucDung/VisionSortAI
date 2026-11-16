"""Recover the interrupted HAUI run, then finish the frozen study and document inputs."""

import argparse
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

from trashsmart.yolo_training.benchmark import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    args = parser.parse_args()
    root = args.study.resolve()
    model_root = root.parents[1]
    state = root / "recovery_status.json"
    if os.name == "nt":
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)

    def run(stage, arguments):
        write_json(state, dict(pid=os.getpid(), stage=stage))
        with (root / (stage + ".log")).open("a", encoding="utf-8") as log:
            subprocess.run([sys.executable, "-X", "utf8", "-u", *arguments],
                           cwd=model_root, stdout=log, stderr=subprocess.STDOUT, check=True)

    try:
        protocol = json.loads((root / "haui/protocol.json").read_text(encoding="utf-8"))
        if protocol["status"] != "complete":
            from trashsmart.yolo_training.benchmark import verify_completed_run
            verify_completed_run(root / "haui/yolo11n", 30)
            try:
                verify_completed_run(root / "haui/yolov8n", 30)
            except ValueError:
                run("resume_haui_yolov8n", ["-m", "trashsmart.yolo_training.benchmark", "--output",
                    str(root / "haui"), "--stage", "train", "--model", "yolov8", "--resume-run"])
            run("evaluate_haui", ["-m", "trashsmart.yolo_training.benchmark", "--output",
                                  str(root / "haui"), "--stage", "evaluate"])
        run("remaining_datasets", ["-m", "trashsmart.yolo_training.multidata", "--root", str(root)])
        run("finish_documents", ["scripts/finish_multidata.py", "--study", str(root)])
        write_json(state, dict(pid=os.getpid(), stage="ready_for_visual_review"))
    except Exception as error:
        write_json(state, dict(pid=os.getpid(), stage="failed", error=str(error)))
        raise
    finally:
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == "__main__":
    main()
