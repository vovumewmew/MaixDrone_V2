# 🚁 PROJECT:HYBRID POSE ESTIMATION SYSTEM

## 1. TỔNG QUAN HỆ THỐNG (System Overview)
* **Thiết bị (Hardware):** MaixCam (Lichee/RV - RISC-V Architecture).
* **Mục tiêu:** Nhận diện dáng người (Pose Estimation)
* **Ràng buộc cốt lõi:**
    * Tài nguyên CPU/NPU hạn chế (Low Power).
    * Yêu cầu FPS ổn định (target 25-30 FPS).
    * Input Camera cố định: `320x224` (tối ưu cho NPU).

## 2. KIẾN TRÚC PHẦN MỀM (Software Architecture)
Hệ thống sử dụng kiến trúc **"Hybrid Intelligence"** (Lai ghép), chuyển tải gánh nặng tính toán từ Mạng Neural sang Logic Thuật toán (Python) để giảm tham số và tăng tốc độ.

### Luồng dữ liệu (Data Flow):
`Camera` -> `Resize (Full Frame)` -> `YOLOv8-Nano` -> `Post-Process (Logic)` -> `Tracker (State)` -> `UI/Control`

### Các Module chính:
| File | Vai trò | Ghi chú quan trọng |
| :--- | :--- | :--- |
| **`main.py`** | Nhạc trưởng (Orchestrator) | Quản lý vòng lặp, `gc.collect()` định kỳ, điều phối nhịp Skip Frames. |
| **`source/ai.py`** | Vision Engine | Luôn resize về `320x224` để đảm bảo toạ độ chính xác tuyệt đối. |
| **`source/postprocess.py`** | Logic Brain (Sửa lỗi) | Chứa thuật toán Deadzone, EMA, và Ràng buộc xương (Bone Constraints). |
| **`source/tracker.py`** | State Memory (Bộ nhớ) | Lưu trạng thái frame trước.|
| **`source/ui.py`** | Visualization | Vẽ an toàn. Kiểm tra biên màn hình và độ tin cậy trước khi `draw`. |

## 3. CÁC QUY TẮC CỐT LÕI (Core Rules - DO NOT BREAK)

### 🔴 NGHIÊM CẤM (Don'ts):
2.  **KHÔNG dùng Affine Transform:** Quá nặng cho chip RISC-V và gây sai số vị trí.
4.  **KHÔNG vẽ điểm có `conf < 0.35`:** (Cập nhật: Chế độ Cân Bằng) Do ảnh input nhỏ (320px), độ tin cậy của khớp tay/chân thường thấp. Đặt quá cao sẽ mất chi tiết.

### 🟢 KHUYẾN KHÍCH (Do's):
1.  **Letterbox Resize:** Luôn giữ tỷ lệ khung hình khi resize về `320x224` để người không bị méo.
2.  **Hard Constraints (Ràng buộc cứng):**
    * Điểm phải nằm trong Bounding Box.
    * Độ dài xương tay/chân không được vượt quá ngưỡng giải phẫu học.
3.  **Stateful Tracking:** Sử dụng kết quả của frame trước để điền vào chỗ trống nếu AI bị skip (Hybrid Mode).
4.  **Defensive Drawing:** Luôn kiểm tra `if 0 < x < width` trước khi vẽ để tránh Crash.

## 4. THUẬT TOÁN ĐẶC THÙ ĐANG SỬ DỤNG

### A. Bone Integrity Check (Kiểm tra toàn vẹn xương)
* *Mục đích:* Chống lỗi "tay cao su" (tay dài bất thường).
* *Logic:* Sử dụng **Tỷ lệ Giải phẫu (Anatomical Ratios)** dựa trên chiều cao Box.
    * Nếu độ dài > 2.0 lần chuẩn -> **XÓA BỎ** (Coi là nhiễu/nối sai).
    * Nếu độ dài sai lệch ít -> Co kéo về vị trí hợp lý.

### B. Adaptive Deadzone (Vùng chết thích ứng)
* *Mục đích:* Chống rung điểm khi đứng yên.
* *Logic:* Nếu $\Delta(pos) < 5px$ -> Coi như đứng yên (giữ vị trí cũ). Nếu $\Delta > 5px$ -> Áp dụng EMA để di chuyển mượt.

### C. Geometric Filtering (Lọc hình học)
* *Mục đích:* Loại bỏ điểm ảo giác (Hallucination) trên tường/nền và các tư thế vô lý.
* *Logic:* 
    * **Box Margin:** Loại bỏ Keypoint nếu nó nằm ngoài Bounding Box mở rộng.
    * **Zone Constraint:** Đầu không thể nằm dưới chân (khi đứng). Cổ tay không thể nằm dưới gót chân.
    * **Edge Penalty:** Phạt nặng các điểm nằm sát mép ảnh (nơi AI hay đoán mò).

## 5. THAM SỐ CẤU HÌNH CHUẨN (Standard Config)
```python
CONF_THRESHOLD = 0.5    # Ngưỡng detect của YOLO
VIS_THRESHOLD = 0.35    # Ngưỡng để vẽ lên màn hình (Chế độ Cân Bằng)
SKIP_FRAMES = 2         # Tỷ lệ: 1 Frame AI / 2 Frame Tracker
INPUT_SIZE = (320, 224) # Kích thước cứng của Model