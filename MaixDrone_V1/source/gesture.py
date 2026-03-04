import math
import time
import config

class GestureFSM:
    """
    Finite State Machine quản lý trạng thái của một cử chỉ.
    Cơ chế: Trigger (Debounce) -> Active -> Hold (Hysteresis) -> Decay -> Neutral
    """
    def __init__(self, name, trigger_frames=5, hold_frames=10):
        self.name = name
        self.trigger_frames = trigger_frames # Số frame liên tục để kích hoạt
        self.hold_frames = hold_frames       # Số frame giữ trạng thái sau khi mất tín hiệu
        
        self.counter = 0        # Đếm số frame kích hoạt
        self.decay_counter = 0  # Đếm lùi thời gian giữ (Hold)
        self.is_active = False  # Trạng thái hiện tại

    def update(self, is_detected):
        if is_detected:
            self.counter += 1
            self.decay_counter = self.hold_frames # Nạp đầy năng lượng giữ
            
            if self.counter >= self.trigger_frames:
                self.is_active = True
                self.counter = self.trigger_frames # Kẹp trần
        else:
            if self.is_active:
                self.decay_counter -= 1
                if self.decay_counter <= 0:
                    self.is_active = False
                    self.counter = 0 # Reset hoàn toàn
            else:
                self.counter = 0 # Reset nếu chưa kịp kích hoạt mà đã mất tín hiệu
                
        return self.is_active

    def reset(self):
        """Reset trạng thái về ban đầu (Dùng cho Mutual Exclusion)"""
        self.counter = 0
        self.decay_counter = 0
        self.is_active = False

