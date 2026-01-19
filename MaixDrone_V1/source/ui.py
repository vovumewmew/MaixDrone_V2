from maix import image
import config
from maix import nn # Import để dùng hàm vẽ tĩnh nếu cần (tùy phiên bản SDK)

class HUD:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.C_RED = image.Color(255, 0, 0)
        self.C_YELLOW = image.Color(255, 255, 0)
        self.C_GREEN = image.Color(0, 255, 0)
        self.C_WHITE = image.Color(255, 255, 255)
        self.C_PINK = image.Color(255, 105, 180) # Màu Hồng (HotPink)
        self.C_BLACK = image.Color(0, 0, 0)      # Màu Đen
        self.C_CYAN = image.Color(0, 255, 255)   # Màu Xanh Lơ (Cyan)
        
        # Định nghĩa các cặp điểm nối xương (COCO Format)
        self.SKELETON = [
            (0, 1), (0, 2), (1, 3), (2, 4),         # Đầu
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10), # Tay
            (11, 12), (5, 11), (6, 12),             # Thân
            (11, 13), (13, 15), (12, 14), (14, 16)  # Chân
        ]
        
    def draw_fps(self, img, fps):
        # Giảm scale từ 2.0 -> 1.2
        img.draw_string(10, 10, f"FPS: {int(fps)}", self.C_WHITE, 1.2)

    def draw_ai_result(self, img, results):
        # Vẽ số lượng người
        count = len(results)
        img.draw_string(10, 30, f"Count: {count}", self.C_YELLOW, 1.2)

        if not results: return

        for obj in results:
            # Lấy thông tin từ Tracker
            oid = obj['id']
            score = obj.get('score', 0.0)
            bx, by, bw, bh = obj['box']
            
            # 1. Vẽ Khung bao (Màu Hồng)
            img.draw_rect(int(bx), int(by), int(bw), int(bh), self.C_PINK, 2)
            
            # 2. Vẽ Nhãn (ID + Score)
            text = f"ID:{oid} {int(score * 100)}%"
            img.draw_string(int(bx), int(by) - 20, text, self.C_PINK, 1.2)
            
            lx = int(bx)
            
            # [MỚI] Hiển thị Vector Score (Độ ổn định cấu trúc)
            v_score = obj.get('vector_score', 0)
            if v_score > 0:
                s_color = self.C_GREEN if v_score > 85 else self.C_RED
                s_text = f"Struct: {int(v_score)}%"
                # Vẽ ở góc dưới bên trái Box
                img.draw_string(lx, int(by + bh) + 5, s_text, s_color, 1.0)
                
            # [GESTURE] Hiển thị cử chỉ nhận diện được
            gestures = obj.get('gestures', [])
            if gestures:
                g_text = " | ".join(gestures)
                img.draw_string(lx, int(by) - 40, g_text, self.C_YELLOW, 1.5)

            # 3. Vẽ Xương (Pose) - Raw Output
            points = obj.get('points', [])
            joints = {}
            
            # [OFFICIAL STYLE] Vẽ đơn giản, trực tiếp, không lọc cầu kỳ
            # Nếu SDK hỗ trợ detector.draw_pose thì tốt, nhưng ở đây ta tách rời UI và AI
            # nên ta sẽ vẽ thủ công nhưng theo phong cách "Raw" của họ.
            
            # Vẽ Skeleton (Nối dây trước cho đỡ đè lên điểm)
            for i in range(0, len(points), 3):
                if points[i+2] > 0: # Chỉ cần conf > 0 là lưu
                    joints[i//3] = (int(points[i]), int(points[i+1]))

            for i, j in self.SKELETON:
                if i in joints and j in joints:
                    # Màu trắng, nét mảnh (1px)
                    img.draw_line(joints[i][0], joints[i][1], joints[j][0], joints[j][1], self.C_WHITE, 1)

            # Vẽ Khớp (Đè lên dây)
            for idx, (px, py) in joints.items():
                # Màu Cyan, bán kính 2
                img.draw_circle(px, py, 2, self.C_CYAN, -1)