import math
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
        self.fsm_l_cao_vuong = GestureFSM("Trai Cao Vuong", trigger_frames=4, hold_frames=8)
        
        # 3. Tay Phải
        self.fsm_r_vuong = GestureFSM("Phai Vuong", trigger_frames=4, hold_frames=8)
        self.fsm_r_ngang = GestureFSM("Phai Ngang", trigger_frames=4, hold_frames=8)
        self.fsm_r_cao   = GestureFSM("Phai Cao",   trigger_frames=4, hold_frames=8)
        self.fsm_r_cao_vuong = GestureFSM("Phai Cao Vuong", trigger_frames=4, hold_frames=8)

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
        def dist(p1, p2):
            return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

        def angle_deg(p1, p2, p3):
            v1x, v1y = p1[0] - p2[0], p1[1] - p2[1]
            v2x, v2y = p3[0] - p2[0], p3[1] - p2[1]
            n1 = math.sqrt(v1x * v1x + v1y * v1y)
            n2 = math.sqrt(v2x * v2x + v2y * v2y)
            if n1 < 1e-3 or n2 < 1e-3:
                return None
            cos_v = (v1x * v2x + v1y * v2y) / (n1 * n2)
            cos_v = max(-1.0, min(1.0, cos_v))
            return math.degrees(math.acos(cos_v))

        def in_range(v, low, high):
            return (v is not None) and (low < v < high)

        final_status = []

        base_min_conf = 0.24
        has_hips = (confs[11] > base_min_conf and confs[12] > base_min_conf)
        has_shoulders = (confs[5] > base_min_conf and confs[6] > base_min_conf)

        if has_hips and has_shoulders:
            mid_sho = ((kp[5][0] + kp[6][0]) / 2, (kp[5][1] + kp[6][1]) / 2)
            mid_hip = ((kp[11][0] + kp[12][0]) / 2, (kp[11][1] + kp[12][1]) / 2)
            torso_len = dist(mid_sho, mid_hip)
        elif has_shoulders:
            torso_len = dist(kp[5], kp[6])
        else:
            torso_len = 1.0
        torso_len = max(1.0, torso_len)

        # Nguong conf dong theo kich thuoc doi tuong.
        if torso_len < 55:
            min_conf = 0.17
            angle_margin = 8.0
        elif torso_len < 85:
            min_conf = 0.23
            angle_margin = 5.0
        else:
            min_conf = 0.35
            angle_margin = 2.0

        wrist_conf_min = min(min_conf, float(getattr(config, "HIGH_HAND_WRIST_CONF_MIN", 0.12)) + 0.08)
        arm_ext_min = max(0.14 * torso_len, float(getattr(config, "HIGH_HAND_EXT_RATIO_LOOSE", 0.16)) * torso_len)

        def get_head_y():
            candidates = []
            for idx in [1, 2, 0, 3, 4]:
                if confs[idx] > min_conf:
                    candidates.append(kp[idx][1])
            if candidates:
                return sum(candidates) / float(len(candidates))
            if confs[5] > min_conf and confs[6] > min_conf:
                return (kp[5][1] + kp[6][1]) / 2.0 - (torso_len * 0.3)
            return 0.0

        def classify_side(side):
            if side == "left":
                s_idx, h_idx, e_idx, w_idx = 5, 11, 7, 9
            else:
                s_idx, h_idx, e_idx, w_idx = 6, 12, 8, 10

            if not (confs[s_idx] > min_conf and confs[h_idx] > min_conf and confs[e_idx] > min_conf and confs[w_idx] > wrist_conf_min):
                return False, False, False, False

            p_sho = kp[s_idx]
            p_hip = kp[h_idx]
            p_elb = kp[e_idx]
            p_wri = kp[w_idx]

            # Chan false positive khi co tay bi co rut/manh.
            if dist(p_sho, p_wri) < arm_ext_min:
                return False, False, False, False

            # Goc A: Khuyu - Vai - Hong
            a = angle_deg(p_elb, p_sho, p_hip)
            # Goc B: Co tay - Khuyu - Vai
            b = angle_deg(p_wri, p_elb, p_sho)
            # Goc C: Hong - Vai - Co tay
            c = angle_deg(p_hip, p_sho, p_wri)

            a_vuong = in_range(a, 70 - angle_margin, 100 + angle_margin)
            b_vuong = in_range(b, 60 - angle_margin, 100 + angle_margin)
            b_ngang = in_range(b, 140 - angle_margin, 180)
            c_cao = in_range(c, 140 - angle_margin, 180)
            a_cao_vuong = in_range(a, 140 - angle_margin, 180)
            b_cao_vuong = in_range(b, 75 - angle_margin, 90 + angle_margin)

            raw_vuong = a_vuong and b_vuong
            raw_ngang = a_vuong and b_ngang
            raw_cao = c_cao
            raw_cao_vuong = a_cao_vuong and b_cao_vuong

            # Priority: Cao Vuong > Ngang > Vuong > Cao
            if raw_cao_vuong:
                return False, False, True, True
            if raw_ngang:
                return False, True, False, False
            if raw_vuong:
                return True, False, False, False
            if raw_cao:
                return False, False, True, False
            return False, False, False, False

        raw_l_vuong, raw_l_ngang, raw_l_cao, raw_l_cao_vuong = classify_side("left")
        raw_r_vuong, raw_r_ngang, raw_r_cao, raw_r_cao_vuong = classify_side("right")

        # [RESTORE] Logic goc cho "Cheo Tay Tren Dau" (giu nguyen nhu truoc).
        raw_crossed = False
        head_y = get_head_y()
        if has_shoulders and confs[7] > 0.2 and confs[8] > 0.2:
            elbows_up = kp[7][1] < kp[5][1] and kp[8][1] < kp[6][1]
            wrists_up = kp[9][1] < head_y and kp[10][1] < head_y
            wrist_dist = dist(kp[9], kp[10])
            elbow_dist = dist(kp[7], kp[8])
            ref_len = max(dist(kp[5], kp[6]), torso_len)
            if elbows_up and wrists_up and (wrist_dist < elbow_dist * 0.8) and (wrist_dist < ref_len * 0.7):
                raw_crossed = True

        act_crossed = self.fsm_emergency.update(raw_crossed)

        if act_crossed:
            self.fsm_l_vuong.reset(); act_l_vuong = False
            self.fsm_l_ngang.reset(); act_l_ngang = False
            self.fsm_l_cao.reset(); act_l_cao = False
            self.fsm_l_cao_vuong.reset(); act_l_cao_vuong = False

            self.fsm_r_vuong.reset(); act_r_vuong = False
            self.fsm_r_ngang.reset(); act_r_ngang = False
            self.fsm_r_cao.reset(); act_r_cao = False
            self.fsm_r_cao_vuong.reset(); act_r_cao_vuong = False
        else:
            act_l_vuong = self.fsm_l_vuong.update(raw_l_vuong)
            act_l_ngang = self.fsm_l_ngang.update(raw_l_ngang)
            act_l_cao = self.fsm_l_cao.update(raw_l_cao)
            act_l_cao_vuong = self.fsm_l_cao_vuong.update(raw_l_cao_vuong)

            act_r_vuong = self.fsm_r_vuong.update(raw_r_vuong)
            act_r_ngang = self.fsm_r_ngang.update(raw_r_ngang)
            act_r_cao = self.fsm_r_cao.update(raw_r_cao)
            act_r_cao_vuong = self.fsm_r_cao_vuong.update(raw_r_cao_vuong)

        if act_crossed:
            # Duy tri ten cu de tuong thich UI/Socket mapping.
            final_status.append("Cheo Tay Tren Dau")
            return final_status

        # Tang dung cho to hop: Cao Vuong duoc tinh la Cao.
        act_l_cao_total = act_l_cao or act_l_cao_vuong
        act_r_cao_total = act_r_cao or act_r_cao_vuong

        if act_l_ngang and act_r_ngang:
            final_status.append("Hai Tay Ngang")
        elif act_l_cao_total and act_r_cao_total:
            final_status.append("Tay Chu V")
        else:
            if act_l_cao_vuong:
                final_status.append("Trai Cao Vuong")
                final_status.append("Trai Cao")
            elif act_l_vuong:
                final_status.append("Trai Vuong")
            elif act_l_ngang:
                final_status.append("Trai Ngang")
            elif act_l_cao_total:
                final_status.append("Trai Cao")

            if act_r_cao_vuong:
                final_status.append("Phai Cao Vuong")
                final_status.append("Phai Cao")
            elif act_r_vuong:
                final_status.append("Phai Vuong")
            elif act_r_ngang:
                final_status.append("Phai Ngang")
            elif act_r_cao_total:
                final_status.append("Phai Cao")

        return final_status
