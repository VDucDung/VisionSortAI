"""Synthetic integration check only; its metrics are never study results."""
import argparse
import json
from pathlib import Path

import torch
from PIL import Image, ImageDraw
from ultralytics import YOLO

from trashsmart.yolo_training.improvements import TRAINERS, AttentionOutput


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for split in ("train", "val"):
        (root / split / "images").mkdir(parents=True)
        (root / split / "labels").mkdir()
        for index in range(2):
            image = Image.new("RGB", (64, 64), (30 + 20 * index, 40, 50))
            ImageDraw.Draw(image).rectangle((16, 8, 48, 56), fill=(160, 200, 220))
            image.save(root / split / "images" / f"{index}.png")
            (root / split / "labels" / f"{index}.txt").write_text("0 .5 .5 .5 .75\n")
    data = root / "data.yaml"
    data.write_text(json.dumps(dict(path=root.as_posix(), train="train/images", val="val/images", nc=1, names=["item"])))
    digests = []
    torch.set_num_threads(4)
    for variant, trainer in TRAINERS.items():
        model = YOLO("yolo11n.pt")
        model.add_callback("on_train_start", lambda trainer: torch.set_num_threads(4))
        model.add_callback("on_val_start", lambda validator: torch.set_num_threads(4))
        model.train(trainer=trainer, data=str(data), project=str(root), name=variant,
                    epochs=1, imgsz=64, batch=2, device="cpu", workers=0, seed=42,
                    deterministic=True, optimizer="AdamW", lr0=.0005, amp=False,
                    plots=False, mosaic=0, cache=False, verbose=False)
        initialization = json.loads((root / variant / "initialization.json").read_text())
        digests.append(initialization["common_initial_sha256"])
        restored = YOLO(str(root / variant / "weights/best.pt"))
        assert sum(isinstance(module, AttentionOutput) for module in restored.model.modules()) == (3 if trainer.cbam else 0)
        restored.predict(source=str(root / "val/images/0.png"), imgsz=64, device="cpu", verbose=False)
        print("SMOKE PASSED", variant, initialization, flush=True)
    assert len(set(digests)) == 1, "Initial original detector tensors differ between variants"
    (root / "verification.json").write_text(json.dumps(dict(status="passed", variants=list(TRAINERS),
        common_initial_sha256=digests[0], scope="Synthetic integration check; never real dataset accuracy"), indent=2))


if __name__ == "__main__":
    main()
