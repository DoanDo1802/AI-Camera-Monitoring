import time

import cv2
from PyQt5.QtCore import QThread, pyqtSignal

from utils.config import CAMERA_RECONNECT_SECONDS, DEFAULT_FRAME_DELAY_MS
from utils.fps import FPSCounter


class CaptureThread(QThread):
    frame_signal = pyqtSignal(int, object)
    fps_signal = pyqtSignal(int, float)
    status_signal = pyqtSignal(int, str)

    def __init__(self, camera_index, source=0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.source = source
        self.running = False

    def run(self):
        self.running = True
        fps_counter = FPSCounter()

        while self.running:
            self.status_signal.emit(self.camera_index, "Connecting")
            cap = cv2.VideoCapture(self.source)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not cap.isOpened():
                self.status_signal.emit(self.camera_index, "Reconnect waiting")
                time.sleep(CAMERA_RECONNECT_SECONDS)
                continue

            ok, frame = cap.read()
            if not ok:
                self.status_signal.emit(self.camera_index, "Reconnect waiting")
                cap.release()
                time.sleep(CAMERA_RECONNECT_SECONDS)
                continue

            video_fps = cap.get(cv2.CAP_PROP_FPS)
            frame_interval = 1 / video_fps if video_fps > 0 else DEFAULT_FRAME_DELAY_MS / 1000
            next_frame_time = time.time()
            self.status_signal.emit(self.camera_index, "Playing")

            while self.running and cap.isOpened():
                self.frame_signal.emit(self.camera_index, frame)
                self.fps_signal.emit(self.camera_index, fps_counter.update())

                next_frame_time += frame_interval
                wait_seconds = next_frame_time - time.time()
                if wait_seconds > 0:
                    self.msleep(int(wait_seconds * 1000))

                ok, frame = cap.read()
                if not ok:
                    self.status_signal.emit(self.camera_index, "Reconnecting")
                    break

            cap.release()
            if self.running:
                time.sleep(CAMERA_RECONNECT_SECONDS)

    def stop(self):
        self.running = False
        self.wait()
