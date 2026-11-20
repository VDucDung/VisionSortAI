"""Compose the HTTP application without initializing model weights."""
from fastapi import FastAPI

from trashsmart.pipeline.admission import PredictionAdmission
from trashsmart.pipeline.routes import create_router
from trashsmart.pipeline.storage import configure_storage


def create_app(*, get_models, process_image, download_image_to_cv2):
    configure_storage()
    app = FastAPI(title="TrashSmart Detection API")
    app.add_middleware(PredictionAdmission)
    app.include_router(create_router(
        get_models=get_models,
        process_image=process_image,
        download_image_to_cv2=download_image_to_cv2,
    ))
    # The independent component experiment still loads its own weights lazily.
    from trashsmart.components.detail_api import app as detailed_app
    app.mount("/details", detailed_app)
    return app
