from pathlib import Path

# Đường dẫn gốc dùng chung trong project.
BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets"
MODEL_DIR = ASSETS_DIR / "models"

# Cấu hình cửa sổ giao diện chính.
APP_TITLE = "AI Camera Monitoring System"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 800

# Cấu hình nguồn camera/video. Khi có camera thật có thể thay bằng URL RTSP.
CAMERA_COUNT = 4
CAMERA_SOURCES = [
    "rtsp://127.0.0.1:8554/camera_1",
    "rtsp://127.0.0.1:8554/camera_2",
    "rtsp://127.0.0.1:8554/camera_3",
    "rtsp://127.0.0.1:8554/camera_4",
]
CAMERA_RECONNECT_SECONDS = 5

# Cấu hình YOLO detect/tracking.
YOLO_MODEL_NAME = "yolo26n.pt"
YOLO_MODEL_PATH = str(MODEL_DIR / YOLO_MODEL_NAME)
# YOLO_TRACKER = "bytetrack.yaml"
YOLO_TRACKER = "botsort.yaml"
YOLO_IMAGE_SIZE = 320
CONFIDENCE_THRESHOLD = 0.25
IOU_THRESHOLD = 0.45
PERSON_CLASS_ID = 0
YOLO_PERSON_CLASSES = [PERSON_CLASS_ID]

# Cấu hình thời gian nghỉ của các thread, đơn vị milliseconds.
DEFAULT_FRAME_DELAY_MS = 33
PROCESS_SLEEP_MS = 10
TRACKING_SLEEP_MS = 10

# Cấu hình lọc và hiển thị tracking.
TRAJECTORY_LENGTH = 30
MIN_TRACK_BOX_AREA = 1200

# Cấu hình cảnh báo trong vùng ROI.
ROI_LOITERING_SECONDS = 10
ROI_MISSING_GRACE_SECONDS = 2
ROI_CROWDED_THRESHOLD = 5
