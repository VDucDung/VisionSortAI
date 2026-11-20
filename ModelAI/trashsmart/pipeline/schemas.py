"""Validated wire schemas shared by the HTTP adapters."""
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl
from trashsmart.pipeline.config import CONF_THRESHOLD, YOLO_IOU_THRESHOLD


class PredictUrlRequest(BaseModel):
    image_url: HttpUrl
    conf: float = Field(default=CONF_THRESHOLD, ge=0, le=1)
    iou: float = Field(default=YOLO_IOU_THRESHOLD, ge=0, le=1)
    request_id: Optional[int] = Field(default=None, ge=1)
