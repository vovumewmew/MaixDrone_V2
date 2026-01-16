from maix import image

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
        
        self.SKELETON = [
            (0, 1), (0, 2), (1, 3), (2, 4), 
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10), 
            (11, 12), (5, 11), (6, 12), 
            (11, 13), (13, 15), (12, 14), (14, 16) 
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
            
            # 1. Vẽ Khung bao (Màu Hồng) - Giảm độ dày xuống 1 (Mỏng hơn, tinh tế hơn)
            img.draw_rect(int(bx), int(by), int(bw), int(bh), self.C_PINK, 1)
            
            # 2. Vẽ Nhãn (Nền hồng, Chữ đen)
            text = f"Person {int(score * 100)}%"
            scale = 0.9 # Giảm từ 1.5 -> 0.9 (40%)
            # Ước lượng kích thước nền (W: ~7px/char, H: 14px)
            tw = len(text) * 7 
            th = 14
            
            # Vị trí: Góc trái trên
            lx = int(bx)
            ly = int(by) - th
            if ly < 0: ly = int(by) # Xử lý tràn màn hình
            
            # Vẽ chữ
            img.draw_string(lx + 1, ly + 1, text, self.C_BLACK, scale)
            
            # 3. Vẽ Xương (Pose)
            points = obj.get('points', [])
            joints = {}
            for i in range(0, len(points), 3):
                px, py, conf = points[i], points[i+1], points[i+2]
                # [FIX] Hạ xuống 0.25 để khớp với config.POSE_CONF_THRESHOLD (0.2)
                # Giúp hiển thị được tay/chân khi ở xa hoặc camera mờ
                if conf > 0.25: 
                    idx = i // 3
                    
                    # Vẽ điểm màu Trắng đơn giản, giảm kích thước
                    img.draw_circle(int(px), int(py), 3, self.C_WHITE, -1)
                    joints[idx] = (int(px), int(py), conf)
            
            # Nối dây
            for i, j in self.SKELETON:
                if i in joints and j in joints:
                    # Chỉ vẽ dây nếu CẢ 2 ĐIỂM đều tin cậy (> 0.25)
                    if joints[i][2] > 0.25 and joints[j][2] > 0.25:
                        p1 = joints[i]
                        p2 = joints[j]
                        # Nét mảnh (1px) và màu Trắng
                        img.draw_line(p1[0], p1[1], p2[0], p2[1], self.C_WHITE, 1)