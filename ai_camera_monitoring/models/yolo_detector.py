from utils.config import (
    CONFIDENCE_THRESHOLD,
    IOU_THRESHOLD,
    YOLO_IMAGE_SIZE,
    YOLO_MODEL_PATH,
    YOLO_PERSON_CLASSES,
    YOLO_TRACKER,
)


class YOLODetector:
    def __init__(self, model_path=YOLO_MODEL_PATH, tracker=YOLO_TRACKER):
        self.model_path = model_path
        self.tracker = tracker
        self.model = None

    def load(self):
        from ultralytics import YOLO

        self.model = YOLO(self.model_path)

    def detect(self, frame):
        if self.model is None:
            self.load()
        return self.model(frame, **self._inference_options())

    def track(self, frame):
        if self.model is None:
            self.load()
        return self.model.track(
            frame,
            persist=True,
            tracker=self.tracker,
            **self._inference_options(),
        )

    def _inference_options(self):
        return {
            "conf": CONFIDENCE_THRESHOLD,
            "iou": IOU_THRESHOLD,
            "classes": YOLO_PERSON_CLASSES,
            "imgsz": YOLO_IMAGE_SIZE,
            "verbose": False,
        }
