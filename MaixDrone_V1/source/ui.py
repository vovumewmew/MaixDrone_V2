from maix import image
import config

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

            # 3. Vẽ Xương (Pose) - Raw Output
            points = obj.get('points', [])
            joints = {}
            
            # Vẽ điểm (Joints)
            for i in range(0, len(points), 3):
                px, py, conf = points[i], points[i+1], points[i+2]
                # Vẽ tất cả các điểm mà AI nhìn thấy (conf > 0)
                if conf > 0:
                    idx = i // 3
                    # [UI] Giảm kích thước điểm từ 3 -> 2
                    img.draw_circle(int(px), int(py), 2, self.C_CYAN, -1)
                    joints[idx] = (int(px), int(py), conf)
            
            # Vẽ đường nối (Bones)
            for i, j in self.SKELETON:
                if i in joints and j in joints:
                    p1 = joints[i]
                    p2 = joints[j]
                    # Chỉ vẽ nếu cả 2 đầu đều có độ tin cậy > 0
                    if p1[2] > 0 and p2[2] > 0:
                        # [UI] Giảm độ dày nét vẽ từ 2 -> 1 (tương đương 1.3px)
                        img.draw_line(p1[0], p1[1], p2[0], p2[1], self.C_WHITE, 1)