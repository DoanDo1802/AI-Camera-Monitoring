import time

from PyQt5.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

from utils.config import ROI_CROWDED_THRESHOLD, ROI_LOITERING_SECONDS, ROI_MISSING_GRACE_SECONDS


class EventThread(QThread):
    alert_signal = pyqtSignal(str)

    def __init__(self, camera_count, parent=None):
        super().__init__(parent)
        self.camera_count = camera_count
        self.running = False
        self.mutex = QMutex()
        self.roi_rects = [None] * camera_count
        self.latest_tracking_data = [None] * camera_count
        self.roi_entry_times = [{} for _ in range(camera_count)]
        self.roi_last_seen_times = [{} for _ in range(camera_count)]
        self.roi_last_alert_times = [{} for _ in range(camera_count)]
        self.roi_crowded_alerting = [False] * camera_count

    def set_roi(self, camera_index, roi):
        with QMutexLocker(self.mutex):
            self.roi_rects[camera_index] = roi
            self._reset_camera_state(camera_index)

    def clear_roi(self, camera_index):
        with QMutexLocker(self.mutex):
            self.roi_rects[camera_index] = None
            self.latest_tracking_data[camera_index] = None
            self._reset_camera_state(camera_index)

    def set_tracking_data(self, camera_index, tracked_objects):
        with QMutexLocker(self.mutex):
            self.latest_tracking_data[camera_index] = list(tracked_objects)

    def run(self):
        self.running = True
        while self.running:
            events = []
            with QMutexLocker(self.mutex):
                for camera_index in range(self.camera_count):
                    roi = self.roi_rects[camera_index]
                    tracked_objects = self.latest_tracking_data[camera_index]
                    self.latest_tracking_data[camera_index] = None
                    if roi is None or tracked_objects is None:
                        continue
                    events.append((camera_index, tracked_objects, roi))

            for camera_index, tracked_objects, roi in events:
                self._process_camera(camera_index, tracked_objects, roi)

            self.msleep(50)

    def stop(self):
        self.running = False
        self.wait()

    def _reset_camera_state(self, camera_index):
        self.roi_entry_times[camera_index].clear()
        self.roi_last_seen_times[camera_index].clear()
        self.roi_last_alert_times[camera_index].clear()
        self.roi_crowded_alerting[camera_index] = False

    def _process_camera(self, camera_index, tracked_objects, roi):
        x1, y1, x2, y2 = roi
        now = time.time()
        current_roi_ids = set()

        for tracked_object in tracked_objects:
            center_x, center_y = tracked_object["center"]
            track_id = tracked_object["id"]
            if not (x1 <= center_x <= x2 and y1 <= center_y <= y2):
                continue

            current_roi_ids.add(track_id)
            self.roi_last_seen_times[camera_index][track_id] = now
            if track_id not in self.roi_entry_times[camera_index]:
                self.roi_entry_times[camera_index][track_id] = now

            duration = now - self.roi_entry_times[camera_index][track_id]
            last_alert_time = self.roi_last_alert_times[camera_index].get(track_id, 0)
            if duration >= ROI_LOITERING_SECONDS and now - last_alert_time >= ROI_LOITERING_SECONDS:
                self.roi_last_alert_times[camera_index][track_id] = now
                self.alert_signal.emit(
                    f"Camera {camera_index + 1}: Track ID {track_id} stayed in ROI over {int(duration)}s"
                )

        if len(current_roi_ids) > ROI_CROWDED_THRESHOLD:
            if not self.roi_crowded_alerting[camera_index]:
                self.roi_crowded_alerting[camera_index] = True
                self.alert_signal.emit(
                    f"Camera {camera_index + 1}: ROI crowded {len(current_roi_ids)}/{ROI_CROWDED_THRESHOLD} people"
                )
        else:
            self.roi_crowded_alerting[camera_index] = False

        previous_roi_ids = set(self.roi_entry_times[camera_index].keys())
        for track_id in previous_roi_ids - current_roi_ids:
            last_seen = self.roi_last_seen_times[camera_index].get(track_id, 0)
            if now - last_seen <= ROI_MISSING_GRACE_SECONDS:
                continue
            self.roi_entry_times[camera_index].pop(track_id, None)
            self.roi_last_seen_times[camera_index].pop(track_id, None)
            self.roi_last_alert_times[camera_index].pop(track_id, None)

