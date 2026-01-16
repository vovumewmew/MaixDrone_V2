# 🚁 MaixDrone V2: Hybrid Pose Estimation System

> **Hệ thống nhận diện dáng người lai ghép (Hybrid Intelligence) tối ưu cho chip RISC-V (MaixCam).**

![Status](https://img.shields.io/badge/Status-Active-success)
![Platform](https://img.shields.io/badge/Platform-MaixCam%20(LicheeRV)-orange)
![Python](https://img.shields.io/badge/Python-3.x-blue)

## 📖 Giới thiệu
Dự án này giải quyết bài toán Pose Estimation (nhận diện xương khớp) trên thiết bị biên (Edge Device) có tài nguyên hạn chế. Thay vì phụ thuộc hoàn toàn vào AI (nặng nề), hệ thống sử dụng kiến trúc **Hybrid**:
*   **AI (YOLOv8-Nano):** Chỉ chạy ở độ phân giải thấp (`320x224`) để lấy toạ độ thô.
*   **Logic (Python):** Sử dụng thuật toán lọc `OneEuroFilter` và `Kinematic Constraints` để làm mịn, sửa lỗi và bù đắp chi tiết.

## 🚀 Tính năng nổi bật

### 1. Chế độ Cân Bằng (Balanced Mode)
- **Input:** 320x224 (Letterbox) - Tối ưu cho NPU.
- **FPS:** Ổn định ở mức 25-30 FPS.
- **Hiển thị:** Lọc bỏ nhiễu nhưng vẫn giữ được các điểm khớp tay/chân khi ở xa hoặc mờ.

### 2. Bộ lọc thông minh (Smart Filters)
- **One Euro Filter:** Chống rung điểm khi đứng yên, bám sát khi chuyển động nhanh.
- **Anatomy Constraints:** 
  - Tự động cắt bỏ các điểm xương nối sai (ví dụ: tay nối xuống chân).
  - Giới hạn độ dài xương theo tỷ lệ giải phẫu học (2.0x).
- **Zone Check:** Loại bỏ các điểm "ma" (Ghost points) xuất hiện trên tường hoặc nền nhà.

### 3. Streaming Server
- Tích hợp MJPEG Streamer qua Socket.
- Xem trực tiếp kết quả qua trình duyệt web (`http://<IP>:80`).

## 🛠 Cài đặt & Chạy

### Yêu cầu phần cứng
- Thiết bị: Sipeed MaixCam (hoặc các board LicheeRV tương đương).
- Kết nối: Wifi (để stream video).

### Chạy chương trình
1. Copy toàn bộ source code vào thẻ nhớ hoặc bộ nhớ trong của MaixCam.
2. Mở Terminal (SSH hoặc Serial).
3. Chạy lệnh:
   ```bash
   python main.py
   ```
4. Mở trình duyệt truy cập: `http://<IP_CUA_MAIXCAM>:80`

## 📂 Cấu trúc thư mục
```
Du_An_Maix_V2/
├── main.py             # File chính điều phối luồng chạy
├── GEMINI.md           # Tài liệu kỹ thuật chi tiết cho AI Assistant
├── source/
│   ├── ai.py           # Xử lý Model YOLOv8
│   ├── camera.py       # Quản lý Camera (RGB888)
│   ├── postprocess.py  # Các bộ lọc (OneEuro, Kinematic, Anatomy)
│   ├── tracker.py      # Theo dõi đối tượng (Tracking)
│   ├── stream.py       # Server truyền hình ảnh
│   └── ui.py           # Vẽ giao diện (HUD)
└── models/             # Chứa file model .cvimodel (không push lên git)
```

## ⚙️ Cấu hình (Config)
Các tham số chính có thể chỉnh trong `GEMINI.md` hoặc code:
- `CONF_THRESHOLD = 0.5`: Ngưỡng nhận diện của AI.
- `VIS_THRESHOLD = 0.35`: Ngưỡng hiển thị lên màn hình.
- `SKIP_FRAMES = 2`: Tỷ lệ bỏ frame để giảm tải CPU.

## 🤝 Đóng góp
Dự án được phát triển bởi **Vo Vu**. Mọi đóng góp xin vui lòng tạo Pull Request.

---
*Lưu ý: Đây là phiên bản V2, tập trung vào sự ổn định và cân bằng giữa Tốc độ/Độ chính xác.*