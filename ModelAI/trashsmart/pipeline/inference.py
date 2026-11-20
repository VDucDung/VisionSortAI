"""YOLO -> material classifier -> optional components, independent of HTTP routing."""
import logging
import os
from typing import Any, Dict, List, Optional
import cv2
import numpy as np
import torch
from trashsmart.pipeline import config
from trashsmart.pipeline.storage import upload_image_bytes_to_cloudinary, upload_crop_to_cloudinary
from trashsmart.components.inference import attach_components
from trashsmart.pipeline.utils import (
    build_detection_label, build_vietnamese_detection_label, draw_label_box,
    enhance_for_display, get_class_labels_batch, preprocess_batch_for_resnet,
)

logger = logging.getLogger(__name__)


def clamp_bbox(x1: int, y1: int, x2: int, y2: int, width: int, height: int):
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(0, min(x2, width))
    y2 = max(0, min(y2, height))
    return x1, y1, x2, y2


def _process_bottles(
    image: np.ndarray,
    yolo_model,
    resnet_model,
    request_id: Optional[int] = None,
    original_image_url: Optional[str] = None,
    conf: float = config.CONF_THRESHOLD,
    iou: float = config.YOLO_IOU_THRESHOLD,
    *,
    inference_lock,
) -> Dict[str, Any]:
    """
    Pipeline chính:
        1. YOLO detect → lấy bounding boxes
        2. Batch enhance + ResNet classify tất cả crops cùng lúc
        3. ESRGAN upscale từng crop để xuất ảnh đẹp
        4. Upload annotated image + crops (needsConfirm) lên Cloudinary

    Returns:
        dict theo format API (requestId, annotatedUrl, detections, ...)
    """
    response_image_url = original_image_url
    h, w = image.shape[:2]

    # --- YOLO Detection ---
    with inference_lock:
        results = yolo_model(image, imgsz=config.YOLO_IMG_SIZE, conf=conf, iou=iou,
                             augment=config.YOLO_TTA, agnostic_nms=config.YOLO_AGNOSTIC_NMS)
    os.makedirs(str(config.CROPS_DIR), exist_ok=True)

    # Thu thập tất cả valid crops + metadata
    valid_items = []

    for result in results:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            continue

        for box in boxes:
            yolo_conf = box.conf.item()
            if yolo_conf < conf:
                continue

            yolo_cls_id = int(box.cls.item())
            raw_yolo_label = result.names.get(yolo_cls_id, "unknown")
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            x1, y1, x2, y2 = clamp_bbox(x1, y1, x2, y2, w, h)

            crop = image[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            valid_items.append({
                "crop":           crop,
                "yolo_label":     config.YOLO_OBJECT_LABEL,
                "raw_yolo_label": raw_yolo_label,
                "yolo_conf":      yolo_conf,
                "bbox":           (x1, y1, x2, y2),
            })

    if not valid_items:
        logger.info("Không phát hiện đối tượng hợp lệ.")
        # Upload ảnh gốc không có annotation
        annotated = image.copy()
        ok, out_jpg = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        annotated_url = None
        if ok:
            annotated_public_id = f"req_{request_id}" if request_id else None
            annotated_url = upload_image_bytes_to_cloudinary(
                out_jpg.tobytes(),
                folder="hauitrash/annotated",
                public_id=annotated_public_id,
                overwrite=True if request_id else False,
            )
        return {
            "apiVersion":           "1",
            "requestId":            request_id,
            "imageUrl":             response_image_url,
            "annotatedUrl":         annotated_url,
            "count":                0,
            "confidenceAvg":        0.0,
            "requiresConfirmation": False,
            "detections":           [],
        }

    logger.info(f"Phát hiện {len(valid_items)} đối tượng → Batch ResNet inference...")

    # --- Batch ResNet Inference ---
    batch_tensor = preprocess_batch_for_resnet([item["crop"] for item in valid_items])

    with inference_lock, torch.no_grad():
        batch_output = resnet_model(batch_tensor)

    resnet_results = get_class_labels_batch(batch_output, config.CLASS_NAMES)

    # --- Vẽ bounding box với cả YOLO + ResNet label lên ảnh gốc ---
    annotated = image.copy()
    for item, (resnet_label, resnet_conf) in zip(valid_items, resnet_results):
        x1, y1, x2, y2 = item["bbox"]
        display_label = build_vietnamese_detection_label(item["yolo_label"], resnet_label)
        label_text = f"{display_label} {resnet_conf:.0%}"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label_y = y1 - 30 if y1 >= 30 else y1 + 4
        draw_label_box(
            annotated,
            label_text,
            x1,
            label_y,
            font_size=20,
            bg_color=(0, 255, 0),
            text_color=(0, 0, 0),
        )

    ok, out_jpg = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        raise RuntimeError("Failed to encode annotated image")

    annotated_public_id = f"req_{request_id}" if request_id else None
    annotated_url = upload_image_bytes_to_cloudinary(
        out_jpg.tobytes(),
        folder="hauitrash/annotated",
        public_id=annotated_public_id,
        overwrite=True if request_id else False,
    )

    # --- Xuất ảnh crop + build response ---
    detections: List[Dict[str, Any]] = []
    conf_list:  List[float] = []

    for i, (item, (resnet_label, resnet_conf)) in enumerate(
        zip(valid_items, resnet_results), start=1
    ):
        crop  = item["crop"]
        x1, y1, x2, y2 = item["bbox"]
        combined_label = build_detection_label(item["yolo_label"], resnet_label)
        display_label = build_vietnamese_detection_label(item["yolo_label"], resnet_label)

        # ESRGAN upscale để xuất ảnh đẹp
        if config.FIX_ESRGAN:
            logger.info(f"  [{i}/{len(valid_items)}] ESRGAN upscale: {resnet_label}")
            crop_final = enhance_for_display(crop)
        else:
            crop_final = crop.copy()

        # Vẽ label lên crop
        label_text = f"{display_label} ({resnet_conf:.0%})"
        draw_label_box(
            crop_final,
            label_text,
            10,
            10,
            font_size=20,
            bg_color=(0, 255, 0),
            text_color=(0, 0, 0),
        )

        needs_confirm = resnet_conf < config.RESNET_CONF_THRESHOLD
        crop_url = None

        if needs_confirm:
            crop_public_id = f"req_{request_id}_crop_{i}" if request_id else None
            try:
                crop_url = upload_crop_to_cloudinary(
                    crop_final,
                    folder="hauitrash/crops",
                    public_id=crop_public_id,
                )
            except Exception:
                crop_url = None

        conf_list.append(resnet_conf)

        detection: Dict[str, Any] = {
            "label": resnet_label,
            "labelDisplay":  display_label,
            "confidence":    round(resnet_conf, 4),
            "x1":            x1,
            "y1":            y1,
            "x2":            x2,
            "y2":            y2,
            "annotatedUrl":  annotated_url,
            "needsConfirm":  needs_confirm,
        }
        if crop_url:
            detection["cropUrl"] = crop_url

        detections.append(detection)

    confidence_avg        = round(sum(conf_list) / len(conf_list), 4) if conf_list else 0.0
    requires_confirmation = any(d.get("needsConfirm", False) for d in detections)

    logger.info(f"Hoàn tất: {len(detections)} đối tượng được phân loại.")

    return {
        "apiVersion":           "1",
            "requestId":            request_id,
        "imageUrl":             response_image_url,
        "annotatedUrl":         annotated_url,
        "count":                len(detections),
        "confidenceAvg":        confidence_avg,
        "requiresConfirmation": requires_confirmation,
        "detections":           detections,
    }


def process_image(image, yolo_model, resnet_model, request_id=None,
                  original_image_url=None, conf=config.CONF_THRESHOLD,
                  iou=config.YOLO_IOU_THRESHOLD, *, inference_lock):
    response = _process_bottles(
        image, yolo_model, resnet_model, request_id=request_id,
        original_image_url=original_image_url, conf=conf, iou=iou,
        inference_lock=inference_lock,
    )
    return attach_components(image, response)
