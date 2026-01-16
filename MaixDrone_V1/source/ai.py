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
            self.model = nn.YOLOv8(self.model_path)
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def process(self, img_hd):
        if not self.model: return img_hd, []
        
        results = []
        
        try:
            # 1. [LETTERBOX] Resize giữ tỷ lệ (Aspect Ratio Preservation)
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

            # 2. Chạy Model (Trả về cả Box và Points)
            objs = self.model.detect(img_input, conf_th=self.threshold, iou_th=0.45)
            
            for obj in objs:
                # Map Box (Trừ đi padding rồi mới chia cho ratio)
                bx = int((obj.x - pad_w) / ratio)
                by = int((obj.y - pad_h) / ratio)
                bw = int(obj.w / ratio)
                bh = int(obj.h / ratio)
                
                # Kiểm tra biên
                if bw < 10 or bh < 10: continue
                bx = max(0, bx)
                by = max(0, by)
                bw = min(img_hd.width() - bx, bw)
                bh = min(img_hd.height() - by, bh)

                # Map Points (Vẫn lấy dữ liệu nhưng chưa xử lý sâu)
                final_points = []
                if obj.points:
                    for i in range(0, len(obj.points), 3):
                        if i + 2 >= len(obj.points): break
                        # Map Points tương tự như Box
                        px = (obj.points[i] - pad_w) / ratio
                        py = (obj.points[i+1] - pad_h) / ratio
                        conf = obj.points[i+2]
                        final_points.extend([px, py, conf])

                results.append({
                    "x": bx, "y": by, "w": bw, "h": bh,
                    "score": obj.score,
                    "class_id": 0,
                    "points": final_points
                })

        except Exception as e:
            print(f"⚠️ AI Error: {e}")
        
        return img_hd, results