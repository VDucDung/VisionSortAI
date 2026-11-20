"""Stable ASGI/CLI entry point; implementation lives in focused pipeline modules."""
import logging
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from trashsmart.pipeline import config, inference
from trashsmart.pipeline.application import create_app
from trashsmart.pipeline.input_limits import download_image as download_image_to_cv2
from trashsmart.pipeline.runtime import ModelRuntime
from trashsmart.pipeline.schemas import PredictUrlRequest

# Keep the integration constants and public Python entry points available.
CLASS_NAMES = config.CLASS_NAMES
RESNET_CONF_THRESHOLD = config.RESNET_CONF_THRESHOLD

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

_runtime = ModelRuntime()


def get_models():
    return _runtime.get_models()


def process_image(image, yolo_model, resnet_model, request_id=None,
                  original_image_url=None, conf=config.CONF_THRESHOLD,
                  iou=config.YOLO_IOU_THRESHOLD):
    return inference.process_image(
        image, yolo_model, resnet_model, request_id=request_id,
        original_image_url=original_image_url, conf=conf, iou=iou,
        inference_lock=_runtime.inference_lock,
    )


app = create_app(
    get_models=lambda: get_models(),
    process_image=lambda *args, **kwargs: process_image(*args, **kwargs),
    download_image_to_cv2=lambda url: download_image_to_cv2(url),
)


def main():
    from trashsmart.pipeline.cli import run
    run(process_image)


if __name__ == "__main__":
    main()
