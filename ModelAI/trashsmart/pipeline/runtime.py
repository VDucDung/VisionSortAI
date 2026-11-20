"""Process-local lazy model ownership and inference synchronization."""
import threading

from trashsmart.pipeline import config
from trashsmart.pipeline.models import load_resnet_model, load_yolo_model


class ModelRuntime:
    def __init__(self):
        self._yolo_model = None
        self._resnet_model = None
        self._model_lock = threading.Lock()
        self.inference_lock = threading.Lock()

    def get_models(self):
        with self._model_lock:
            if self._yolo_model is None:
                self._yolo_model = load_yolo_model(config.YOLO_MODEL_PATH)
            if self._resnet_model is None:
                self._resnet_model = load_resnet_model(config.RESNET_MODEL_PATH, config.NUM_CLASSES)
        return self._yolo_model, self._resnet_model
