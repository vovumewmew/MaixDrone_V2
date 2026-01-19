from maix import nn, image

class AIEngine:
    def __init__(self, model_path, conf_threshold):
        self.model_path = model_path
        self.threshold = conf_threshold
        self.model = None
        self.input_w = 320
        self.input_h = 224

    def load(self):
        try:
            print("🧠 Loading YOLOv8 Pose (Single Model)...")
            # [OFFICIAL] Bật dual_buff để tăng tốc xử lý song song
            self.model = nn.YOLOv8(self.model_path, dual_buff=True)
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def process(self, img_hd):
        if not self.model: return img_hd, []
        
        results = []
        
        try:
            # --- GIAI ĐOẠN 1: TÌM NGƯỜI (GLOBAL DETECTION) ---
            # [OPTIMIZATION] Kiểm tra nếu ảnh đầu vào đã đúng kích thước Model (320x224)
            # thì bỏ qua bước Resize và Padding để tăng tốc độ xử lý.
            if img_hd.width() == self.input_w and img_hd.height() == self.input_h:
                img_input = img_hd
                ratio = 1.0
                pad_w = 0
                pad_h = 0
            else:
                # Tính tỷ lệ scale để ảnh vừa khít khung 320x224 mà không bị méo
                ratio = min(self.input_w / img_hd.width(), self.input_h / img_hd.height())
                new_w = int(img_hd.width() * ratio)
                new_h = int(img_hd.height() * ratio)
                
                # Resize ảnh gốc
                img_resized = img_hd.resize(new_w, new_h)
                
                # Tạo ảnh nền đen 320x224 và dán ảnh đã resize vào giữa
                img_input = image.Image(self.input_w, self.input_h) # Mặc định là đen
                pad_w = (self.input_w - new_w) // 2
                pad_h = (self.input_h - new_h) // 2
                img_input.draw_image(pad_w, pad_h, img_resized)

            # Chạy Model lần 1 để lấy Box
            objs = self.model.detect(img_input, conf_th=self.threshold, iou_th=0.45)
            
            for obj in objs:
                # Map Box gốc từ YOLO
                bx = (obj.x - pad_w) / ratio
                by = (obj.y - pad_h) / ratio
                bw = obj.w / ratio
                bh = obj.h / ratio

                # [PADDING] Mở rộng 10% để bao quát toàn bộ vật thể (như lúc ổn định)
                PAD_RATIO = 0.10
                pad_w_val = bw * PAD_RATIO
                pad_h_val = bh * PAD_RATIO
                bx -= pad_w_val / 2
                by -= pad_h_val / 2
                bw += pad_w_val
                bh += pad_h_val

                # Map Points (Lấy dữ liệu trực tiếp từ AI Global)
                final_points = []
                if obj.points:
                    for i in range(0, len(obj.points), 3):
                        if i + 2 >= len(obj.points): break
                        px = (obj.points[i] - pad_w) / ratio
                        py = (obj.points[i+1] - pad_h) / ratio
                        conf = obj.points[i+2]
                        final_points.extend([px, py, conf])

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