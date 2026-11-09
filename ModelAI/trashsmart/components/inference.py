"""Optional component analysis. Missing/unvalidated weights never produce fake parts."""
import hashlib
import json
import logging
import os
import threading
from pathlib import Path

from . import PARTS, MATERIALS

logger = logging.getLogger(__name__)
_lock = threading.Lock()
_engine = None
_loaded_signature = None


def release_config():
    enabled = os.getenv("PARTS_ENABLED", "false").strip().lower() in ("1", "true", "yes")
    path = Path(os.getenv("PARTS_RELEASE_PATH", "trashsmart/models/components/release.json"))
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    path = path.resolve()
    if not enabled:
        return "NOT_RUN", None, path
    try:
        release = json.loads(path.read_text(encoding="utf-8"))
        if release.get("trainingScope") != "bottle-components" or release.get("validated") is not True:
            return "MODEL_UNAVAILABLE", None, path
        if not release.get("version") or not release.get("evaluationReport"):
            return "MODEL_UNAVAILABLE", None, path
        for key in ("detector", "materialClassifier"):
            entry = release[key]
            weight = (path.parent / entry["file"]).resolve()
            if not weight.is_relative_to(path.parent) or not weight.is_file() or len(entry.get("sha256", "")) != 64:
                return "MODEL_UNAVAILABLE", None, path
        evaluation_path = (path.parent / release["evaluationReport"]).resolve()
        if not evaluation_path.is_relative_to(path.parent):
            return "MODEL_UNAVAILABLE", None, path
        evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        if (evaluation.get("split") != "test" or evaluation.get("endToEndReviewed") is not True
                or evaluation.get("detectorSha256") != release["detector"]["sha256"]
                or evaluation.get("materialSha256") != release["materialClassifier"]["sha256"]):
            return "MODEL_UNAVAILABLE", None, path
        return "READY", release, path
    except (OSError, ValueError, KeyError, TypeError):
        return "MODEL_UNAVAILABLE", None, path


def capabilities():
    status, release, path = release_config()
    return {"apiVersion": 1, "status": status, "partTypes": list(PARTS),
            "materialCodes": list(MATERIALS), "modelVersion": release["version"] if release else None,
            "requiresValidatedCheckpoint": True,
            "weightsLoaded": _engine is not None and _loaded_signature == json.dumps(release, sort_keys=True) + str(path)}


class ComponentEngine:
    def __init__(self, release, path):
        from ultralytics import YOLO
        from .training import load_classifier, material_transform
        for key in ("detector", "materialClassifier"):
            weight = path.parent / release[key]["file"]
            if hashlib.sha256(weight.read_bytes()).hexdigest() != release[key]["sha256"]:
                raise ValueError("Component checkpoint checksum mismatch")
        self.detector = YOLO(str(path.parent / release["detector"]["file"]))
        if [self.detector.names[i] for i in range(len(self.detector.names))] != list(PARTS):
            raise ValueError("Wrong part detector classes")
        self.classifier, _ = load_classifier(path.parent / release["materialClassifier"]["file"])
        self.transform = material_transform()
        self.threshold = float(release.get("materialThreshold", .7))
        self.detector_threshold = float(release.get("detectionThreshold", .25))
        if not 0 <= self.threshold <= 1 or not 0 <= self.detector_threshold <= 1:
            raise ValueError("Invalid component confidence thresholds")
        self.version = release["version"]
        self.image_size = int(release.get("detectorImageSize", 512))

    def predict(self, image, detections):
        import torch
        from PIL import Image
        h, w = image.shape[:2]
        output = []
        for parent in detections:
            x1, y1, x2, y2 = (int(parent[k]) for k in ("x1", "y1", "x2", "y2"))
            if not 0 <= x1 < x2 <= w or not 0 <= y1 < y2 <= h:
                raise ValueError("Invalid bottle coordinates")
            crop = image[y1:y2, x1:x2]
            components = []
            # Class-aware NMS allows overlapping body and label boxes.
            result = self.detector.predict(crop, conf=self.detector_threshold, imgsz=self.image_size, max_det=30,
                                           agnostic_nms=False, device="cpu", verbose=False)[0]
            crops, boxes = [], []
            if result.boxes is not None:
                for b in result.boxes:
                    px1, py1, px2, py2 = [int(v) for v in b.xyxy[0].tolist()]
                    px1, py1 = max(0, px1), max(0, py1)
                    px2, py2 = min(x2-x1, px2), min(y2-y1, py2)
                    if px1 >= px2 or py1 >= py2:
                        continue
                    rgb = Image.fromarray(crop[py1:py2, px1:px2, ::-1].copy())
                    crops.append(self.transform(rgb))
                    boxes.append((b, (px1+x1, py1+y1, px2+x1, py2+y1)))
            if crops:
                with torch.inference_mode():
                    probabilities = self.classifier(torch.stack(crops)).softmax(1)
                for (b, coords), probabilities in zip(boxes, probabilities):
                    confidence, cls = probabilities.max(0)
                    confidence = float(confidence)
                    known = confidence >= self.threshold
                    components.append({"partType": PARTS[int(b.cls.item())], "material": MATERIALS[int(cls)] if known else "unknown",
                                       "detectionConfidence": round(float(b.conf.item()), 5), "materialConfidence": round(confidence, 5),
                                       "needsConfirm": not known, **dict(zip(("x1", "y1", "x2", "y2"), coords))})
            output.append(components)
        return output


def attach_components(image, response):
    global _engine, _loaded_signature
    status, release, path = release_config()
    response.update({"componentsApiVersion": 1, "componentModelVersion": None, "analysisMode": "bottle", "componentCount": 0})
    for parent in response["detections"]:
        parent.update({"componentAnalysisStatus": status if status != "READY" else "FAILED", "components": []})
    if status != "READY":
        return response
    try:
        signature = json.dumps(release, sort_keys=True) + str(path)
        with _lock:
            if _engine is None or signature != _loaded_signature:
                _engine = ComponentEngine(release, path)
                _loaded_signature = signature
            groups = _engine.predict(image, response["detections"])
        if len(groups) != len(response["detections"]):
            raise ValueError("Component parent count mismatch")
        for parent, components in zip(response["detections"], groups):
            parent.update({"componentAnalysisStatus": "COMPLETED", "components": components})
        response.update({"analysisMode": "bottle_components", "componentModelVersion": release["version"],
                         "componentCount": sum(len(g) for g in groups)})
        response["requiresConfirmation"] = response.get("requiresConfirmation", False) or any(c["needsConfirm"] for g in groups for c in g)
    except Exception:
        logger.exception("Optional component analysis failed; returning bottle result")
    return response
