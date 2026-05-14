import time

import cv2

from PyQt5.QtCore import Qt, QRect, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPainter, QPen, QPixmap

from threads.capture_thread import CaptureThread
from threads.event_thread import EventThread
from threads.process_thread import ProcessThread
from threads.tracking_thread import TrackingThread
from utils.config import APP_TITLE, CAMERA_COUNT, CAMERA_SOURCES, WINDOW_HEIGHT, WINDOW_WIDTH
from PyQt5.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CameraView(QLabel):
    roi_drawn = pyqtSignal(int, tuple)

    def __init__(self, camera_index, text):
        super().__init__(text)
        self.camera_index = camera_index
        self.drawing_enabled = False
        self.start_pos = None
        self.preview_rect = None
        self.frame_shape = None
        self.setMouseTracking(True)

    def enable_roi_drawing(self):
        self.drawing_enabled = True
        self.setCursor(Qt.CrossCursor)

    def set_frame_shape(self, frame_shape):
        self.frame_shape = frame_shape

    def clear_preview(self):
        self.preview_rect = None
        self.update()

    def mousePressEvent(self, event):
        if self.drawing_enabled and event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.preview_rect = QRect(self.start_pos, self.start_pos)
            self.update()

    def mouseMoveEvent(self, event):
        if self.drawing_enabled and self.start_pos is not None:
            self.preview_rect = QRect(self.start_pos, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if not self.drawing_enabled or self.start_pos is None or event.button() != Qt.LeftButton:
            return

        self.preview_rect = QRect(self.start_pos, event.pos()).normalized()
        roi = self._label_rect_to_frame_rect(self.preview_rect)
        self.drawing_enabled = False
        self.start_pos = None
        self.preview_rect = None
        self.unsetCursor()
        if roi is not None:
            self.roi_drawn.emit(self.camera_index, roi)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.preview_rect is None:
            return
        painter = QPainter(self)
        painter.setPen(QPen(Qt.yellow, 2, Qt.DashLine))
        painter.drawRect(self.preview_rect)

    def _label_rect_to_frame_rect(self, rect):
        if self.frame_shape is None or self.pixmap() is None:
            return None

        frame_height, frame_width = self.frame_shape[:2]
        scaled = self.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        offset_x = (self.width() - scaled.width()) / 2
        offset_y = (self.height() - scaled.height()) / 2

        x1 = max(rect.left() - offset_x, 0)
        y1 = max(rect.top() - offset_y, 0)
        x2 = min(rect.right() - offset_x, scaled.width())
        y2 = min(rect.bottom() - offset_y, scaled.height())

        if x2 <= x1 or y2 <= y1:
            return None

        scale_x = frame_width / scaled.width()
        scale_y = frame_height / scaled.height()
        return (
            int(x1 * scale_x),
            int(y1 * scale_y),
            int(x2 * scale_x),
            int(y2 * scale_y),
        )


class CameraZoomWindow(QWidget):
    def __init__(self, camera_index):
        super().__init__()
        self.camera_index = camera_index
        self.setWindowTitle(f"Camera {camera_index + 1} - Zoom")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)
        self.video_label = QLabel(f"Camera {camera_index + 1}")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #111; color: white; font-size: 22px;")
        layout.addWidget(self.video_label)

    def update_frame(self, pixmap):
        self.video_label.setPixmap(
            pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.camera_views = []
        self.camera_status_labels = []
        self.camera_fps_labels = []
        self.camera_process_fps_labels = []
        self.camera_tracking_fps_labels = []
        self.camera_object_labels = []
        self.camera_roi_count_labels = []
        self.camera_toggle_buttons = []
        self.camera_zoom_buttons = []
        self.camera_roi_buttons = []
        self.camera_clear_roi_buttons = []
        self.camera_roi_rects = [None] * len(CAMERA_SOURCES)
        self.camera_connection_alerting = [False] * len(CAMERA_SOURCES)
        self.zoom_windows = [None] * len(CAMERA_SOURCES)
        self.capture_threads = [None] * len(CAMERA_SOURCES)
        self.process_threads = [None] * len(CAMERA_SOURCES)
        self.tracking_threads = [None] * len(CAMERA_SOURCES)
        self.event_thread = EventThread(len(CAMERA_SOURCES))
        self.event_thread.roi_count_signal.connect(self.update_roi_count)
        self.event_thread.alert_signal.connect(self.show_alert)
        self.event_thread.start()
        self.auto_started = False
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        main_layout = QHBoxLayout(root)

        camera_grid = QGridLayout()
        for camera_index in range(CAMERA_COUNT):
            camera_box = self._create_camera_box(camera_index)
            row = camera_index // 2
            column = camera_index % 2
            camera_grid.addWidget(camera_box, row, column)

        side_panel = QVBoxLayout()
        self.total_object_count_label = QLabel("Total objects: 0")
        self.alert_label = QLabel("Alert: None")
        self.event_log = QListWidget()

        side_panel.addWidget(QLabel("System status"))
        side_panel.addWidget(self.total_object_count_label)
        side_panel.addWidget(self.alert_label)
        side_panel.addWidget(QLabel("Alert history"))
        side_panel.addWidget(self.event_log)

        main_layout.addLayout(camera_grid, 4)
        main_layout.addLayout(side_panel, 1)

        self.setCentralWidget(root)

    def _create_camera_box(self, camera_index):
        camera_number = camera_index + 1
        box = QGroupBox(f"Camera {camera_number}")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        video_label = CameraView(camera_index, f"Camera {camera_number}\nassets/videos/camera_{camera_number}.mp4")
        video_label.setAlignment(Qt.AlignCenter)
        video_label.setMinimumSize(420, 320)
        video_label.setStyleSheet("background-color: #111; color: white; font-size: 18px;")
        video_label.roi_drawn.connect(self.set_camera_roi)

        status_label = QLabel("Status: Stopped")
        fps_label = QLabel("Capture: 0")
        process_fps_label = QLabel("Process: 0")
        tracking_fps_label = QLabel("Tracking: 0")
        object_label = QLabel("Objects: 0")
        roi_count_label = QLabel("ROI: 0")
        info_layout = QHBoxLayout()
        info_layout.setSpacing(10)
        info_layout.addWidget(status_label)
        info_layout.addWidget(fps_label)
        info_layout.addWidget(process_fps_label)
        info_layout.addWidget(tracking_fps_label)
        info_layout.addWidget(object_label)
        info_layout.addWidget(roi_count_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        toggle_button = QPushButton("Start")
        zoom_button = QPushButton("Zoom")
        roi_button = QPushButton("Draw ROI")
        clear_roi_button = QPushButton("Clear ROI")
        for button in (toggle_button, zoom_button, roi_button, clear_roi_button):
            button.setFixedHeight(28)
        toggle_button.clicked.connect(lambda checked=False, index=camera_index: self.toggle_camera(index))
        zoom_button.clicked.connect(lambda checked=False, index=camera_index: self.open_zoom_window(index))
        roi_button.clicked.connect(lambda checked=False, index=camera_index: self.enable_roi_drawing(index))
        clear_roi_button.clicked.connect(lambda checked=False, index=camera_index: self.clear_camera_roi(index))
        button_layout.addWidget(toggle_button)
        button_layout.addWidget(zoom_button)
        button_layout.addWidget(roi_button)
        button_layout.addWidget(clear_roi_button)

        layout.addWidget(video_label, 1)
        layout.addLayout(info_layout)
        layout.addLayout(button_layout)

        self.camera_views.append(video_label)
        self.camera_status_labels.append(status_label)
        self.camera_fps_labels.append(fps_label)
        self.camera_process_fps_labels.append(process_fps_label)
        self.camera_tracking_fps_labels.append(tracking_fps_label)
        self.camera_object_labels.append(object_label)
        self.camera_roi_count_labels.append(roi_count_label)
        self.camera_toggle_buttons.append(toggle_button)
        self.camera_zoom_buttons.append(zoom_button)
        self.camera_roi_buttons.append(roi_button)
        self.camera_clear_roi_buttons.append(clear_roi_button)

        return box

    def showEvent(self, event):
        super().showEvent(event)
        if self.auto_started:
            return
        self.auto_started = True
        QTimer.singleShot(500, self.start_all_cameras)

    def start_all_cameras(self):
        for camera_index in range(CAMERA_COUNT):
            self.start_camera(camera_index)

    def start_camera(self, camera_index):
        if self.capture_threads[camera_index] is not None:
            return

        capture_thread = CaptureThread(camera_index, CAMERA_SOURCES[camera_index])
        process_thread = ProcessThread(camera_index)
        tracking_thread = TrackingThread(camera_index)

        roi = self.camera_roi_rects[camera_index]
        if roi is not None:
            process_thread.set_roi(roi)

        capture_thread.frame_signal.connect(process_thread.set_frame)
        process_thread.processed_signal.connect(tracking_thread.set_processed_frame)
        capture_thread.fps_signal.connect(self.update_camera_fps)
        capture_thread.status_signal.connect(self.update_camera_status)
        process_thread.fps_signal.connect(self.update_process_fps)
        tracking_thread.fps_signal.connect(self.update_tracking_fps)
        tracking_thread.tracked_frame_signal.connect(self.update_camera_frame)
        tracking_thread.tracking_data_signal.connect(self.update_tracking_data)

        process_thread.start()
        tracking_thread.start()
        capture_thread.start()

        self.capture_threads[camera_index] = capture_thread
        self.process_threads[camera_index] = process_thread
        self.tracking_threads[camera_index] = tracking_thread
        self.camera_toggle_buttons[camera_index].setText("Stop")
        self.camera_status_labels[camera_index].setText("Status: Starting")

    def stop_camera(self, camera_index):
        threads = (
            self.capture_threads[camera_index],
            self.process_threads[camera_index],
            self.tracking_threads[camera_index],
        )
        if all(thread is None for thread in threads):
            return

        for thread in threads:
            if thread is not None:
                thread.stop()

        self.capture_threads[camera_index] = None
        self.process_threads[camera_index] = None
        self.tracking_threads[camera_index] = None
        self.camera_connection_alerting[camera_index] = False
        self.camera_toggle_buttons[camera_index].setText("Start")
        self.camera_status_labels[camera_index].setText("Status: Stopped")
        self.camera_fps_labels[camera_index].setText("Capture: 0")
        self.camera_process_fps_labels[camera_index].setText("Process: 0")
        self.camera_tracking_fps_labels[camera_index].setText("Tracking: 0")
        self.camera_object_labels[camera_index].setText("Objects: 0")
        self.camera_roi_count_labels[camera_index].setText("ROI: 0")
        self.update_total_object_count()
        self.camera_views[camera_index].clear()
        self.camera_views[camera_index].setText(
            f"Camera {camera_index + 1}\n{CAMERA_SOURCES[camera_index]}"
        )

    def toggle_camera(self, camera_index):
        if self.capture_threads[camera_index] is None:
            self.start_camera(camera_index)
        else:
            self.stop_camera(camera_index)

    def enable_roi_drawing(self, camera_index):
        self.camera_views[camera_index].enable_roi_drawing()
        self.camera_status_labels[camera_index].setText("Status: Draw ROI")

    def set_camera_roi(self, camera_index, roi):
        self.camera_roi_rects[camera_index] = roi
        process_thread = self.process_threads[camera_index]
        if process_thread is not None:
            process_thread.set_roi(roi)
        tracking_thread = self.tracking_threads[camera_index]
        if tracking_thread is not None:
            tracking_thread.reset_tracks()
        self.event_thread.set_roi(camera_index, roi)
        self.camera_roi_count_labels[camera_index].setText("ROI: 0")
        self.camera_status_labels[camera_index].setText("Status: ROI ready")

    def clear_camera_roi(self, camera_index):
        self.camera_roi_rects[camera_index] = None
        process_thread = self.process_threads[camera_index]
        if process_thread is not None:
            process_thread.clear_roi()
        tracking_thread = self.tracking_threads[camera_index]
        if tracking_thread is not None:
            tracking_thread.reset_tracks()
        self.event_thread.clear_roi(camera_index)
        self.camera_roi_count_labels[camera_index].setText("ROI: 0")
        self.camera_views[camera_index].clear_preview()

    def open_zoom_window(self, camera_index):
        if self.zoom_windows[camera_index] is None:
            self.zoom_windows[camera_index] = CameraZoomWindow(camera_index)
            self.zoom_windows[camera_index].destroyed.connect(
                lambda _, index=camera_index: self.clear_zoom_window(index)
            )
        self.zoom_windows[camera_index].show()
        self.zoom_windows[camera_index].raise_()
        self.zoom_windows[camera_index].activateWindow()

    def clear_zoom_window(self, camera_index):
        self.zoom_windows[camera_index] = None

    def update_camera_frame(self, camera_index, frame):
        roi = self.camera_roi_rects[camera_index]
        display_frame = frame.copy() if roi is not None else frame
        if roi is not None:
            x1, y1, x2, y2 = roi
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 255), 3)
            cv2.putText(
                display_frame,
                "ROI",
                (x1, max(y1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )

        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb_frame.shape
        bytes_per_line = channels * width
        image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        view = self.camera_views[camera_index]
        view.set_frame_shape(display_frame.shape)
        view.setPixmap(pixmap.scaled(view.size(), Qt.KeepAspectRatio, Qt.FastTransformation))

        zoom_window = self.zoom_windows[camera_index]
        if zoom_window is not None:
            zoom_window.update_frame(pixmap)

    def update_camera_fps(self, camera_index, fps):
        self.camera_fps_labels[camera_index].setText(f"Capture: {fps:.1f}")

    def update_process_fps(self, camera_index, fps):
        self.camera_process_fps_labels[camera_index].setText(f"Process: {fps:.1f}")

    def update_tracking_fps(self, camera_index, fps):
        self.camera_tracking_fps_labels[camera_index].setText(f"Tracking: {fps:.1f}")

    def update_camera_status(self, camera_index, status):
        self.camera_status_labels[camera_index].setText(f"Status: {status}")

        if status in ("Reconnect waiting", "Reconnecting"):
            if not self.camera_connection_alerting[camera_index]:
                self.camera_connection_alerting[camera_index] = True
                self.show_alert(f"Camera {camera_index + 1}: reconnect failed, waiting for stream")
            return

        if status == "Playing" and self.camera_connection_alerting[camera_index]:
            self.camera_connection_alerting[camera_index] = False
            self.show_alert(f"Camera {camera_index + 1}: reconnected successfully")

    def update_tracking_data(self, camera_index, tracked_objects):
        tracked_ids = {tracked_object["id"] for tracked_object in tracked_objects}
        self.camera_object_labels[camera_index].setText(f"Objects: {len(tracked_ids)}")
        self.event_thread.set_tracking_data(camera_index, tracked_objects)
        self.update_total_object_count()

    def update_roi_count(self, camera_index, count):
        self.camera_roi_count_labels[camera_index].setText(f"ROI: {count}")

    def show_alert(self, message):
        self.alert_label.setText(f"Alert: {message}")
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.event_log.insertItem(0, f"[{timestamp}] {message}")

    def update_total_object_count(self):
        total = 0
        for label in self.camera_object_labels:
            total += int(label.text().split(": ")[1])
        self.total_object_count_label.setText(f"Total objects: {total}")

    def closeEvent(self, event):
        for camera_index in range(len(self.capture_threads)):
            self.stop_camera(camera_index)
            zoom_window = self.zoom_windows[camera_index]
            if zoom_window is not None:
                zoom_window.close()
        self.event_thread.stop()
        event.accept()
