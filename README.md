# AI Camera Monitoring

Ứng dụng giám sát AI Camera bằng Python + PyQt5, hỗ trợ 4 camera, RTSP giả lập, YOLO26, ByteTrack, ROI và cảnh báo realtime.

## Tính năng chính

- Giao diện PyQt5 hiển thị 4 camera dạng lưới 2x2.
- Đọc video file hoặc luồng RTSP realtime bằng OpenCV.
- Tự reconnect khi mất kết nối camera.
- Tạo luồng RTSP giả lập từ video bằng FFmpeg + MediaMTX.
- Vẽ ROI trên từng camera.
- Chỉ detect người trong vùng ROI đã vẽ.
- YOLO `model.track()` + ByteTrack chạy trong `ProcessThread`.
- `TrackingThread` hiển thị bbox, Track ID, tâm object và trajectory.
- `EventThread` đếm người trong ROI và sinh cảnh báo realtime.
- Cảnh báo người đứng lâu trong ROI.
- Cảnh báo đông người trong ROI.

## Cấu trúc project

```text
ai_camera_monitoring/
├── main.py
├── requirements.txt
├── ui/
│   └── main_window.py
├── threads/
│   ├── capture_thread.py
│   ├── process_thread.py
│   ├── tracking_thread.py
│   └── event_thread.py
├── models/
│   └── yolo_detector.py
├── utils/
│   ├── config.py
│   └── fps.py
└── assets/
    ├── videos/
    └── models/

rtsp_server.py
mediamtx.yml
AI_Camera_Monitoring_Report.md
```

## Cài đặt

Tạo môi trường ảo:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Cài dependencies:

```bash
pip install -r ai_camera_monitoring/requirements.txt
```

Cài MediaMTX nếu chưa có:

```bash
brew install mediamtx
```

## Chuẩn bị assets

Đặt video test vào:

```text
ai_camera_monitoring/assets/videos/
```

Tên mặc định:

```text
camera_1.mp4
camera_2.mp4
camera_3.mp4
camera_4.mp4
```

Đặt model YOLO vào:

```text
ai_camera_monitoring/assets/models/
```

Tên mặc định trong config:

```text
yolo26s.pt
```

## Chạy RTSP giả lập

Chạy 4 camera:

```bash
python3 rtsp_server.py --count 4
```

Chạy 2 camera:

```bash
python3 rtsp_server.py --count 2
```

Nếu đã chạy 2 camera và muốn bật thêm camera 3, 4 ở terminal khác:

```bash
python3 rtsp_server.py --publish-only --start-index 3 --count 2
```

Các URL RTSP mặc định:

```text
rtsp://127.0.0.1:8554/camera_1
rtsp://127.0.0.1:8554/camera_2
rtsp://127.0.0.1:8554/camera_3
rtsp://127.0.0.1:8554/camera_4
```


## Chạy ứng dụng


```bash
python ai_camera_monitoring/main.py
```


## Luồng xử lý

```text
RTSP / Video file
   ↓
CaptureThread
   ↓
ProcessThread
   ↓
TrackingThread
   ↓
Main UI Thread
```

Luồng cảnh báo:

```text
TrackingThread
   ↓
tracking_data_signal
   ↓
EventThread
   ↓
roi_count_signal / alert_signal
   ↓
Main UI Thread
```

## Cấu hình chính

Các cấu hình nằm trong:

```text
ai_camera_monitoring/utils/config.py
```

Một số cấu hình quan trọng:

```python
CAMERA_COUNT = 4
YOLO_MODEL_NAME = "yolo26s.pt"
YOLO_TRACKER = "bytetrack.yaml"
ROI_LOITERING_SECONDS = 10
ROI_CROWDED_THRESHOLD = 5
```

## Ghi chú

- File video `.mp4` và model `.pt` không được commit lên Git để tránh repo quá nặng.
- `bytetrack.yaml` là tracker config mặc định có sẵn trong Ultralytics.
- Báo cáo chi tiết nằm trong `AI_Camera_Monitoring_Report.md`.
