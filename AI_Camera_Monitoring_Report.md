# Báo cáo AI Camera Monitoring

## 1. Mục tiêu

Project xây dựng ứng dụng giám sát AI Camera bằng Python và PyQt5 nhằm thực hành:

- Đa luồng với `QThread`.
- Truyền dữ liệu bằng signal-slot.
- Đọc video/RTSP realtime.
- Detect và tracking người bằng YOLO26 + ByteTrack.
- Vẽ vùng ROI, đếm người trong vùng và sinh cảnh báo.

Ứng dụng mô phỏng hệ thống giám sát gồm 4 camera. Camera thật được giả lập bằng video file hoặc luồng RTSP local.

---

## 2. Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Ngôn ngữ | Python |
| Giao diện | PyQt5 |
| Đa luồng | QThread |
| Xử lý video | OpenCV |
| AI detection | YOLO26 |
| Tracking | YOLO `model.track()` + ByteTrack |
| RTSP giả lập | MediaMTX + FFmpeg |

---

## 3. Cấu trúc project

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
```

---

## 4. Luồng RTSP giả lập camera

Do chưa dùng camera thật, project dùng video file để giả lập luồng camera RTSP.

Luồng tạo RTSP:

```text
Video file (.mp4)
   ↓
FFmpeg phát lặp liên tục
   ↓
MediaMTX RTSP server
   ↓
rtsp://127.0.0.1:8554/camera_1
rtsp://127.0.0.1:8554/camera_2
rtsp://127.0.0.1:8554/camera_3
rtsp://127.0.0.1:8554/camera_4
```

Chạy server 4 camera:

```bash
python3 rtsp_server.py --count 4
```

Chạy 2 camera:

```bash
python3 rtsp_server.py --count 2
```

chạy thêm 2 camera:

```bash
python3 rtsp_server.py --publish-only --start-index 3 --count 2
```
---

## 5. Luồng xử lý trong ứng dụng

Mỗi camera có một nhóm thread riêng để tránh treo giao diện.

Luồng hiển thị và tracking chính:

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

Luồng xử lý cảnh báo:

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

`ProcessThread` nhận frame từ `CaptureThread`, crop vùng ROI rồi chạy YOLO `model.track()` + ByteTrack trong vùng đã vẽ. `TrackingThread` nhận bbox và Track ID từ `ProcessThread`, cập nhật trajectory, vẽ overlay và tạo frame hiển thị cuối cùng.

Với 4 camera:

```text
Camera 1 → CaptureThread → ProcessThread → TrackingThread → UI + EventThread
Camera 2 → CaptureThread → ProcessThread → TrackingThread → UI + EventThread
Camera 3 → CaptureThread → ProcessThread → TrackingThread → UI + EventThread
Camera 4 → CaptureThread → ProcessThread → TrackingThread → UI + EventThread
```

---

## 6. Các thread chính

### CaptureThread

Chức năng:

- Mở video file hoặc URL RTSP bằng OpenCV.
- Đọc frame realtime.
- Tự reconnect khi mất luồng.
- Gửi frame sang thread khác bằng signal.
- Tính `Capture FPS`.

Luồng:

```text
cv2.VideoCapture(source)
   ↓
cap.read()
   ↓
frame_signal.emit(camera_index, frame)
```

### ProcessThread

Chức năng theo yêu cầu:

- Nhận frame từ `CaptureThread`.
- Chuyển frame sang grayscale hoặc blur.
- Detect người bằng YOLO/OpenCV.
- Vẽ bounding box.
- Tính số lượng người trong frame.

Trong project hiện tại:

- `ProcessThread` nhận frame từ `CaptureThread`.
- Nếu chưa có ROI thì không detect.
- Nếu đã có ROI thì crop đúng vùng ROI từ frame gốc.
- YOLO `model.track()` + ByteTrack chỉ chạy trên ảnh crop ROI, không detect phần ngoài vùng vẽ.
- Kết quả bbox và Track ID được đổi lại về tọa độ frame gốc rồi gửi sang `TrackingThread`.

### TrackingThread

Chức năng theo yêu cầu:

- Nhận kết quả tracking từ `ProcessThread`.
- Cập nhật trajectory theo Track ID đã có.
- Hiển thị bounding box, Track ID, tâm object và trajectory.

Trong project hiện tại:

- Nhận frame, bbox và Track ID từ `ProcessThread`.
- Không tự gán ID; Track ID được ByteTrack tạo trong `ProcessThread`.
- Lưu danh sách tâm object gần nhất theo từng Track ID để vẽ trajectory.
- Tính số lượng người trong frame từ danh sách tracked object.
- Gửi frame cuối cùng về UI.
- Tính `Process FPS`, tức FPS của output sau tracking.

Luồng tracking:

```text
Frame + bbox + Track ID từ ProcessThread
   ↓
Sử dụng Track ID từ ByteTrack
   ↓
Cập nhật trajectory
   ↓
Draw bbox / ID / trajectory
   ↓
