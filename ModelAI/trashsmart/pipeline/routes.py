"""HTTP adapters. Services are injected so request handling never owns models."""
import logging
from typing import Any, Dict, Optional
import anyio
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from trashsmart.pipeline.config import (
    CLASS_NAMES, RESNET_CONF_THRESHOLD, CONF_THRESHOLD, YOLO_IOU_THRESHOLD,
)
from trashsmart.pipeline.input_limits import read_upload, ImageInputError
from trashsmart.pipeline.schemas import PredictUrlRequest
from trashsmart.components.inference import capabilities as component_capabilities

logger = logging.getLogger(__name__)


def create_router(*, get_models, process_image, download_image_to_cv2):
    router = APIRouter()
    _health_limiter = anyio.CapacityLimiter(1)

    @router.get("/metadata")
    async def metadata():
        """Lightweight integration contract; does not load weights or run inference."""
        from trashsmart.pipeline.input_limits import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS, MAX_IMAGE_SIDE
        return {
            "apiVersion": "1",
            "materialCodes": list(CLASS_NAMES),
            "unknownLabel": "unknown",
            "confidenceSource": "resnet50",
            "confidenceRange": [0, 1],
            "confirmationThreshold": RESNET_CONF_THRESHOLD,
            "detectorConfidence": CONF_THRESHOLD,
            "detectorIou": YOLO_IOU_THRESHOLD,
            "maxImageBytes": MAX_IMAGE_BYTES,
            "maxImagePixels": MAX_IMAGE_PIXELS,
            "maxImageSide": MAX_IMAGE_SIDE,
            "components": component_capabilities(),
        }

    @router.get("/health")
    async def health():
        try:
            await anyio.to_thread.run_sync(get_models, limiter=_health_limiter)
        except Exception:
            logger.exception("Model readiness failed")
            return JSONResponse({"status": "unavailable", "modelsReady": False}, status_code=503)
        return {"status": "ok", "modelsReady": True, "components": component_capabilities()}

    @router.get("/live")
    async def live():
        return {"status": "ok"}

    @router.post("/predict-image")
    def predict_image(file: UploadFile = File(...)):
        return predict_uploaded_image(file)

    def predict_uploaded_image(file: UploadFile, request_id: Optional[int] = None):
        """Sync endpoints run decoding, inference and uploads in FastAPI's thread pool."""
        try:
            img = read_upload(file.file)
            yolo_model, resnet_model = get_models()
            result = process_image(img, yolo_model, resnet_model, request_id=request_id)
            return JSONResponse(content=result, status_code=200)
        except ImageInputError as e:
            return JSONResponse({"error": str(e)}, status_code=e.status_code)
        except Exception:
            logger.exception("Prediction/upload failed")
            return JSONResponse({"error": "Prediction/upload failed"}, status_code=500)

    @router.post("/predict-image-url")
    def predict_image_url(req: PredictUrlRequest) -> Dict[str, Any]:
        try:
            img = download_image_to_cv2(str(req.image_url))
        except ImageInputError as e:
            return JSONResponse({"error": str(e)}, status_code=e.status_code)
        except Exception:
            logger.exception("Image URL download failed")
            return JSONResponse(
                {"error": "Failed to download/decode image"},
                status_code=400,
            )

        if img is None:
            return JSONResponse({"error": "Invalid image data"}, status_code=400)

        try:
            yolo_model, resnet_model = get_models()
            result = process_image(
                img,
                yolo_model,
                resnet_model,
                request_id=req.request_id,
                original_image_url=str(req.image_url),
                conf=req.conf,
                iou=req.iou,
            )
            return result
        except Exception:
            logger.exception("URL prediction/upload failed")
            return JSONResponse({"error": "Predict/upload failed"}, status_code=500)

    @router.post("/predict-image-json")
    def predict_image_json(
        file: UploadFile = File(...),
        request_id: Optional[int] = None
    ):
        return predict_uploaded_image(file, request_id=request_id)

    return router
