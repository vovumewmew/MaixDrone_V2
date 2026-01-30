import math

class PoseEstimator:
    def __init__(self, history_size=5):
        self.history = []
        self.history_size = history_size

    def update(self, keypoints):
        """
        Input: keypoints list [x1, y1, c1, x2, y2, c2, ...]
        Output: List of status strings (e.g., ["Standing", "Hands Up"])
        """
        if not keypoints or len(keypoints) < 17 * 3: return []
        
        # 1. Parse Keypoints (x, y)
        current_kpts = []
        for i in range(0, len(keypoints), 3):
            current_kpts.append((keypoints[i], keypoints[i+1]))
            
        # 2. Smooth Keypoints (Moving Average)
        self.history.append(current_kpts)
        if len(self.history) > self.history_size:
            self.history.pop(0)

        avg_kpts = []
        for i in range(17):
            sx = sum(frame[i][0] for frame in self.history)
            sy = sum(frame[i][1] for frame in self.history)
            n = len(self.history)
            avg_kpts.append((sx/n, sy/n))

        return self._analyze(avg_kpts)

    def _analyze(self, kp):
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

        # [SAFETY] Kiểm tra nếu thiếu các điểm quan trọng (Vai hoặc Hông)
        # Nếu thiếu Hông (11, 12) -> Không thể tính Spine -> Bỏ qua Body State
        has_hips = (kp[11][0] != 0 and kp[12][0] != 0)
        has_shoulders = (kp[5][0] != 0 and kp[6][0] != 0)

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
        # [STRICT LOGIC] Góc A (Vai) và Góc B (Khuỷu)
        # Góc A: Giữa thân dưới (Spine Down) và bắp tay (Vai -> Khuỷu)
        # Góc B: Góc trong khuỷu tay (180 là thẳng, 90 là vuông)
        
        if has_hips and has_shoulders:
            spine_down = (-spine[0], -spine[1])
        else:
            spine_down = (0, 1)

        l_status = None
        r_status = None

        # --- TAY TRÁI (Left Arm) ---
        # Cần: Vai(5), Khuỷu(7), Cổ tay(9)
        if kp[5][0] != 0 and kp[7][0] != 0 and kp[9][0] != 0:
            # Góc A: Thân dưới vs Vai->Khuỷu
            v_sho_elb = vec(kp[5], kp[7])
            ang_A = abs(angle(spine_down, v_sho_elb))
            
            # Góc B: Khuỷu->Vai vs Khuỷu->Cổ tay (Góc trong khuỷu tay)
            v_elb_sho = vec(kp[7], kp[5])
            v_elb_wri = vec(kp[7], kp[9])
            ang_B = abs(angle(v_elb_sho, v_elb_wri))
            
            # [NEW] Góc C: Vai->Hông vs Vai->Cổ tay
            ang_C = 0
            if kp[11][0] != 0:
                v_sho_hip = vec(kp[5], kp[11])
                v_sho_wri = vec(kp[5], kp[9])
                ang_C = abs(angle(v_sho_hip, v_sho_wri))
            
            if 140 < ang_A < 180 and 75 < ang_B < 90:
                l_status = "Trai Cao Vuong"
            elif 70 < ang_A < 100 and 60 < ang_B < 100:
                l_status = "Trai Vuong"
            elif 70 < ang_A < 100 and 140 < ang_B < 180:
                l_status = "Trai Ngang"
            elif 140 < ang_C < 180:
                l_status = "Trai Cao"

        # --- TAY PHẢI (Right Arm) ---
        # Cần: Vai(6), Khuỷu(8), Cổ tay(10)
        if kp[6][0] != 0 and kp[8][0] != 0 and kp[10][0] != 0:
            # Góc A: Thân dưới vs Vai->Khuỷu
            v_sho_elb = vec(kp[6], kp[8])
            ang_A = abs(angle(spine_down, v_sho_elb))
            
            # Góc B: Khuỷu->Vai vs Khuỷu->Cổ tay
            v_elb_sho = vec(kp[8], kp[6])
            v_elb_wri = vec(kp[8], kp[10])
            ang_B = abs(angle(v_elb_sho, v_elb_wri))
            
            # [NEW] Góc C: Vai->Hông vs Vai->Cổ tay
            ang_C = 0
            if kp[12][0] != 0:
                v_sho_hip = vec(kp[6], kp[12])
                v_sho_wri = vec(kp[6], kp[10])
                ang_C = abs(angle(v_sho_hip, v_sho_wri))
            
            if 140 < ang_A < 180 and 75 < ang_B < 90:
                r_status = "Phai Cao Vuong"
            elif 70 < ang_A < 100 and 60 < ang_B < 100:
                r_status = "Phai Vuong"
            elif 70 < ang_A < 100 and 140 < ang_B < 180:
                r_status = "Phai Ngang"
            # [UPDATE] Mở rộng góc A lên 180 để bắt được tay giơ thẳng đứng
            elif 140 < ang_C < 180:
                r_status = "Phai Cao"

        # --- 3. COMBINED GESTURES (Tư thế phối hợp) ---
        # Logic mới: Kết hợp từ trạng thái đơn lẻ "Cao Vuong"

        # Tổng hợp trạng thái
        # [UPDATE] Ưu tiên hiển thị tư thế kết hợp, ẩn tư thế con
        
        # [NEW LOGIC] Cheo Tay Tren Dau (Emergency Stop) - Hình học
        is_crossed = False
        if has_shoulders and kp[9][0] != 0 and kp[10][0] != 0:
            # Mốc Y: Mũi (0) hoặc Trung điểm vai
            ref_y = kp[0][1] if kp[0][0] != 0 else (kp[5][1] + kp[6][1])/2
            # Check 1: Tay cao hơn đầu
            wrists_up = kp[9][1] < ref_y and kp[10][1] < ref_y
            # Check 2: Hai tay gần nhau
            sho_width = dist(kp[5], kp[6])
            
            # [FIX] Dùng độ dài thân (Vai-Hông) làm tham chiếu phụ vì khi giơ tay vai thường bị co lại
            torso_len = dist(kp[5], kp[11]) if kp[11][0] != 0 else 0
            ref_len = max(sho_width, torso_len) # Lấy thước đo lớn hơn để ổn định
            
            wrist_dist = dist(kp[9], kp[10])
            if wrists_up and wrist_dist < (ref_len * 0.8):
                is_crossed = True

        if is_crossed:
            status.append("Cheo Tay Tren Dau")
        elif l_status == "Trai Ngang" and r_status == "Phai Ngang":
            status.append("Hai Tay Ngang")
        elif l_status == "Trai Cao" and r_status == "Phai Cao":
            status.append("Tay Chu V")
        else:
            if l_status: status.append(l_status)
            if r_status: status.append(r_status)
        
        return status