Emit frame ra UI
```

### EventThread

Chức năng:

- Nhận dữ liệu tracking từ `TrackingThread`.
- Kiểm tra người có nằm trong vùng ROI hay không.
- Đếm số người trong ROI.
- Phát hiện người đứng quá lâu trong vùng ROI.
- Phát hiện nhiều người trong cùng khu vực.
- Sinh event cảnh báo realtime.
- Gửi số người trong ROI và cảnh báo về UI bằng signal.

Luồng event:

```text
tracking_data_signal
   ↓
EventThread
   ↓
Lấy Track ID và tâm object
   ↓
Kiểm tra tâm object có nằm trong ROI
   ↓
Đếm số người trong ROI
   ↓
Kiểm tra thời gian đứng trong ROI
   ↓
roi_count_signal / alert_signal
   ↓
Main UI Thread
```

---

## 7. Giao tiếp giữa các thread

Project dùng signal-slot và `latest_frame` buffer.

Ví dụ signal:

```python
frame_signal = pyqtSignal(int, object)
fps_signal = pyqtSignal(int, float)
tracked_frame_signal = pyqtSignal(int, object)
tracking_data_signal = pyqtSignal(int, list)
roi_count_signal = pyqtSignal(int, int)
alert_signal = pyqtSignal(str)
```

Frame mới nhất được lưu bằng `QMutex` để tránh lỗi khi nhiều thread cùng truy cập:

```python
with QMutexLocker(self.mutex):
    self.latest_frame = frame
```

Khi thread xử lý lấy frame ra, `latest_frame` được đặt lại `None`. Cách này giúp không bị dồn nhiều frame cũ, giảm độ trễ realtime.

---

## 8. ROI và cảnh báo

Mỗi camera có các nút:

```text
Start | Zoom | Draw ROI | Clear ROI
```

Cách hoạt động:

1. Người dùng bấm `Draw ROI`.
2. Kéo chuột để vẽ vùng cần theo dõi.
3. ROI được lưu theo tọa độ frame gốc.
4. YOLO + ByteTrack chỉ xử lý người nằm trong ROI.
5. `EventThread` đếm số người trong ROI.
6. `EventThread` cảnh báo nếu người đứng trong ROI quá 10 giây.
7. `EventThread` cảnh báo nếu số người trong ROI lớn hơn 5.

Cấu hình:

```python
ROI_LOITERING_SECONDS = 10
ROI_CROWDED_THRESHOLD = 5
```

Ví dụ cảnh báo:

```text
Camera 1: Track ID 5 stayed in ROI over 10s
Camera 1: ROI crowded 6/5 people
```

---

## 9. Giao diện

Giao diện gồm:

- 4 camera dạng lưới 2x2.
- Tự động kết nối camera khi mở app.
- Mỗi camera hiển thị:
  - Video realtime.
  - Capture FPS.
  - Process FPS.
  - Objects.
  - ROI count.
  - Start/Stop, Zoom, Draw ROI, Clear ROI.
- Panel bên phải hiển thị:
  - Tổng số object.
  - Cảnh báo hiện tại.
  - Lịch sử cảnh báo.

---

## 10. Kết quả đạt được

- Đọc được video file và luồng RTSP giả lập.
- Hỗ trợ 4 camera.
- Tự reconnect khi mất luồng.
- Hiển thị Capture FPS và Process FPS.
- Detect người bằng YOLO26.
- Tracking người bằng ByteTrack và gán ID.
- Vẽ bounding box, tâm object và trajectory.
- Vẽ ROI trên từng camera.
- Chỉ checking người trong ROI khi đã vẽ vùng.
- Tách riêng `EventThread` để xử lý ROI và cảnh báo.
- Đếm người trong ROI bằng `EventThread`.
- Cảnh báo người đứng lâu trong ROI.
- Cảnh báo đông người trong ROI.
- Hiển thị lịch sử cảnh báo.

---

## 11. Hạn chế và hướng phát triển

Hạn chế:

- Track ID vẫn có thể đổi khi người bị che khuất lâu, ra khỏi ROI hoặc đứng quá gần nhau.
- Chưa lưu cảnh báo ra file hoặc database.
- Chưa test với camera RTSP thật.

Hướng phát triển:

- Lưu alert history ra file/database.
- Hỗ trợ nhiều ROI trên một camera.
- Tối ưu inference bằng GPU.
- Kết nối camera RTSP thật.

---

## 12. Kết luận

Project đã xây dựng được ứng dụng AI Camera Monitoring sử dụng PyQt5 đa luồng. Hệ thống có thể đọc video/RTSP realtime, tracking người bằng YOLO26 + ByteTrack, vẽ ROI, đếm người trong vùng và sinh cảnh báo realtime.

Qua project này có thể hiểu rõ hơn về `QThread`, signal-slot, giao tiếp dữ liệu giữa các thread và cách xây dựng pipeline xử lý video realtime trong PyQt5.
