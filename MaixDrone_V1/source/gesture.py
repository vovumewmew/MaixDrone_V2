import math
import time
from collections import Counter # [NEW] Dùng để bỏ phiếu

class PoseEstimator:
    def __init__(self, history_size=5):
        self.history = []
        self.history_size = history_size
        self.gesture_buffer = [] # [NEW] Bộ nhớ đệm để chống rung cử chỉ
        self.BUFFER_SIZE = 8     # Cần ổn định trong 8 frame (~0.3s) mới chốt
        
        # [WAVE DYNAMIC] Lịch sử vector tương đối (Cổ tay - Khuỷu tay) cho tay phải
        self.rw_wave_hist = []
        self.WAVE_LEN = 20       # Cửa sổ xét dao động (~0.6s)

    def update(self, keypoints):
        """
        Input: keypoints list [x1, y1, c1, x2, y2, c2, ...]
        Output: List of status strings (e.g., ["Standing", "Hands Up"])
        """
        if not keypoints or len(keypoints) < 17 * 3: return []
        
        # 1. Parse Keypoints (x, y, conf)
        current_kpts = []
        current_confs = [] # [NEW] Lưu độ tin cậy
        for i in range(0, len(keypoints), 3):
            current_kpts.append((keypoints[i], keypoints[i+1]))
            current_confs.append(keypoints[i+2])
            
        # [WAVE DYNAMIC] Cập nhật dữ liệu thô (Raw Data)
        # Tính chênh lệch X giữa Cổ tay phải (10) và Khuỷu tay phải (8)
        val = None
        if len(keypoints) >= 33:
            # Conf > 0.4
            if current_confs[8] > 0.4 and current_confs[10] > 0.4:
                val = current_kpts[10][0] - current_kpts[8][0] # Delta X
        
        self.rw_wave_hist.append(val)
        if len(self.rw_wave_hist) > self.WAVE_LEN:
            self.rw_wave_hist.pop(0)
            
        # [PURE AI] Không làm mượt điểm (Moving Average), dùng trực tiếp
        avg_kpts = current_kpts

        # 3. Phân tích cử chỉ (kèm độ tin cậy)
        raw_gestures = self._analyze(avg_kpts, current_confs)
        
        # 4. [SMART] Cơ chế Bỏ phiếu (Voting)
        # Chỉ trả về cử chỉ nếu nó xuất hiện liên tục (ổn định)
        if raw_gestures:
            self.gesture_buffer.append(tuple(sorted(raw_gestures))) # Lưu dưới dạng tuple để hash được
        else:
            self.gesture_buffer.append(None)
            
        if len(self.gesture_buffer) > self.BUFFER_SIZE:
            self.gesture_buffer.pop(0)
            
        # Đếm tần suất xuất hiện trong buffer
        valid_gestures = [g for g in self.gesture_buffer if g is not None]
        if not valid_gestures: return []
        
        most_common, count = Counter(valid_gestures).most_common(1)[0]
        
        # Ngưỡng chấp nhận: Phải xuất hiện > 60% trong buffer
        if count > (self.BUFFER_SIZE * 0.6):
            return list(most_common)
        else:
            return []

    def _analyze(self, kp, confs):
        # Helper: Vector Math
        def vec(p1, p2): return (p2[0] - p1[0], p2[1] - p1[1])
        def dot(v1, v2): return v1[0]*v2[0] + v1[1]*v2[1]
        def cross(v1, v2): return v1[0]*v2[1] - v1[1]*v2[0]
        def angle(v1, v2): return math.degrees(math.atan2(cross(v1, v2), dot(v1, v2)))
        def dist(p1, p2): return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
        
        # Indices (COCO)
        # 5,6: Shoulders | 11,12: Hips | 7,8: Elbows | 9,10: Wrists | 13,14: Knees
        
        status = []
        UP = (0, -1)
        
        # [SMART] Ngưỡng tin cậy tối thiểu để tính toán góc (tránh rác)
        MIN_CONF = 0.35

        # [SAFETY] Kiểm tra nếu thiếu các điểm quan trọng (Vai hoặc Hông)
        # Nếu thiếu Hông (11, 12) -> Không thể tính Spine -> Bỏ qua Body State
        has_hips = (confs[11] > MIN_CONF and confs[12] > MIN_CONF)
        has_shoulders = (confs[5] > MIN_CONF and confs[6] > MIN_CONF)

        # [SCALE] Chuẩn hoá theo kích thước cơ thể để ổn định mọi khoảng cách
        if has_hips and has_shoulders:
            mid_sho = ((kp[5][0]+kp[6][0])/2, (kp[5][1]+kp[6][1])/2)
            mid_hip = ((kp[11][0]+kp[12][0])/2, (kp[11][1]+kp[12][1])/2)
            torso_len = dist(mid_sho, mid_hip)
        elif has_shoulders:
            torso_len = dist(kp[5], kp[6])
        else:
            torso_len = 1.0
        if torso_len < 1.0: torso_len = 1.0

        # --- 1. BODY STATE (Standing/Sitting/Lying) ---
        # Spine Vector (Mid-Hip to Mid-Shoulder)
        if has_hips and has_shoulders:
            mid_sho = ((kp[5][0]+kp[6][0])/2, (kp[5][1]+kp[6][1])/2)
            mid_hip = ((kp[11][0]+kp[12][0])/2, (kp[11][1]+kp[12][1])/2)
            spine = vec(mid_hip, mid_sho)
            
            spine_angle = abs(angle(UP, spine))
            
            body_pose = "Khong Ro"
            if spine_angle < 30: # Upright
                # Check Legs for Sitting vs Standing
                # Thigh Vector (Hip to Knee) vs Spine
                l_thigh = vec(kp[11], kp[13])
                r_thigh = vec(kp[12], kp[14])
                
                # Angle between Spine (Up) and Thigh (Down)
                # If standing, thigh goes down (~180 deg from spine). If sitting, thigh goes forward (~90 deg).
                # Let's use relative angle to Spine vector (which points UP)
                # Thigh points DOWN. So angle should be ~180.
                l_leg_ang = abs(angle(spine, l_thigh))
                r_leg_ang = abs(angle(spine, r_thigh))
                
                if l_leg_ang > 150 or r_leg_ang > 150:
                    body_pose = "Dung"
                elif l_leg_ang < 120 or r_leg_ang < 120:
                    body_pose = "Ngoi"
                else:
                    body_pose = "Dung"
            elif spine_angle < 70:
                body_pose = "Nghieng"
            else:
                body_pose = "Nam"
                
            status.append(body_pose)
        else:
            # Nếu không thấy hông, giả định Spine thẳng đứng để tính tay
            spine = (0, -1) 
            spine_down = (0, 1)

        # --- 2. ARM STATE (Control Signals) ---
        # [UPDATE] RELATIVE COORDINATE LOGIC (ZONE-BASED)
        # Thay vì tính góc (dễ sai khi 2D), ta so sánh toạ độ Y và X tương đối.
        
        # 1. Xác định mốc chiều cao của "Đầu" (Head Level)
        def get_head_y():
            candidates = []
            # Ưu tiên: Mắt (1,2), Mũi (0), Tai (3,4)
            for idx in [1, 2, 0, 3, 4]:
                if confs[idx] > MIN_CONF: candidates.append(kp[idx][1])
            
            if candidates: return sum(candidates) / len(candidates)
            
            # Fallback: Vai - 30% Thân người
            if confs[5] > MIN_CONF and confs[6] > MIN_CONF:
                return (kp[5][1] + kp[6][1])/2 - (torso_len * 0.3)
            return 0

        head_y = get_head_y()
        
        # Toạ độ Vai (Làm mốc so sánh)
        y_sho_l, x_sho_l = kp[5][1], kp[5][0] # Vai Trái (Image Right)
        y_sho_r, x_sho_r = kp[6][1], kp[6][0] # Vai Phải (Image Left)

        l_status = None
        r_status = None

        # [TUNING] Các ngưỡng so sánh (Dựa trên chiều dài thân người)
        HORIZ_TOL = 0.25 * torso_len  # Dung sai cho ngang (+/- 25% thân)
        EXT_MIN = 0.4 * torso_len     # Độ vươn tay tối thiểu ra ngoài
        VERT_MIN = 0.25 * torso_len   # Độ cao tối thiểu (Cổ tay > Khuỷu)

        # --- TAY TRÁI (Left Arm: 5-7-9) ---
        if confs[5] > MIN_CONF and confs[7] > MIN_CONF and confs[9] > MIN_CONF:
            y_elb, x_elb = kp[7][1], kp[7][0]
            y_wri, x_wri = kp[9][1], kp[9][0]

            # 1. Check CAO (High): Cổ tay cao hơn Đầu
            if y_wri < head_y:
                l_status = "Trai Cao"
            
            # 2. Check NGANG (Horizontal): Khuỷu & Cổ tay ngang tầm Vai
            elif abs(y_elb - y_sho_l) < HORIZ_TOL and abs(y_wri - y_sho_l) < HORIZ_TOL:
                # Check Vươn tay: Cổ tay phải nằm ngoài Vai (về phía bên phải ảnh)
                if x_wri > x_sho_l + EXT_MIN:
                    l_status = "Trai Ngang"
            
            # 3. Check VUONG (Square): Khuỷu ngang Vai, Cổ tay dựng đứng
            elif abs(y_elb - y_sho_l) < HORIZ_TOL:
                # Cổ tay cao hơn Khuỷu tay một đoạn đáng kể
                if y_wri < y_elb - VERT_MIN:
                    l_status = "Trai Vuong"

        # --- TAY PHẢI (Right Arm: 6-8-10) ---
        if confs[6] > MIN_CONF and confs[8] > MIN_CONF and confs[10] > MIN_CONF:
            y_elb, x_elb = kp[8][1], kp[8][0]
            y_wri, x_wri = kp[10][1], kp[10][0]

            # 1. Check CAO (High): Cổ tay cao hơn Đầu
            if y_wri < head_y:
                r_status = "Phai Cao"
            
            # 2. Check NGANG (Horizontal): Khuỷu & Cổ tay ngang tầm Vai
            elif abs(y_elb - y_sho_r) < HORIZ_TOL and abs(y_wri - y_sho_r) < HORIZ_TOL:
                # Check Vươn tay: Cổ tay phải nằm ngoài Vai (về phía bên trái ảnh)
                if x_wri < x_sho_r - EXT_MIN:
                    r_status = "Phai Ngang"
            
            # 3. Check VUONG (Square): Khuỷu ngang Vai, Cổ tay dựng đứng
            elif abs(y_elb - y_sho_r) < HORIZ_TOL:
                if y_wri < y_elb - VERT_MIN:
                    r_status = "Phai Vuong"

        # --- 3. COMBINED GESTURES (Tư thế phối hợp) ---
        # Logic mới: Kết hợp từ trạng thái đơn lẻ "Cao Vuong"

        # Tổng hợp trạng thái
        # [UPDATE] Ưu tiên hiển thị tư thế kết hợp, ẩn tư thế con
        
        # [NEW LOGIC] Cheo Tay Tren Dau (Emergency Stop) - Hình học
        is_crossed = False
        # [SMART] Yêu cầu độ tin cậy cao hơn cho hành động quan trọng này
        if has_shoulders and confs[9] > 0.4 and confs[10] > 0.4:
            # Check 1: Cả 2 tay đều cao hơn Đầu (dùng head_y chuẩn ở trên)
            wrists_up = kp[9][1] < head_y and kp[10][1] < head_y
            
            # Check 2: Hai tay gần nhau
            wrist_dist = dist(kp[9], kp[10])
            
            # Tham chiếu: Chiều rộng vai hoặc Chiều dài thân
            ref_len = max(dist(kp[5], kp[6]), torso_len)
            
            # Ngưỡng: Khoảng cách 2 tay nhỏ hơn 60% kích thước cơ thể
            if wrists_up and wrist_dist < (ref_len * 0.6):
                is_crossed = True

        if is_crossed:
            status.append("Cheo Tay Tren Dau")
        else:
            # [DISABLED] Tắt thuật toán cũ để nhường quyền cho ST-GCN (source/st_gcn.py)
            pass
            # # --- [NEW] DYNAMIC WAVE LOGIC (User Request) ---
            # # Xét dao động của vector Cổ tay - Khuỷu tay (Biên độ > 15px, Đổi chiều >= 2 lần)
            # def check_right_wave_dynamic():
            #     data = [x for x in self.rw_wave_hist if x is not None]
            #     if len(data) < 10: return False # Cần ít nhất 10 frame dữ liệu
            #     
            #     # 1. Check Biên độ (15px)
            #     amp = max(data) - min(data)
            #     if amp < 20: return False
            #     
            #     # 2. Check Số lần đổi chiều (Oscillation)
            #     changes = 0
            #     last_dir = 0
            #     for i in range(1, len(data)-1):
            #         diff = data[i] - data[i-1]
            #         if abs(diff) < 10: continue # Lọc nhiễu nhỏ (<3px coi như đứng yên)
            #         curr_dir = 1 if diff > 0 else -1
            #         if last_dir != 0 and curr_dir != last_dir:
            #             changes += 1
            #         last_dir = curr_dir
            #     
            #     return changes >= 3
            # 
            # # Ưu tiên logic động này cho tay phải (Ghi đè logic tĩnh)
            # if check_right_wave_dynamic():
            #     # Vẫn cần điều kiện: Cổ tay cao hơn Khuỷu tay (để tránh lúc đi bộ đánh tay thấp)
            #     if kp[10][1] < kp[8][1]:
            #         r_status = "Vay Tay Phai"

            if l_status == "Trai Ngang" and r_status == "Phai Ngang":
                status.append("Hai Tay Ngang")
            elif l_status == "Trai Cao" and r_status == "Phai Cao":
                status.append("Tay Chu V")
            else:
                if l_status: status.append(l_status)
                if r_status: status.append(r_status)
        
        return status
