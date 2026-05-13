from PyQt5.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

from models.yolo_detector import YOLODetector
from utils.config import MIN_TRACK_BOX_AREA, PERSON_CLASS_ID, PROCESS_SLEEP_MS
from utils.fps import FPSCounter


class ProcessThread(QThread):
    processed_signal = pyqtSignal(int, object, list)
    fps_signal = pyqtSignal(int, float)

    def __init__(self, camera_index, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.running = False
        self.latest_frame = None
        self.roi = None
        self.mutex = QMutex()
        self.detector = YOLODetector()

    def set_frame(self, camera_index, frame):
        if camera_index != self.camera_index:
            return
        with QMutexLocker(self.mutex):
            self.latest_frame = frame.copy()

    def set_roi(self, roi):
        with QMutexLocker(self.mutex):
            self.roi = roi

    def clear_roi(self):
        with QMutexLocker(self.mutex):
            self.roi = None

    def run(self):
        self.running = True
        fps_counter = FPSCounter()

        while self.running:
            with QMutexLocker(self.mutex):
                frame = self.latest_frame
                roi = self.roi
                self.latest_frame = None

            if frame is None:
                self.msleep(PROCESS_SLEEP_MS)
                continue

            detections = self._track_people_in_roi(frame, roi)
            self.processed_signal.emit(self.camera_index, frame, detections)
            self.fps_signal.emit(self.camera_index, fps_counter.update())

    def _track_people_in_roi(self, frame, roi):
        if roi is None:
            return []

        frame_height, frame_width = frame.shape[:2]
        x1, y1, x2, y2 = roi
        x1 = max(0, min(x1, frame_width - 1))
        y1 = max(0, min(y1, frame_height - 1))
        x2 = max(0, min(x2, frame_width))
        y2 = max(0, min(y2, frame_height))
        if x2 <= x1 or y2 <= y1:
            return []

        roi_frame = frame[y1:y2, x1:x2]
        results = self.detector.track(roi_frame)
        detections = []

        if not results or results[0].boxes is None:
            return detections

        for box in results[0].boxes:
            if box.id is None:
                continue

            class_id = int(box.cls[0])
            if class_id != PERSON_CLASS_ID:
                continue

            track_id = int(box.id[0])
            confidence = float(box.conf[0])
            box_x1, box_y1, box_x2, box_y2 = [int(value) for value in box.xyxy[0].tolist()]
            global_x1 = box_x1 + x1
            global_y1 = box_y1 + y1
            global_x2 = box_x2 + x1
            global_y2 = box_y2 + y1
            if (global_x2 - global_x1) * (global_y2 - global_y1) < MIN_TRACK_BOX_AREA:
                continue

            center = ((global_x1 + global_x2) // 2, (global_y1 + global_y2) // 2)
            detections.append(
                {
                    "id": track_id,
                    "bbox": (global_x1, global_y1, global_x2, global_y2),
                    "confidence": confidence,
                    "class_id": class_id,
                    "class_name": "person",
                    "center": center,
                }
            )

        return detections

    def stop(self):
        self.running = False
        self.wait()
