from maix import image
import time
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
        
        # --- CẤU HÌNH HIỂN THỊ (Sửa True/False để Bật/Tắt các phần bạn muốn) ---
        self.SHOW_FPS = True         # Hiển thị FPS góc trái
        self.SHOW_COUNT = True       # Hiển thị số lượng người (Count: X)
        self.SHOW_BOX = True         # Hiển thị khung chữ nhật bao quanh người
        self.SHOW_INFO = True        # Hiển thị ID và độ tin cậy (%)
        self.SHOW_GESTURE = True     # Hiển thị tên cử chỉ (Giơ tay, ngồi...)
        self.SHOW_SKELETON = True    # Hiển thị bộ xương và khớp nối

        # Định nghĩa các cặp điểm nối xương (COCO Format)
        self.SKELETON = [
            (0, 1), (0, 2), (1, 3), (2, 4),         # Đầu
            (5, 6), (5, 7), (7, 9), (6, 8), (8, 10), # Tay
            (11, 12), (5, 11), (6, 12),             # Thân
            (11, 13), (13, 15), (12, 14), (14, 16)  # Chân
        ]
        
        self.last_print_time = time.time()
        self.keypoint_names = {
            0: "Nose", 1: "L-Eye", 2: "R-Eye", 3: "L-Ear", 4: "R-Ear",
            5: "L-Sho", 6: "R-Sho", 7: "L-Elb", 8: "R-Elb", 9: "L-Wri",
            10: "R-Wri", 11: "L-Hip", 12: "R-Hip", 13: "L-Knee", 14: "R-Knee",
            15: "L-Ank", 16: "R-Ank"
        }
        
    def draw_fps(self, img, fps):
        if not self.SHOW_FPS: return
        # Giảm scale từ 2.0 -> 1.2
        img.draw_string(10, 10, f"FPS: {int(fps)}", self.C_WHITE, 1.2)

    def draw_ai_result(self, img, results):
        # Vẽ số lượng người
        count = len(results)
        if self.SHOW_COUNT:
            img.draw_string(10, 30, f"Count: {count}", self.C_YELLOW, 1.2)

        if not results: return

        do_print = False
        if time.time() - self.last_print_time > 2.0:
            do_print = True
            self.last_print_time = time.time()

        for obj in results:
            # Lấy thông tin từ Tracker
            oid = obj['id']
            score = obj.get('score', 0.0)
            pose_score = obj.get('pose_score', 0.0)
            bx, by, bw, bh = obj['box']
            
            # 1. Vẽ Khung bao (Màu Hồng)
            if self.SHOW_BOX:
                img.draw_rect(int(bx), int(by), int(bw), int(bh), self.C_PINK, 2)
            
            # 2. Vẽ Nhãn (ID + Score)
            if self.SHOW_INFO:
                # [UI] Hiển thị thêm độ chính xác Pose: "ID:1 85% Pose:70%"
                text = f"ID:{oid} {int(score * 100)}% Pose:{int(pose_score * 100)}%"
                img.draw_string(int(bx), int(by) - 20, text, self.C_PINK, 0.7)
            
            lx = int(bx)
            
            # [GESTURE] Hiển thị cử chỉ nhận diện được
            if self.SHOW_GESTURE:
                gestures = obj.get('gestures', [])
                if gestures:
                    g_text = " + ".join(gestures)
                    # [UI] Giảm kích thước chữ 50% (1.5 -> 0.8) cho gọn
                    img.draw_string(int(bx + bw) + 5, int(by), g_text, self.C_YELLOW, 0.8)

            # 3. Vẽ Xương (Pose) - Raw Output
            if self.SHOW_SKELETON:
                points = obj.get('points', [])
                joints = {}
                
                # [POLISH] Tự động xác định stride (bước nhảy)
                stride = 3 if len(points) % 3 == 0 else 2
                num_points = len(points) // stride

                # 1. Lấy danh sách khớp hợp lệ
                for i in range(num_points):
                    base = i * stride
                    conf = points[base+2] if stride == 3 else 1.0
                    # [FIX] Lọc bỏ điểm ma ở góc trái trên (0,0) - Chỉ vẽ nếu toạ độ > 5
                    if conf > 0 and (points[base] > 5 or points[base+1] > 5):
                        joints[i] = (int(points[base]), int(points[base+1]))

                # 2. Vẽ dây (Line) - Màu Trắng
                for i, j in self.SKELETON:
                    if i in joints and j in joints:
                        img.draw_line(joints[i][0], joints[i][1], joints[j][0], joints[j][1], self.C_WHITE, 1)

                # 3. Vẽ Khớp (Dot) - Màu Trắng (Đè lên dây)
                for px, py in joints.values():
                    img.draw_circle(px, py, 2, self.C_WHITE, -1)
            
            if do_print:
                points = obj.get('points', [])
                stride = 3 if len(points) % 3 == 0 else 2
                num_points = len(points) // stride
                
                info = []
                for i in range(num_points):
                    base = i * stride
                    x = int(points[base])
                    y = int(points[base+1])
                    name = self.keypoint_names.get(i, str(i))
                    info.append(f"{name}:({x},{y})")
                print(f"ID{oid}: " + ", ".join(info))
        
        if do_print:
            print()