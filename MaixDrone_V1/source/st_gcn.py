import math
import time

class STGCN_Recognizer:
    def __init__(self, window_size=20, stride=3):
        # --- CẤU HÌNH ST-GCN ---
        self.WINDOW_SIZE = window_size
        self.STRIDE = stride
        self.buffer = []                # Hàng đợi (Queue) chứa chuỗi keypoints
        self.frame_counter = 0
        
        # [REQ] Cấu hình Debounce & Hysteresis (Chống nhòe chuyển động)
        self.PROB_THRESHOLD = 0.85      # Ngưỡng xác suất (Step 5)
        
        # Hit Counter (Bộ đếm kích hoạt)
        self.wave_hit_count = 0
        self.HIT_THRESHOLD = 4          # [NẠP CHẬM] Tăng lên 4: Cần vẫy dứt khoát (~0.4s) mới hiện
        
        # Missing Tolerance (Dung sai mất dấu)
        self.missing_tolerance = 0
        self.MAX_TOLERANCE = 2          # [XẢ NHANH] Giảm xuống 2: Dừng tay là tắt ngay (~0.2s)

    def update(self, keypoints):
        """
        Input: Danh sách keypoints đã lọc nhiễu (Filtered Points)
        Output: Tên hành động (String) hoặc None
        """
        if not keypoints: return None

        # [BƯỚC 2] TIỀN XỬ LÝ & CHUẨN HÓA (Normalization)
        norm_kpts = self._normalize(keypoints)
        if norm_kpts is None: return None

        # [BƯỚC 3] CƠ CHẾ CỬA SỔ TRƯỢT (Sliding Window Buffer)
        self.buffer.append(norm_kpts)
        
        # Duy trì độ dài hàng đợi cố định T=30
        if len(self.buffer) > self.WINDOW_SIZE:
            self.buffer.pop(0)
        
        # Kiểm tra đủ dữ liệu chưa
        if len(self.buffer) < self.WINDOW_SIZE:
            return None

        # Kiểm tra bước nhảy (Stride) - Chỉ chạy Inference mỗi 5 frame
        self.frame_counter += 1
        if self.frame_counter % self.STRIDE != 0:
            # Trả về trạng thái hiện tại trong lúc chờ inference tiếp theo
            return "Vay Tay Phai" if self.wave_hit_count >= self.HIT_THRESHOLD else None

        # [BƯỚC 4] THỰC THI ST-GCN (Core Inference)
        # Input Tensor: (1, 30, 17, 2) -> Batch, Time, Joints, Coords
        action_id, prob = self._inference(self.buffer)

        # [BƯỚC 5] HẬU XỬ LÝ (Debounce & Hysteresis Logic)
        # Class 1: Waving (Vay Tay Phai)
        is_waving = (prob > self.PROB_THRESHOLD and action_id == 1)

        if is_waving:
            # [HIT COUNTER] Tăng bộ đếm khi phát hiện đúng
            self.wave_hit_count += 1
            # [TOLERANCE] Nạp đầy dung sai (Reset bộ đếm lùi)
            self.missing_tolerance = self.MAX_TOLERANCE
        else:
            # [MISSING TOLERANCE] Xử lý khi mất dấu (Motion Blur / Che khuất)
            if self.missing_tolerance > 0:
                self.missing_tolerance -= 1
                # Vẫn giữ nguyên wave_hit_count để duy trì trạng thái
            else:
                # Chỉ reset khi đã hết dung sai
                self.wave_hit_count = 0

        # Output kết quả dựa trên ngưỡng kích hoạt
        if self.wave_hit_count >= self.HIT_THRESHOLD:
            return "Vay Tay Phai"
        
        return None

    def _normalize(self, kpts):
        """
        Chuẩn hóa tọa độ về khoảng [-1, 1] dựa trên trọng tâm cơ thể.
        """
        # Parse keypoints (giả sử input là list phẳng [x, y, c, ...])
        # Cần convert sang list các tuple (x, y)
        points = []
        stride = 3 if len(kpts) % 3 == 0 else 2
        for i in range(0, len(kpts), stride):
            points.append((kpts[i], kpts[i+1]))
            
        if len(points) < 13: return None # Thiếu điểm quan trọng

        # 1. Trọng tâm hóa (Centering)
        # Lấy trung điểm hông (11, 12) làm gốc (0,0)
        # Nếu không có hông, dùng trung điểm vai (5, 6)
        root_x = (points[11][0] + points[12][0]) / 2
        root_y = (points[11][1] + points[12][1]) / 2
        
        if root_x == 0 or root_y == 0:
            root_x = (points[5][0] + points[6][0]) / 2
            root_y = (points[5][1] + points[6][1]) / 2

        # 2. Scale (Chia cho chiều cao khung xương)
        # Chiều cao = Khoảng cách từ Vai đến Hông (Torso Length)
        # Hoặc khoảng cách Vai - Vai nếu Torso không rõ
        scale = math.sqrt((points[5][0] - points[11][0])**2 + (points[5][1] - points[11][1])**2)
        if scale < 10: scale = 100.0 # Tránh chia cho 0

        norm_points = []
        for px, py in points:
            nx = (px - root_x) / scale
            ny = (py - root_y) / scale
            norm_points.append((nx, ny))
            
        return norm_points

    def _inference(self, buffer):
        """
        Mô phỏng lớp Spatial-Temporal Conv.
        Nếu có model .mud, ta sẽ gọi: self.model.run(buffer)
        Ở đây ta dùng thuật toán phân tích phương sai để mô phỏng logic ST-GCN.
        """
        # Class 0: Standing, 1: Waving
        
        # Lấy dữ liệu chuỗi thời gian của Cổ tay phải (Index 10) và Khuỷu tay phải (Index 8)
        wrist_x_seq = [frame[10][0] for frame in buffer]
        wrist_y_seq = [frame[10][1] for frame in buffer]
        elbow_x_seq = [frame[8][0] for frame in buffer]
        
        # --- SPATIAL ANALYSIS (Không gian) ---
        # [UPDATE] Sử dụng Toạ độ tương đối (Relative Coordinates)
        # Thay vì tính góc (dễ sai do 2D), ta kiểm tra vị trí Cổ tay so với Vai.
        last_frame = buffer[-1]
        
        # Index: 6: R-Sho, 10: R-Wri
        p_sho = last_frame[6]
        p_wri = last_frame[10]
        
        # Điều kiện: Cổ tay phải (10) cao hơn ngưỡng cho phép
        # Trong hệ toạ độ chuẩn hóa (Normalized): Gốc (0,0) tại Hông, Vai ~ -1.0.
        # Ta cho phép tay thấp hơn vai một chút (0.65 * Torso Length) để bắt được vẫy tay thấp.
        threshold_y = p_sho[1] + 0.65
        
        # Y trục hướng xuống -> Lớn hơn nghĩa là thấp hơn (buông thõng)
        if p_wri[1] > threshold_y:
            return 0, 0.99 # Chắc chắn là Standing

        # --- TEMPORAL ANALYSIS (Thời gian) ---
        # Tính phương sai (Variance) của tọa độ X cổ tay trong 30 frame
        # Vẫy tay -> X biến thiên mạnh (Variance cao)
        # Đứng yên giơ tay -> X biến thiên ít (Variance thấp)
        
        def variance(data):
            n = len(data)
            if n < 2: return 0
            mean = sum(data) / n
            return sum((x - mean) ** 2 for x in data) / (n - 1)

        var_x = variance(wrist_x_seq)
        
        # Tính tần số dao động (Zero-crossing rate của vận tốc)
        # Để phân biệt vẫy tay với việc di chuyển tay một lần
        velocities = [wrist_x_seq[i] - wrist_x_seq[i-1] for i in range(1, len(wrist_x_seq))]
        
        # [REQ] Lọc bỏ vận tốc rác (jitter) trước khi đếm đảo chiều
        clean_velocities = [v for v in velocities if abs(v) > 0.03]
        
        zero_crossings = 0
        for i in range(1, len(clean_velocities)):
            if clean_velocities[i] * clean_velocities[i-1] < 0:
                zero_crossings += 1

        # --- SOFTMAX SIMULATION ---
        # [REQ] Giảm ngưỡng Variance (>0.015) và số lần đảo chiều (>=2) để nhạy hơn
        if var_x > 0.015 and zero_crossings >= 2:
            # Tính xác suất giả lập dựa trên độ mạnh của tín hiệu
            prob = min(0.99, 0.7 + var_x * 5) 
            return 1, prob # Class 1: Waving
        else:
            return 0, 0.8 # Class 0: Standing