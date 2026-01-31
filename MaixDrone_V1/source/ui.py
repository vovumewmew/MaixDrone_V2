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
        # [NEW] Biến để giới hạn tốc độ in log ra terminal (1s/lần)
        self.last_action_msg = None
        self.last_action_time = 0
        
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
        notification_msg = None # Biến lưu nội dung thông báo
        current_max_score = -1.0 # [NEW] Biến lưu điểm tin cậy cao nhất để ưu tiên hiển thị
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
                # [UI] Tối giản: Chỉ hiện ID và Pose Score (Bỏ Detect Score)
                text = f"ID:{oid} Pose:{int(pose_score * 100)}%"
                img.draw_string(int(bx), int(by) - 20, text, self.C_PINK, 0.7)
            
            lx = int(bx)
            
            # [GESTURE] Hiển thị cử chỉ nhận diện được
            if self.SHOW_GESTURE:
                gestures = obj.get('gestures', [])
                if gestures:
                    g_text = " + ".join(gestures)
                    
                    # [NOTIFY] Hiển thị thông báo trạng thái hệ thống
                    temp_msg = None
                    if "Trai Cao" in gestures:
                        temp_msg = "shortage of material"
                    elif "Phai Cao" in gestures:
                        temp_msg = "technical or quality issue"
                    elif "Cheo Tay Tren Dau" in gestures:
                        temp_msg = "emergency stop"
                    elif "Vay Tay Phai" in gestures:
                        temp_msg = "urgent attention"
                    
                    # [LOGIC] Chỉ hiển thị thông báo của người có độ tin cậy Pose cao nhất
                    if temp_msg and pose_score > current_max_score:
                        notification_msg = temp_msg
                        current_max_score = pose_score

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
                    # [FIX] Lọc bỏ điểm ma ở góc trái trên (0,0) - Giảm ngưỡng từ 5 xuống 1
                    if conf > 0 and (points[base] > 1 or points[base+1] > 1):
                        joints[i] = (int(points[base]), int(points[base+1]))

                # 2. Vẽ dây (Line) - Màu Trắng
                for i, j in self.SKELETON:
                    if i in joints and j in joints:
                        img.draw_line(joints[i][0], joints[i][1], joints[j][0], joints[j][1], self.C_WHITE, 1)
                
                # [CUSTOM] Vẽ đường nối từ Mũi (0) xuống Trung điểm Vai (5,6) - Tạo cảm giác cổ/ngực
                if 0 in joints and 5 in joints and 6 in joints:
                    mx = int((joints[5][0] + joints[6][0]) / 2)
                    my = int((joints[5][1] + joints[6][1]) / 2)
                    img.draw_line(joints[0][0], joints[0][1], mx, my, self.C_WHITE, 1)

                # 3. Vẽ Khớp (Dot) - Màu Trắng (Đè lên dây)
                for px, py in joints.values():
                    img.draw_circle(px, py, 2, self.C_WHITE, -1)
            
            if do_print:
                # [DEBUG] Tạm ẩn toạ độ để tập trung vào thông báo hành động
                # points = obj.get('points', [])
                # stride = 3 if len(points) % 3 == 0 else 2
                # num_points = len(points) // stride
                # 
                # info = []
                # for i in range(num_points):
                #     base = i * stride
                #     x = int(points[base])
                #     y = int(points[base+1])
                #     name = self.keypoint_names.get(i, str(i))
                #     info.append(f"{name}:({x},{y})")
                # print(f"ID{oid}: " + ", ".join(info))
                pass
        
        # [UI] Vẽ thông báo ở góc dưới màn hình (nếu có)
        if notification_msg:
            self._draw_notification(img, notification_msg)
            
        # [DEBUG] In thông báo trực tiếp ra terminal (Real-time) - Giới hạn 1s/lần cho cùng hành động
        t_now = time.time()
        if notification_msg != self.last_action_msg or (t_now - self.last_action_time > 1.0):
            print(f"🔔 ACTION: {notification_msg}")
            self.last_action_msg = notification_msg
            self.last_action_time = t_now
            
        # if do_print:
        #     print()

    def _draw_notification(self, img, text):
        """Vẽ thông báo nền trắng chữ đen ở góc dưới (Auto Wrap)"""
        # [REQ] Làm nhỏ đi ~20% (1.6 -> 1.3)
        scale = 1.3 
        char_w = 8 * scale 
        line_h = 20 * scale 
        
        # [AUTO WRAP] Tự động xuống dòng khi gần hết màn hình (Chừa lề 15px mỗi bên)
        max_width = self.width - 30
        
        words = text.split(' ')
        lines = []
        current_line = words[0]
        
        for word in words[1:]:
            if (len(current_line) + 1 + len(word)) * char_w <= max_width:
                current_line += " " + word
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        
        # Tính kích thước Box
        max_len = max(len(line) for line in lines)
        text_w = int(max_len * char_w)
        text_h = int(len(lines) * line_h)
        
        # [REQ] Tăng chiều ngang bên phải (Tổng 60px: Trái 20px, Phải 40px)
        box_w = int(text_w + 60)
        # [REQ] Giảm chiều cao đi ~30% (Padding trên dưới còn 6px: Trên 3px, Dưới 3px)
        box_h = int(text_h + 6)
        
        x = int((self.width - box_w) / 2)
        y = int(self.height - box_h - 10) # Cách đáy 10px cho thoáng
        
        # Vẽ nền trắng (Filled = -1)
        img.draw_rect(x, y, box_w, box_h, self.C_WHITE, -1)
        
        # Vẽ chữ đen đậm (vẽ 2 lần lệch nhau 1px để tạo hiệu ứng đậm)
        for i, line in enumerate(lines):
            ly = int(y + 3 + i * line_h) # Padding top 3px
            lx = int(x + 20)             # Padding left 20px (Căn giữa box)
            
            img.draw_string(lx, ly, line, self.C_BLACK, scale)
            img.draw_string(lx + 1, ly, line, self.C_BLACK, scale)