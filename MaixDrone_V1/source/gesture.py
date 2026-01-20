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
        # Upper Arm Vector (Shoulder to Elbow)
        # Cần check xem có tay không
        if kp[7][0] == 0 or kp[8][0] == 0: return status # Thiếu khuỷu tay -> Thoát

        l_arm = vec(kp[5], kp[7])
        r_arm = vec(kp[6], kp[8])
        
        # Angle relative to Spine (inverted to point down)
        if has_hips and has_shoulders:
            spine_down = (-spine[0], -spine[1])
        else:
            spine_down = (0, 1) # Giả định người đứng thẳng
        
        l_arm_ang = abs(angle(spine_down, l_arm))
        r_arm_ang = abs(angle(spine_down, r_arm))
        
        # [OFFICIAL LOGIC] Phân loại trạng thái tay chi tiết theo MaixPy
        # < 20: Drooping (Thõng xuống)
        # < 80: Raised (Nâng nhẹ)
        # < 110: Horizontal (Ngang vai)
        # < 160: High (Giơ cao)
        # >= 160: Upright (Thẳng đứng)
        
        def get_arm_state(ang):
            if ang < 20: return "Down"
            if ang < 80: return "Low"
            if ang < 110: return "Side"
            if ang < 160: return "High"
            return "Up"

        l_state = get_arm_state(l_arm_ang)
        r_state = get_arm_state(r_arm_ang)
        
        if (l_state == "High" or l_state == "Up") and (r_state == "High" or r_state == "Up"): status.append("Gio Tay")
        elif l_state == "Side" and r_state == "Side": status.append("Dang Tay")
        elif l_state == "Side" and (r_state == "Low" or r_state == "Down"): status.append("Dang Tay Trai")
        elif r_state == "Side" and (l_state == "Low" or l_state == "Down"): status.append("Dang Tay Phai") 
        elif l_state == "High" or l_state == "Up": status.append("Trai Len")
        elif r_state == "High" or r_state == "Up": status.append("Phai Len")
        
        return status