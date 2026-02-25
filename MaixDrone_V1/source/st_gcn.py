import math
import time

class STGCN_Recognizer:
    def __init__(self, window_size=30, stride=5):
        # --- CẤU HÌNH ST-GCN ---
        self.WINDOW_SIZE = window_size  # T=30 frames
        self.STRIDE = stride            # Inference mỗi 5 frames
        self.buffer = []                # Hàng đợi (Queue) chứa chuỗi keypoints
        self.frame_counter = 0
        
        # Trạng thái đầu ra
        self.last_action = "Standing"
        self.consecutive_count = 0      # Bộ đếm xác nhận (Step 5)
        self.CONFIRM_THRESHOLD = 3      # Cần 3 lần detect liên tiếp để chốt
        self.PROB_THRESHOLD = 0.85      # Ngưỡng xác suất (Step 5)

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
            return self.last_action if self.consecutive_count >= self.CONFIRM_THRESHOLD else None

        # [BƯỚC 4] THỰC THI ST-GCN (Core Inference)
        # Input Tensor: (1, 30, 17, 2) -> Batch, Time, Joints, Coords
        action_id, prob = self._inference(self.buffer)

        # [BƯỚC 5] HẬU XỬ LÝ & KÍCH HOẠT (Post-processing)
        final_action = None
        
        # 1. Thresholding
        if prob > self.PROB_THRESHOLD:
            # 2. Counter (Bộ đếm xác nhận)
            if action_id == 1: # Class 1: Waving
                detected_action = "Vay Tay Phai"
            elif action_id == 2: # Class 2: Walking (Ví dụ)
                detected_action = "Di Bo"
            else:
                detected_action = "Standing"

            if detected_action == self.last_action:
                self.consecutive_count += 1
            else:
                self.last_action = detected_action
                self.consecutive_count = 1
            
            # Chỉ trả về kết quả nếu đã duy trì đủ lâu
            if self.consecutive_count >= self.CONFIRM_THRESHOLD:
                final_action = self.last_action
        else:
            # Nếu xác suất thấp, reset bộ đếm dần dần
            self.consecutive_count = max(0, self.consecutive_count - 1)

        return final_action

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
        # Ta cho phép tay thấp hơn vai một chút (0.3 * Torso Length) để bắt được vẫy tay thấp.
        threshold_y = p_sho[1] + 0.3
        
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
        zero_crossings = 0
        for i in range(1, len(velocities)):
            if velocities[i] * velocities[i-1] < 0:
                zero_crossings += 1

        # --- SOFTMAX SIMULATION ---
        # Logic: Variance cao (>0.02 sau khi norm) VÀ có đảo chiều (>2 lần trong 30 frame)
        if var_x > 0.02 and zero_crossings >= 3:
            # Tính xác suất giả lập dựa trên độ mạnh của tín hiệu
            prob = min(0.99, 0.7 + var_x * 5) 
            return 1, prob # Class 1: Waving
        else:
            return 0, 0.8 # Class 0: Standing