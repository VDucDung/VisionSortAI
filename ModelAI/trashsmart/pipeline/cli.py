"""Local single-image pipeline command, separate from the HTTP application."""
import json
import logging
import os
import cv2
from trashsmart.pipeline.config import (
    OUTPUT_DIR, INPUT_IMAGE, YOLO_MODEL_PATH, RESNET_MODEL_PATH, NUM_CLASSES,
)
from trashsmart.pipeline.models import load_yolo_model, load_resnet_model

logger = logging.getLogger(__name__)


def run(process_image):
    os.makedirs(str(OUTPUT_DIR), exist_ok=True)

    yolo_model   = load_yolo_model(YOLO_MODEL_PATH)
    resnet_model = load_resnet_model(RESNET_MODEL_PATH, NUM_CLASSES)

    logger.info("Bắt đầu xử lý ảnh...")
    image = cv2.imread(str(INPUT_IMAGE))
    if image is None:
        logger.error(f"Không đọc được ảnh: {INPUT_IMAGE}")
        return

    response = process_image(image, yolo_model, resnet_model)

    json_path = os.path.join(str(OUTPUT_DIR), "response.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(response, f, ensure_ascii=False, indent=2)

    logger.info(f"Kết quả JSON: {json_path}")
    logger.info(f"Tổng đối tượng phát hiện: {len(response['detections'])}")
