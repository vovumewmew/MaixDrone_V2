import math
import config

class OneEuroFilter:
    def __init__(self, t0, x0, dx0=0.0, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = float(x0)
        self.dx_prev = float(dx0)
        self.t_prev = float(t0)

    def smoothing_factor(self, t_e, cutoff):
        r = 2 * math.pi * cutoff * t_e
        return r / (r + 1)

    def exponential_smoothing(self, a, x, x_prev):
        return a * x + (1 - a) * x_prev

    def __call__(self, t, x):
        t_e = t - self.t_prev
        if t_e <= 0.0: return self.x_prev

        # Tính đạo hàm (vận tốc thay đổi)
        a_d = self.smoothing_factor(t_e, self.d_cutoff)
        dx = (x - self.x_prev) / t_e
        dx_hat = self.exponential_smoothing(a_d, dx, self.dx_prev)

        # Tính cutoff tần số dựa trên vận tốc (Đây là bí mật của One Euro)
        # Vận tốc càng lớn -> Cutoff càng lớn -> Ít lọc -> Bám sát chuyển động
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        a = self.smoothing_factor(t_e, cutoff)
        
        # Lọc giá trị
        x_hat = self.exponential_smoothing(a, x, self.x_prev)

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat

class KinematicFilter:
    def __init__(self, tolerance, deletion_multiplier):
        self.tolerance = tolerance
        self.deletion_multiplier = deletion_multiplier
        # Định nghĩa cây xương: Child -> Parent
        # [UPDATE] Sắp xếp lại thứ tự xử lý: Gốc -> Ngọn (Root -> Leaf)
        # Sửa điểm cha (Khuỷu/Gối) trước, rồi mới sửa điểm con (Cổ tay/Cổ chân)
        # Điều này giúp cả cánh tay/chân bám chặt vào thân người
        self.parents = {
            7: 5, 9: 7,     # Tay trái: Khuỷu->Vai, rồi Cổ tay->Khuỷu
            8: 6, 10: 8,    # Tay phải
            13: 11, 15: 13, # Chân trái
            14: 12, 16: 14  # Chân phải
        }
        # [THAY ĐỔI LỚN] Sử dụng Tỷ lệ Giải phẫu Chuẩn (Anatomical Ratios)
        # Thay vì học từ dữ liệu nhiễu, ta ép xương phải đúng tỷ lệ so với chiều cao Box
        self.ratios = {
            (7, 5): 0.16, (9, 7): 0.14,   # Cánh tay trên/dưới (~15% chiều cao)
            (8, 6): 0.16, (10, 8): 0.14,
            (13, 11): 0.23, (15, 13): 0.20, # Đùi/Cẳng chân (~22% chiều cao)
            (14, 12): 0.23, (16, 14): 0.20
        }

    def update(self, kpts, box_h):
        # Copy để không sửa trực tiếp mảng input
        out_kpts = list(kpts)

        for child, parent in self.parents.items():
            # [FIX] Lấy dữ liệu trực tiếp từ out_kpts để cập nhật theo thời gian thực (Cascade)
            if (child * 3 + 2) >= len(out_kpts) or (parent * 3 + 2) >= len(out_kpts): continue
            
            # Lấy độ tin cậy hiện tại
            conf_c = out_kpts[child*3+2]
            conf_p = out_kpts[parent*3+2]
            
            # [DOMINO] Nếu cha bị xóa (conf=0) -> Con cũng bị xóa theo (Orphan Removal)
            if conf_p <= 0:
                out_kpts[child*3+2] = 0.0
                continue
            
            if conf_c <= 0: continue
            
            # Lấy toạ độ
            cx, cy = out_kpts[child*3], out_kpts[child*3+1]
            px, py = out_kpts[parent*3], out_kpts[parent*3+1]
            
            dx = cx - px
            dy = cy - py
            curr_dist = math.sqrt(dx*dx + dy*dy)
            
            if curr_dist == 0: continue
            
            bone_id = (child, parent)
            
            # [NẮN XƯƠNG] Tính độ dài chuẩn dựa trên chiều cao Box
            target_len = box_h * self.ratios.get(bone_id, 0.2)
            
            # Cho phép sai số linh hoạt (từ config)
            min_len = target_len * (1.0 - self.tolerance)
            max_len = target_len * (1.0 + self.tolerance)
            
            scale = 1.0
            if curr_dist < min_len: scale = min_len / curr_dist
            elif curr_dist > max_len: scale = max_len / curr_dist
            
            if scale != 1.0:
                # [CHIẾN THUẬT 2] The Leash Constraint (Sợi dây xích)
                # Nếu khoảng cách > Chiều dài xương cho phép (dính tường) -> Cắt dây (Xóa điểm)
                if curr_dist > max_len * self.deletion_multiplier:
                    out_kpts[child*3+2] = 0.0 
                else:
                    # Kéo điểm con về vị trí hợp lý (giữ nguyên hướng, chỉ chỉnh độ dài)
                    out_kpts[child*3] = px + dx * scale
                    out_kpts[child*3+1] = py + dy * scale
                    
        return out_kpts

class AnatomyFilter:
    def __init__(self, min_valid_keypoints):
        self.min_valid_keypoints = min_valid_keypoints
        
    def check(self, kpts, box):
        """
        Global Check: Kiểm tra cấu trúc cơ thể có hợp lý không.
        Trả về: True (Hợp lý) / False (Bất thường)
        """
        bx, by, bw, bh = box
        # Parse điểm quan trọng
        # 0: Mũi, 5,6: Vai, 11,12: Hông
        pts = {}
        for i in range(0, len(kpts), 3):
            if i + 2 >= len(kpts): break # [FIX] Kiểm tra an toàn
            pts[i//3] = {'y': kpts[i+1], 'c': kpts[i+2]}
            
        # [MỚI] Kiểm tra số lượng điểm tin cậy
        valid_cnt = sum(1 for p in pts.values() if p['c'] > config.POSE_CONF_THRESHOLD)
        if valid_cnt < self.min_valid_keypoints: 
            return False
            
        # 1. Kiểm tra Đầu - Vai (Đầu thường phải cao hơn Vai)
        # Lưu ý: Trục Y hướng xuống, nên y_nose < y_shoulder là đúng
        if 0 in pts and 5 in pts and 6 in pts:
            if pts[0]['c'] > 0.5 and pts[5]['c'] > 0.5 and pts[6]['c'] > 0.5:
                shoulder_y = (pts[5]['y'] + pts[6]['y']) / 2
                # Nếu mũi thấp hơn vai quá nhiều (người lộn ngược hoặc detect sai) -> Cảnh báo
                if pts[0]['y'] > shoulder_y + 20: return False
        
        # 2. [MỚI] Kiểm tra Trọng tâm (Centroid Check)
        # Trọng tâm của bộ xương phải nằm gần tâm của Box
        sum_x, sum_y, count = 0, 0, 0
        for p in pts.values():
            if p['c'] > 0.5:
                # sum_x += p['x'] # Logic này bị lỗi, cần sửa ở v2
                sum_y += p['y']
                count += 1
        
        return True

class PoseFilter:
    def __init__(self):
        # Quản lý bộ lọc cho từng đối tượng
        self.filters = {} 
        
        # --- Nạp cấu hình từ config.py ---
        self.kpt_conf_thresh = config.POSE_CONF_THRESHOLD
        self.edge_conf_thresh = config.EDGE_CONF_THRESHOLD
        self.min_valid_kpts = config.MIN_VALID_KEYPOINTS
        kinematic_tolerance = config.KINEMATIC_TOLERANCE
        kinematic_del_multiplier = config.KINEMATIC_DELETION_MULTIPLIER
        
        # [FIX TRIỆT ĐỂ] Tăng Beta lên 0.3 để bám sát người (hết lag), giữ min_cutoff 0.5 để chống rung
        self.box_cfg = {'min_cutoff': 0.5, 'beta': 0.3, 'd_cutoff': 1.0}
        
        # [FIX TRIỆT ĐỂ] Pose cũng cần nhạy hơn để tay chân không bị trễ nhịp
        self.kpt_cfg = {'min_cutoff': 0.5, 'beta': 0.3, 'd_cutoff': 1.0}
        
        # --- Khởi tạo các bộ lọc phụ với cấu hình đã nạp ---
        self.kinematics = {} # Sẽ được tạo cho mỗi ID mới
        self.kinematic_template = KinematicFilter(
            tolerance=kinematic_tolerance, 
            deletion_multiplier=kinematic_del_multiplier
        )
        self.anatomy = AnatomyFilter(min_valid_keypoints=self.min_valid_kpts)
        
    def filter_box(self, oid, t, box):
        if oid not in self.filters:
            self.filters[oid] = {
                'box': [OneEuroFilter(t, x, **self.box_cfg) for x in box],
                'kpts': {}
            }
        
        return [f(t, x) for f, x in zip(self.filters[oid]['box'], box)]

    def filter_kpts(self, oid, t, kpts, box):
        if oid not in self.filters: return kpts # Chưa init thì trả về gốc
        
        bx, by, bw, bh = box
        
        filtered = []
        for i in range(0, len(kpts), 3):
            idx = i // 3
            x, y, conf = kpts[i], kpts[i+1], kpts[i+2]

            # [CHIẾN THUẬT 1] Center Bias Weighting (Trọng số trung tâm)
            # Nguyên lý: Người ở giữa, rác ở rìa. Giảm tín nhiệm các điểm xa tâm.
            if bw > 0 and bh > 0:
                box_cx = bx + bw / 2
                box_cy = by + bh / 2
                # Tính khoảng cách từ điểm đến tâm Box
                dist_from_center = math.sqrt((x - box_cx)**2 + (y - box_cy)**2)
                max_radius = math.sqrt((bw/2)**2 + (bh/2)**2)
                
                # Phạt: Càng xa tâm càng trừ điểm. Tối đa trừ 0.4 (40%) độ tin cậy.
                if max_radius > 0:
                    penalty = (dist_from_center / max_radius) * 0.4
                    conf -= penalty

            # [ALGO 1] Cổng Gác (Confidence Thresholding) - Dùng config
            if conf < self.kpt_conf_thresh:
                filtered.extend([x, y, 0.0])
                continue

            # [ALGO 2] Ràng buộc Hình học Hộp (Bounding Box Constraint)
            if idx in [0, 1, 2, 3, 4, 5, 6, 11, 12]: # Đầu, Vai, Hông (Core) -> Siết chặt
                margin_x = bw * 0.03
                margin_y = bh * 0.03
            elif idx in [7, 8, 13, 14]: # Khuỷu, Gối -> Vừa phải
                margin_x = bw * 0.08
                margin_y = bh * 0.08
            else: # Cổ tay, Cổ chân -> Nới lỏng
                margin_x = bw * 0.15
                margin_y = bh * 0.15
                
            if x < bx - margin_x or x > bx + bw + margin_x or \
               y < by - margin_y or y > by + bh + margin_y:
                filtered.extend([x, y, 0.0])
                continue

            # [ALGO 5] Zone Constraint (Phân vùng cơ thể)
            if bh > bw:
                if idx <= 6 and y > by + bh * 0.6: # Thân trên không ở dưới
                    filtered.extend([x, y, 0.0])
                    continue
                if idx in [9, 10] and y > by + bh * 0.85: # Cổ tay không ở chân
                    filtered.extend([x, y, 0.0])
                    continue

            # [ALGO 4] Edge Penalty (Phạt điểm ở mép) - Dùng config
            # [FIX] Chỉ phạt điểm ở mép DƯỚI (chân chạm biên ảnh), bỏ phạt mép trái/phải/trên
            # Vì tay thường xuyên chạm mép trái/phải của Box.
            if y > by + bh * 0.95: 
                 if conf < self.edge_conf_thresh:
                    filtered.extend([x, y, 0.0])
                    continue
            
            # Bỏ đoạn check is_near_edge cho các cạnh còn lại

            if idx not in self.filters[oid]['kpts']:
                self.filters[oid]['kpts'][idx] = [
                    OneEuroFilter(t, x, **self.kpt_cfg),
                    OneEuroFilter(t, y, **self.kpt_cfg)
                ]
            
            fx = self.filters[oid]['kpts'][idx][0](t, x)
            fy = self.filters[oid]['kpts'][idx][1](t, y)
            filtered.extend([fx, fy, conf])
                
        # --- GIAI ĐOẠN 2: KINEMATIC FILTER (Ràng buộc xương) ---
        if oid not in self.kinematics:
            self.kinematics[oid] = self.kinematic_template
            
        kpts_kinematic = self.kinematics[oid].update(filtered, bh)
        
        # --- GIAI ĐOẠN 3: ANATOMY CHECK & REFINE (Global Check) ---
        # Hàm này sẽ trả về danh sách các điểm đã được tinh lọc
        refined_kpts = self.check_anatomy_v2(kpts_kinematic, box)

        return refined_kpts

    def check_anatomy_v2(self, kpts, box):
        bx, by, bw, bh = box

        # --- Giai đoạn 1: Lấy tất cả các điểm hợp lệ ban đầu và GHI NHỚ INDEX ---
        valid_points = []
        for i in range(0, len(kpts), 3):
            if i + 2 >= len(kpts): break
            # Chỉ xét các điểm có độ tin cậy ban đầu, được lọc bởi các bộ lọc trước
            if kpts[i+2] > 0:
                valid_points.append({'idx': i//3, 'x': kpts[i], 'y': kpts[i+1], 'c': kpts[i+2]})

        if len(valid_points) < self.min_valid_kpts: return []

        # [ANTI-GHOST] Kiểm tra "Xương Sống" (Core Joints)
        # Một người thật phải có ít nhất 1 điểm thuộc thân mình (Vai hoặc Hông)
        # Nếu chỉ có tay/chân/đầu bay lơ lửng -> Là ma (Ghost) -> Loại bỏ
        has_core = False
        for p in valid_points:
            if p['idx'] in [5, 6, 11, 12]: # 5,6: Vai | 11,12: Hông
                has_core = True
                break
        if not has_core: return []

        # --- Giai đoạn 2: Kiểm tra Trọng tâm đơn giản (Simple Centroid Check) ---
        # [FIX] Bỏ thuật toán lặp (Iterative) vì nó cắt mất tay chân ở xa trọng tâm.
        # Chỉ tính trọng tâm một lần để kiểm tra xem người có bị lệch quá xa khỏi Box không.
        
        sum_x = sum(p['x'] for p in valid_points)
        sum_y = sum(p['y'] for p in valid_points)
        centroid = (sum_x / len(valid_points), sum_y / len(valid_points))

        # --- Giai đoạn 3: Kiểm tra cuối cùng và tạo list output ---
        if len(valid_points) < self.min_valid_kpts: return []

        # Kiểm tra trọng tâm của cụm điểm cuối cùng so với tâm Box
        center_x, center_y = centroid
        box_cx = bx + bw / 2
        box_cy = by + bh / 2
        
        dist = math.sqrt((center_x - box_cx)**2 + (center_y - box_cy)**2)
        max_dist = math.sqrt(bw**2 + bh**2) * 0.3
        
        if dist > max_dist: return []
        
        # --- TẠO OUTPUT ---
        # Tạo một danh sách rỗng (toàn số 0) và điền các điểm hợp lệ vào đúng vị trí
        final_kpts = [0.0] * 17 * 3
        for p in valid_points:
            idx = p['idx']
            final_kpts[idx * 3] = p['x']
            final_kpts[idx * 3 + 1] = p['y']
            final_kpts[idx * 3 + 2] = p['c']
            
        return final_kpts