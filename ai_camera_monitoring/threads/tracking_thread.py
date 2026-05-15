import cv2
from PyQt5.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

from utils.config import TRACKING_SLEEP_MS, TRAJECTORY_LENGTH
from utils.fps import FPSCounter


class TrackingThread(QThread):
    tracked_frame_signal = pyqtSignal(int, object, float)
    tracking_data_signal = pyqtSignal(int, list)
    fps_signal = pyqtSignal(int, float)

    def __init__(self, camera_index, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.running = False
        self.latest_frame = None
        self.latest_frame_time = 0.0
        self.latest_detections = []
        self.mutex = QMutex()
        self.trajectories = {}

    def set_processed_frame(self, camera_index, frame, detections, frame_time):
        if camera_index != self.camera_index:
            return
        with QMutexLocker(self.mutex):
            self.latest_frame = frame
            self.latest_frame_time = frame_time
            self.latest_detections = list(detections)

    def reset_tracks(self):
        with QMutexLocker(self.mutex):
            self.trajectories.clear()

    def run(self):
        self.running = True
        fps_counter = FPSCounter()
        while self.running:
            with QMutexLocker(self.mutex):
                frame = self.latest_frame
                frame_time = self.latest_frame_time
                detections = list(self.latest_detections)
                self.latest_frame = None
                self.latest_detections = []

            if frame is None:
                self.msleep(TRACKING_SLEEP_MS)
                continue

            if not detections:
                self.tracked_frame_signal.emit(self.camera_index, frame, frame_time)
                self.tracking_data_signal.emit(self.camera_index, [])
                self.fps_signal.emit(self.camera_index, fps_counter.update())
                continue

            tracked_frame, tracked_objects = self._draw_tracks(frame, detections)
            self.tracked_frame_signal.emit(self.camera_index, tracked_frame, frame_time)
            self.tracking_data_signal.emit(self.camera_index, tracked_objects)
            self.fps_signal.emit(self.camera_index, fps_counter.update())

    def _draw_tracks(self, frame, detections):
        annotated_frame = frame.copy()
        tracked_objects = self._update_tracks(detections)

        for tracked_object in tracked_objects:
            self._draw_track(annotated_frame, tracked_object)

        return annotated_frame, tracked_objects

    def _update_tracks(self, detections):
        tracked_objects = []
        current_track_ids = set()

        for detection in detections:
            track_id = detection["id"]
            center = detection["center"]
            current_track_ids.add(track_id)

            trajectory = self.trajectories.setdefault(track_id, [])
            trajectory.append(center)
            if len(trajectory) > TRAJECTORY_LENGTH:
                trajectory.pop(0)

            tracked_objects.append({**detection, "trajectory": trajectory.copy()})

        for track_id in set(self.trajectories.keys()) - current_track_ids:
            self.trajectories.pop(track_id, None)

        return tracked_objects

    def _draw_track(self, frame, tracked_object):
        x1, y1, x2, y2 = tracked_object["bbox"]
        center = tracked_object["center"]
        trajectory = tracked_object["trajectory"]
        track_id = tracked_object["id"]
        confidence = tracked_object["confidence"]

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame, center, 5, (0, 0, 255), -1)
        cv2.putText(
            frame,
            f"Track ID {track_id} person {confidence:.2f}",
            (x1, max(y1 - 8, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
        for index in range(1, len(trajectory)):
            cv2.line(frame, trajectory[index - 1], trajectory[index], (255, 0, 0), 2)

    def stop(self):
        self.running = False
        self.wait()
