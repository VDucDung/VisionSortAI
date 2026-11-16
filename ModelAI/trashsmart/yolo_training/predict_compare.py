"""Run either or both benchmark YOLO models on exactly the same local image."""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

from trashsmart.yolo_training.benchmark import sha256, write_json


def select_image():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        filename = filedialog.askopenfilename(
            parent=root,
            title="Choose an image for YOLO detection",
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
    finally:
        root.destroy()
    return Path(filename) if filename else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, help="Image path. Omit to open a file picker")
    parser.add_argument("--show", action="store_true", help="Open the saved result image")
    parser.add_argument("--model", choices=("yolo11", "yolov8", "existing", "both"), default="both")
    parser.add_argument("--experiment", type=Path, default=Path("outputs/yolo11-vs-yolov8"))
    parser.add_argument("--weights", type=Path, help="Override weights for a single-model run")
    parser.add_argument("--output", type=Path, required=True, help="Output directory, automatically numbered on repeated runs")
    parser.add_argument("--imgsz", type=int, help="Defaults to the frozen experiment size")
    parser.add_argument("--conf", type=float, default=.25)
    parser.add_argument("--iou", type=float, default=.7, help="NMS IoU, not ground-truth matching IoU")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    protocol_path = args.experiment / "protocol.json"
    if args.imgsz is None:
        if not protocol_path.is_file():
            parser.error("Provide --imgsz when no experiment protocol exists")
        args.imgsz = json.loads(protocol_path.read_text(encoding="utf-8"))["settings"]["imgsz"]
    if args.imgsz < 32 or args.imgsz % 32 or min(args.threads, args.repeats) < 1 or not 0 <= args.conf <= 1 or not 0 < args.iou <= 1:
        parser.error("Invalid image size, thresholds, threads or repeat count")
    if args.weights and args.model == "both":
        parser.error("--weights requires one model")
    choices = {"yolo11": args.experiment/"yolo11n/weights/best.pt",
               "yolov8": args.experiment/"yolov8n/weights/best.pt",
               "existing": args.experiment/"initial/existing_yolo11.pt"}
    names = ["yolo11", "yolov8"] if args.model == "both" else [args.model]
    paths = {name: args.weights or choices[name] for name in names}
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f"Train the model first, or provide --weights: {path}")
    if args.image is None:
        args.image = select_image()
        if args.image is None:
            print("Image selection cancelled.")
            return
    if not args.image.is_file():
        parser.error(f"Image does not exist: {args.image}. Omit --image to choose an image.")
    import cv2
    import numpy as np
    import torch
    from PIL import Image, ImageOps, ImageDraw, ImageFont
    from ultralytics import YOLO
    from ultralytics.utils.files import increment_path
    with Image.open(args.image) as source:
        rgb = ImageOps.exif_transpose(source).convert("RGB")
    pixels = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    torch.set_num_threads(args.threads)
    args.output = increment_path(args.output, exist_ok=False, mkdir=True)
    report = dict(image=str(args.image.resolve()), image_sha256=sha256(args.image),
                  width=rgb.width, height=rgb.height,
                  settings=dict(imgsz=args.imgsz, conf=args.conf, nms_iou=args.iou,
                                tta=False, device=args.device, threads=args.threads,
                                warmups=2, repeats=args.repeats),
                  interpretation="Confidence scores describe individual predictions. Dataset accuracy is measured against annotated ground-truth boxes.",
                  timing_scope="Median wall time for model.predict after warmup, including preprocessing and NMS.",
                  models=[])
    panels = []
    for name, path in paths.items():
        model = YOLO(str(path))
        # setup_model/device initialization can reset PyTorch thread settings.
        options = dict(source=pixels.copy(), imgsz=args.imgsz, conf=args.conf, iou=args.iou,
                       device=args.device, augment=False, agnostic_nms=True,
                       verbose=False, save=False)
        for _ in range(2):
            model.predict(**options)
            torch.set_num_threads(args.threads)
        durations = []
        for _ in range(args.repeats):
            if str(args.device) != "cpu" and torch.cuda.is_available():
                torch.cuda.synchronize()
            start = time.perf_counter()
            result = model.predict(**options)[0]
            if str(args.device) != "cpu" and torch.cuda.is_available():
                torch.cuda.synchronize()
            durations.append((time.perf_counter()-start)*1000)
        detections = [dict(class_id=int(box.cls.item()),
                           label=model.names[int(box.cls.item())],
                           confidence=float(box.conf.item()),
                           xyxy=[float(v) for v in box.xyxy[0].tolist()]) for box in result.boxes]
        row = dict(name=name, weights=str(path.resolve()), weights_sha256=sha256(path),
                   detection_count=len(detections), detections=detections,
                   median_predict_ms=statistics.median(durations),
                   min_predict_ms=min(durations), max_predict_ms=max(durations))
        report["models"].append(row)
        annotated = Image.fromarray(cv2.cvtColor(result.plot(), cv2.COLOR_BGR2RGB))
        annotated.save(args.output / (name + ".jpg"))
        # Keep the standalone image at full resolution; make a readable panel
        # for a desktop viewer and for the thesis figure.
        panel_image = Image.fromarray(cv2.cvtColor(result.plot(line_width=max(2, round(max(pixels.shape[:2])/500))), cv2.COLOR_BGR2RGB))
        panel_image.thumbnail((900, 900))
        panel = Image.new("RGB", (max(500, panel_image.width), panel_image.height+80), "white")
        panel.paste(panel_image, ((panel.width-panel_image.width)//2, 80))
        font = ImageFont.load_default(size=24)
        display_name = {"yolo11": "YOLO11", "yolov8": "YOLOv8", "existing": "Existing YOLO11"}[name]
        ImageDraw.Draw(panel).text((12, 8), f"{display_name} | boxes={len(detections)}\nMedian predict: {row['median_predict_ms']:.1f} ms", font=font, fill="black", spacing=7)
        panels.append(panel)
        print(json.dumps(row, ensure_ascii=False, indent=2))
    if len(panels) == 2:
        combined = Image.new("RGB", (sum(p.width for p in panels), max(p.height for p in panels)), "white")
        x = 0
        for panel in panels:
            combined.paste(panel, (x, 0))
            x += panel.width
        combined.save(args.output / "side_by_side.jpg")
    write_json(args.output / "predictions.json", report)
    print(f"Saved: {args.output.resolve()}")
    if args.show:
        filename = "side_by_side.jpg" if len(names) == 2 else names[0] + ".jpg"
        result_path = (args.output / filename).resolve()
        try:
            if os.name == "nt":
                os.startfile(result_path)
            else:
                with Image.open(result_path) as preview:
                    preview.show()
        except OSError as error:
            print(f"Could not open the image viewer: {error}. Open {result_path} manually.")


if __name__ == "__main__":
    main()
