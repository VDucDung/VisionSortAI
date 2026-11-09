import argparse

from ultralytics import YOLO
from trashsmart.shared.paths import YOLO_MODEL_PATH
from trashsmart.pipeline.config import CONF_THRESHOLD, YOLO_IMG_SIZE, YOLO_IOU_THRESHOLD, YOLO_TTA


def main():
    parser = argparse.ArgumentParser(description="Run YOLO inference on an image.")
    parser.add_argument("--image", required=True, help="Path to input image.")
    parser.add_argument("--imgsz", type=int, default=YOLO_IMG_SIZE, help="YOLO inference image size.")
    parser.add_argument("--conf", type=float, default=CONF_THRESHOLD, help="Confidence threshold.")
    parser.add_argument("--save", action="store_true", help="Save prediction image.")
    args = parser.parse_args()

    model = YOLO(str(YOLO_MODEL_PATH))
    results = model(args.image, imgsz=args.imgsz, conf=args.conf, iou=YOLO_IOU_THRESHOLD,
                    augment=YOLO_TTA, agnostic_nms=True, save=args.save)
    results[0].show()


if __name__ == "__main__":
    main()