class PoseEstimator:
    def __init__(self):
        # --- KHỞI TẠO CÁC MÁY TRẠNG THÁI (FSM) ---
        # Cấu hình: Tên, Trigger (Độ nhạy), Hold (Độ lì)
        
        # 1. Emergency Stop (Quan trọng nhất -> Hold lâu để chắc chắn)
        self.fsm_emergency = GestureFSM("Cheo Tay Tren Dau", trigger_frames=6, hold_frames=15)
        
        # 2. Tay Trái
        self.fsm_l_vuong = GestureFSM("Trai Vuong", trigger_frames=4, hold_frames=8)
        self.fsm_l_ngang = GestureFSM("Trai Ngang", trigger_frames=4, hold_frames=8)
        self.fsm_l_cao   = GestureFSM("Trai Cao",   trigger_frames=4, hold_frames=8)
        
        # 3. Tay Phải
        self.fsm_r_vuong = GestureFSM("Phai Vuong", trigger_frames=4, hold_frames=8)
        self.fsm_r_ngang = GestureFSM("Phai Ngang", trigger_frames=4, hold_frames=8)
        self.fsm_r_cao   = GestureFSM("Phai Cao",   trigger_frames=4, hold_frames=8)

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
            
        # 2. Phân tích cử chỉ (Logic hình học -> FSM Update)
        # Hàm _analyze giờ đây sẽ cập nhật trạng thái FSM bên trong
        final_status = self._analyze(current_kpts, current_confs)
        
        return final_status

    def _analyze(self, kp, confs):
        # Helper: Vector Math
        def dist(p1, p2): return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
        
        # Indices (COCO)
        # 5,6: Shoulders | 11,12: Hips | 7,8: Elbows | 9,10: Wrists | 13,14: Knees
        
        final_status = []
        
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
        
        # [T-REX FILTER] Ngưỡng vươn tay tối thiểu (Chống tay co rút do nhiễu)
        high_wrist_conf_min = getattr(config, "HIGH_HAND_WRIST_CONF_MIN", 0.12)
        high_head_margin = getattr(config, "HIGH_HAND_HEAD_MARGIN_RATIO", 0.10) * torso_len
        high_elbow_lift_ratio = getattr(config, "HIGH_HAND_ELBOW_LIFT_RATIO", 0.20)
        MIN_ARM_EXT = getattr(config, "HIGH_HAND_EXT_RATIO", 0.30) * torso_len
        # Nới riêng cho trạng thái giơ cao tay trái (dễ bị co rút do che khuất).
        MIN_ARM_EXT_HIGH_LEFT = getattr(config, "HIGH_HAND_EXT_RATIO_LOOSE", 0.16) * torso_len
        # Nới riêng cho trạng thái giơ cao tay phải (dễ bị co rút do che khuất).
        MIN_ARM_EXT_HIGH_RIGHT = getattr(config, "HIGH_HAND_EXT_RATIO_LOOSE", 0.16) * torso_len

        # --- LOGIC BOOLEAN (RAW) ---
        
        # --- TAY TRÁI (Left Arm: 5-7-9) ---
        raw_l_vuong = raw_l_ngang = raw_l_cao = False
        if confs[5] > MIN_CONF and confs[7] > MIN_CONF and confs[9] > high_wrist_conf_min:
            y_elb, x_elb = kp[7][1], kp[7][0]
            y_wri, x_wri = kp[9][1], kp[9][0]

            # [T-REX CHECK] Kiểm tra độ vươn tay
            arm_l_dist = dist(kp[5], kp[9])
            
            left_high_candidate = (y_wri < (head_y + high_head_margin) and y_elb < y_sho_l - (HORIZ_TOL * high_elbow_lift_ratio))
            if arm_l_dist > MIN_ARM_EXT or (left_high_candidate and arm_l_dist > MIN_ARM_EXT_HIGH_LEFT):
                # 1. Check VUONG (Square): Khuỷu ngang Vai, Cổ tay dựng đứng
                # [PRIORITY 1] Ưu tiên bắt dáng vuông góc trước để tránh nhầm với giơ cao
                if abs(y_elb - y_sho_l) < HORIZ_TOL and y_wri < y_elb - VERT_MIN:
                    raw_l_vuong = True
                
                # 2. Check NGANG (Horizontal): Khuỷu & Cổ tay ngang tầm Vai
                elif abs(y_elb - y_sho_l) < HORIZ_TOL and abs(y_wri - y_sho_l) < HORIZ_TOL:
                    # Check Vươn tay: Cổ tay phải nằm ngoài Vai (về phía bên phải ảnh)
                    if x_wri > x_sho_l + EXT_MIN:
                        raw_l_ngang = True

                # 3. Check CAO (High): Cổ tay cao hơn Đầu VÀ Khuỷu tay cao hơn Vai
                # [STRICT] Siết chặt điều kiện: Khuỷu tay phải nâng lên rõ rệt
                elif y_wri < (head_y + high_head_margin) and y_elb < y_sho_l - (HORIZ_TOL * high_elbow_lift_ratio):
                    raw_l_cao = True

        # --- TAY PHẢI (Right Arm: 6-8-10) ---
        raw_r_vuong = raw_r_ngang = raw_r_cao = False
        if confs[6] > MIN_CONF and confs[8] > MIN_CONF and confs[10] > high_wrist_conf_min:
            y_elb, x_elb = kp[8][1], kp[8][0]
            y_wri, x_wri = kp[10][1], kp[10][0]

            # [T-REX CHECK] Kiểm tra độ vươn tay
            arm_r_dist = dist(kp[6], kp[10])

            right_high_candidate = (y_wri < (head_y + high_head_margin) and y_elb < y_sho_r - (HORIZ_TOL * high_elbow_lift_ratio))
            if arm_r_dist > MIN_ARM_EXT or (right_high_candidate and arm_r_dist > MIN_ARM_EXT_HIGH_RIGHT):
                # 1. Check VUONG (Square): Khuỷu ngang Vai, Cổ tay dựng đứng
                if abs(y_elb - y_sho_r) < HORIZ_TOL and y_wri < y_elb - VERT_MIN:
                    raw_r_vuong = True
                
                # 2. Check NGANG (Horizontal): Khuỷu & Cổ tay ngang tầm Vai
                elif abs(y_elb - y_sho_r) < HORIZ_TOL and abs(y_wri - y_sho_r) < HORIZ_TOL:
                    # Check Vươn tay: Cổ tay phải nằm ngoài Vai (về phía bên trái ảnh)
                    if x_wri < x_sho_r - EXT_MIN:
                        raw_r_ngang = True

                # 3. Check CAO (High): Cổ tay cao hơn Đầu VÀ Khuỷu tay cao hơn Vai
                elif y_wri < (head_y + high_head_margin) and y_elb < y_sho_r - (HORIZ_TOL * high_elbow_lift_ratio):
                    raw_r_cao = True

        # --- EMERGENCY STOP (Cheo Tay) ---
        raw_crossed = False
        
        # [NEW LOGIC] Cheo Tay Tren Dau (Emergency Stop) - Hình học
        # [OCCLUSION FIX] Bỏ qua conf Cổ tay (do bị che), chỉ cần Khuỷu tay rõ (0.2)
        if has_shoulders and confs[7] > 0.2 and confs[8] > 0.2:
            # Check 1: Khuỷu tay cao hơn Vai (Elbows Up) - Y càng nhỏ càng cao
            elbows_up = kp[7][1] < kp[5][1] and kp[8][1] < kp[6][1]
            
            # Check 2: Cổ tay cao hơn Đầu (Wrists Up)
            # Dù conf thấp, vẫn dùng toạ độ (giả định là đã được lọc/dự đoán từ tracker)
            wrists_up = kp[9][1] < head_y and kp[10][1] < head_y
            
            # Check 3: Hai tay gần nhau (Wrist Dist)
            wrist_dist = dist(kp[9], kp[10])
            elbow_dist = dist(kp[7], kp[8])
            
            # Tham chiếu: Chiều rộng vai hoặc Chiều dài thân
            ref_len = max(dist(kp[5], kp[6]), torso_len)
            
            # [STRICT] Khoảng cách phải nhỏ (0.8) và Khuỷu tay phải đưa lên
            if elbows_up and wrists_up and (wrist_dist < elbow_dist * 0.8) and (wrist_dist < ref_len * 0.7):
                raw_crossed = True

        # --- FSM UPDATE (Cập nhật trạng thái máy) ---
        # Truyền tín hiệu thô vào FSM để lọc nhiễu
        
        # 1. Emergency
        act_crossed = self.fsm_emergency.update(raw_crossed)
        
        if act_crossed:
            # [MUTUAL EXCLUSION] Nếu Emergency kích hoạt, Reset toàn bộ các FSM khác ngay lập tức
            self.fsm_l_vuong.reset(); act_l_vuong = False
            self.fsm_l_ngang.reset(); act_l_ngang = False
            self.fsm_l_cao.reset();   act_l_cao = False
            self.fsm_r_vuong.reset(); act_r_vuong = False
            self.fsm_r_ngang.reset(); act_r_ngang = False
            self.fsm_r_cao.reset();   act_r_cao = False
        else:
            # 2. Left Arm
            act_l_vuong = self.fsm_l_vuong.update(raw_l_vuong)
            act_l_ngang = self.fsm_l_ngang.update(raw_l_ngang)
            act_l_cao   = self.fsm_l_cao.update(raw_l_cao)
            
            # 3. Right Arm
            act_r_vuong = self.fsm_r_vuong.update(raw_r_vuong)
            act_r_ngang = self.fsm_r_ngang.update(raw_r_ngang)
            act_r_cao   = self.fsm_r_cao.update(raw_r_cao)

        # --- PRIORITY & COMBINATION (Xử lý xung đột) ---
        
        if act_crossed:
            final_status.append("Cheo Tay Tren Dau")
            # Nếu đang Emergency thì bỏ qua các tay khác
        else:
            # Logic kết hợp (Combined) dựa trên trạng thái Active của FSM
            if act_l_ngang and act_r_ngang:
                final_status.append("Hai Tay Ngang")
            elif act_l_cao and act_r_cao:
                final_status.append("Tay Chu V")
            else:
                # Trạng thái đơn lẻ
                if act_l_vuong: final_status.append("Trai Vuong")
                elif act_l_ngang: final_status.append("Trai Ngang")
                elif act_l_cao: final_status.append("Trai Cao")
                
                if act_r_vuong: final_status.append("Phai Vuong")
                elif act_r_ngang: final_status.append("Phai Ngang")
                elif act_r_cao: final_status.append("Phai Cao")
        
        return final_status
