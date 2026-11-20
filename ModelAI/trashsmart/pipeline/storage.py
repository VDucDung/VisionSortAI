"""Image storage adapter. Credentials are configured at application startup."""
import os
from typing import Optional
import cloudinary
import cloudinary.uploader
import cv2
import numpy as np


def configure_storage():
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )


def upload_image_bytes_to_cloudinary(
    image_bytes: bytes,
    folder: str,
    public_id: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    res = cloudinary.uploader.upload(
        image_bytes,
        resource_type="image",
        folder=folder,
        public_id=public_id,
        overwrite=overwrite,
        timeout=15,
    )
    return res.get("secure_url")


def upload_crop_to_cloudinary(
    crop_img: np.ndarray,
    folder: str,
    public_id: Optional[str] = None,
) -> Optional[str]:
    if crop_img is None or crop_img.size == 0:
        return None
    ok, crop_jpg = cv2.imencode(".jpg", crop_img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        return None
    res = cloudinary.uploader.upload(
        crop_jpg.tobytes(),
        resource_type="image",
        folder=folder,
        public_id=public_id,
        overwrite=True if public_id else False,
        timeout=15,
    )
    return res.get("secure_url")
