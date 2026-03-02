from maix import nn, image
import math # [NEW] Cần dùng math để tính khoảng cách xương
import config # Import config để lấy KEYPOINT_THRESHOLD
import time # [NEW] Để kiểm soát spam log

class AIEngine:
    def __init__(self, model_path, conf_threshold):
        self.model_path = model_path
        self.threshold = conf_threshold
        self.model = None
        self.input_w = 0 # [AUTO] Sẽ tự cập nhật theo Model
        self.input_h = 0 # [AUTO] Sẽ tự cập nhật theo Model
        self.first_run = True # [DEBUG] Biến cờ để chỉ in log 1 lần
        self.last_warning_time = 0 # [DEBUG] Chống spam cảnh báo

    def load(self):
        try:
            print(f"🧠 Loading Model: {self.model_path}")
            
            # [AUTO-DETECT] Tự động chọn class phù hợp với phiên bản YOLO
            path_lower = self.model_path.lower()
            # [UPDATE] Loại bỏ YOLOv5, tập trung vào YOLO11. YOLOv8 là phụ.
            if "yolov8" in path_lower:
                self.model = nn.YOLOv8(self.model_path, dual_buff=True)
            else:
                # Mặc định là YOLO11 (cho cả yolo11n, yolo11s...)
                self.model = nn.YOLO11(self.model_path, dual_buff=True)
            
            # [NEW] Tự động lấy kích thước input từ Model
            self.input_w = self.model.input_width()
            self.input_h = self.model.input_height()
            print(f"📏 Model Input Size: {self.input_w}x{self.input_h}")
            
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def process(self, img_hd):
        if not self.model: return img_hd, []
        
        results = []
        
        try:
            # --- GIAI ĐOẠN 1: TÌM NGƯỜI (GLOBAL DETECTION) ---
            
            # [PERFORMANCE] FAST RESIZE STRATEGY (Thay thế Letterbox)
            # Thay vì tạo ảnh nền đen và padding (tốn RAM/CPU), ta resize thẳng.
            # Chấp nhận méo hình dọc nhẹ (~6%) để đổi lấy tốc độ.
            
            # 1. Resize ảnh đầu vào (nếu cần)
            if img_hd.width() != self.input_w or img_hd.height() != self.input_h:
                img_input = img_hd.resize(self.input_w, self.input_h)
            else:
                img_input = img_hd

            # 2. Tính tỷ lệ hồi quy (Mapping Scale)
            # Dùng để map toạ độ từ Model (320x224) ngược về Camera (320x240)
            scale_x = img_hd.width() / self.input_w
            scale_y = img_hd.height() / self.input_h

            if self.first_run:
                print(f"🚀 [PERFORMANCE MODE] Direct Resize Activated: {scale_x:.2f}x{scale_y:.2f}")
                self.first_run = False

            # Chạy Model lần 1 để lấy Box
            # [FIX] Thêm keypoint_th để NPU không lọc bỏ điểm xương quá sớm
            # Dùng config.KEYPOINT_THRESHOLD (0.15) để bắt được cả điểm mờ
            
            # [UPDATE] Đã loại bỏ YOLOv5, nên luôn gọi hàm detect chuẩn của YOLO11/8
            objs = self.model.detect(img_input, conf_th=self.threshold, iou_th=0.45, keypoint_th=config.KEYPOINT_THRESHOLD)
            
            for obj in objs:
                # Map Box gốc từ YOLO (Nhân với scale thay vì chia ratio)
                bx = obj.x * scale_x
                by = obj.y * scale_y
                bw = obj.w * scale_x
                bh = obj.h * scale_y

                # [PADDING] Mở rộng Box để bao quát tay giơ cao
                pad_w_val = bw * 0.25  # Mở rộng chiều ngang 10%
                pad_h_val = bh * 0.25  # [HACK] Mở rộng chiều dọc lên hẳn 25%

                # Tùy chỉnh dịch tâm Box lên phía trên một chút (để hứng cái tay)
                bx -= pad_w_val / 2
                by -= pad_h_val * 0.7  # [HACK] Dịch phần lớn phần đệm lên trên đầu
                bw += pad_w_val
                bh += pad_h_val

                # Map Points (Lấy dữ liệu trực tiếp từ AI Global)
                final_points = []
                if obj.points:
                    # [FIX CRITICAL] Tự động xác định stride để tránh lỗi lệch pha dữ liệu
                    # Nếu độ dài chia hết cho 3 -> [x, y, conf]. Nếu không -> [x, y]
                    stride = 3 if len(obj.points) % 3 == 0 else 2
                    num_points = len(obj.points) // stride

                    for i in range(num_points):
                        base = i * stride
                        px = obj.points[base] * scale_x
                        py = obj.points[base+1] * scale_y
                        conf = obj.points[base+2] if stride == 3 else 1.0

                        # [CORNER TRAP] Lọc điểm ma kẹt ở góc trên BBox
                        # [DYNAMIC] Dùng 8% kích thước cạnh lớn nhất của Box làm bán kính góc kẹt
                        if conf > 0:
                            corner_thresh = max(bw, bh) * 0.08
                            d_tl = math.sqrt((px - bx)**2 + (py - by)**2)
                            d_tr = math.sqrt((px - (bx + bw))**2 + (py - by)**2)
                            if d_tl < corner_thresh or d_tr < corner_thresh:
                                conf = 0.0

                        final_points.extend([px, py, conf])

                # [EDGE FIX] Ràng buộc chiều dài xương (Bone Length Constraint)
                self._apply_bone_constraint(final_points)

                # Convert sang int và kẹp biên
                bx = int(max(0, bx))
                by = int(max(0, by))
                bw = int(min(img_hd.width() - bx, bw))
                bh = int(min(img_hd.height() - by, bh))

                results.append({
                    "x": bx, "y": by, "w": bw, "h": bh, # [STABLE] Vẫn trả về Box gốc ổn định
                    "score": obj.score,
                    "class_id": 0,
                    # [OFFICIAL] Trả về nguyên bản points để dùng hàm draw_pose nếu cần
                    # Lưu ý: final_points của ta đã map về ảnh gốc, rất tốt.
                    "points": final_points 
                })

        except Exception as e:
            print(f"⚠️ AI Error: {e}")
        
        return img_hd, results

    def _apply_bone_constraint(self, points):
        """
        [KINEMATIC EXTRAPOLATION] Tự động tái tạo cẳng tay khi AI bị mù hoặc vẽ dị dạng (T-Rex).
        """
        def fix_arm_kinematics(sho_idx, elb_idx, wri_idx):
            base_s, base_e, base_w = sho_idx * 3, elb_idx * 3, wri_idx * 3
            
            # Kiểm tra an toàn index
            if base_w + 2 >= len(points): return
            
            sho_x, sho_y, sho_c = points[base_s], points[base_s+1], points[base_s+2]
            elb_x, elb_y, elb_c = points[base_e], points[base_e+1], points[base_e+2]
            wri_x, wri_y, wri_c = points[base_w], points[base_w+1], points[base_w+2]

            # Chỉ nội suy nếu AI vẫn đang nhìn thấy Vai và Khuỷu tay tương đối rõ
            if sho_c > 0.25 and elb_c > 0.25:
                upper_arm = math.sqrt((elb_x - sho_x)**2 + (elb_y - sho_y)**2)
                
                if upper_arm > 10.0: # Tránh chia cho 0 hoặc nhiễu quá nhỏ
                    lower_arm = math.sqrt((wri_x - elb_x)**2 + (wri_y - elb_y)**2)
                    ratio = lower_arm / upper_arm
                    
                    # Nếu tay bị rút (ratio < 0.75) HOẶC mất dấu hoàn toàn (conf < 0.15)
                    if ratio < 0.75 or wri_c < 0.15:
                        # TÍNH TOÁN ĐỘNG HỌC (Phóng vector)
                        dx = elb_x - sho_x
                        dy = elb_y - sho_y
                        
                        # Cẳng tay thực tế thường dài bằng ~1.3 lần bắp tay
                        points[base_w] = elb_x + dx * 1.1
                        points[base_w+1] = elb_y + dy * 1.1
                        
                        # Gán Conf = 0.5 (Đủ lớn để FSM nhận diện "Giơ tay", 
                        # nhưng đủ nhỏ để OneEuroFilter biết đây là dữ liệu dự đoán)
                        points[base_w+2] = 0.5 

        # Áp dụng cho Tay Trái (Vai: 5, Khuỷu: 7, Cổ tay: 9)
        fix_arm_kinematics(5, 7, 9)
        # Áp dụng cho Tay Phải (Vai: 6, Khuỷu: 8, Cổ tay: 10)
        fix_arm_kinematics(6, 8, 10)
