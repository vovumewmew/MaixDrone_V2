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
        # [FIX 3] Tỷ lệ giải phẫu cơ bản (Base Ratios)
        # Sẽ được nhân với chiều cao tham chiếu (Reference Height)
        self.base_ratios = {
            (7, 5): 0.16, (9, 7): 0.14,     # Tay
            (8, 6): 0.16, (10, 8): 0.14,
            (13, 11): 0.23, (15, 13): 0.20, # Chân
            (14, 12): 0.23, (16, 14): 0.20
        }

    def update(self, kpts, box_h):
        # Copy để không sửa trực tiếp mảng input
        out_kpts = list(kpts)

        # [FIX 3] Tính chiều cao tham chiếu ĐỘNG (Dynamic Reference Height)
        # Ưu tiên dùng chiều dài thân mình (Torso Length) * 3.0 để ước lượng chiều cao thật
        # Nếu không thấy thân mình, mới dùng chiều cao Box.
        ref_height = box_h
        
        # Lấy toạ độ Vai và Hông (nếu có)
        # 5,6: Vai | 11,12: Hông
        if (out_kpts[5*3+2] > 0 and out_kpts[6*3+2] > 0 and 
            out_kpts[11*3+2] > 0 and out_kpts[12*3+2] > 0):
            
            shoulder_y = (out_kpts[5*3+1] + out_kpts[6*3+1]) / 2
            hip_y = (out_kpts[11*3+1] + out_kpts[12*3+1]) / 2
            torso_len = abs(hip_y - shoulder_y)
            
            if torso_len > 0:
                # Thân mình thường chiếm 1/3 chiều cao cơ thể -> Nhân 3 để ra chiều cao chuẩn
                ref_height = torso_len * 3.0

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
            # Dùng ref_height thay vì box_h cố định
            target_len = ref_height * self.base_ratios.get(bone_id, 0.2)
            
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

class PoseQualityScorer:
    def __init__(self):
        self.weights = {
            'structural': 0.3,     # Cấu trúc cơ thể hợp lý
            'symmetry': 0.2,       # Tính đối xứng
            'kinematic': 0.25,     # Tuân thủ động học
            'temporal': 0.15,      # Ổn định theo thời gian
            'coverage': 0.1        # Độ phủ keypoints
        }
    
    def score_pose(self, kpts, box, prev_kpts=None):
        """Tính điểm chất lượng tổng thể của pose (0-1)"""
        if not kpts:
            return {'total': 0.0, 'grade': 'INVALID', 'breakdown': {}}
            
        scores = {}
        
        # 1. Structural Score - Cấu trúc cơ thể
        scores['structural'] = self._structural_score(kpts, box)
        
        # 2. Symmetry Score - Đối xứng trái/phải
        scores['symmetry'] = self._symmetry_score(kpts)
        
        # 3. Kinematic Score - Độ dài xương hợp lý
        scores['kinematic'] = self._kinematic_score(kpts, box[3])  # box height
        
        # 4. Temporal Score - Ổn định theo thời gian
        if prev_kpts:
            scores['temporal'] = self._temporal_score(kpts, prev_kpts)
        else:
            scores['temporal'] = 0.7  # Default nếu không có history
            
        # 5. Coverage Score - Số lượng keypoints phát hiện được
        scores['coverage'] = self._coverage_score(kpts)
        
        # Tính tổng trọng số
        total_score = sum(scores[key] * self.weights[key] for key in scores)
        
        return {
            'total': total_score,
            'breakdown': scores,
            'grade': self._assign_grade(total_score)
        }
    
    def _structural_score(self, kpts, box):
        """Điểm dựa trên cấu trúc cơ thể hợp lý"""
        bx, by, bw, bh = box
        pts = {}
        for i in range(0, len(kpts), 3):
            if i + 2 < len(kpts) and kpts[i+2] > 0.1:
                pts[i//3] = {'x': kpts[i], 'y': kpts[i+1], 'c': kpts[i+2]}
        
        score = 0.0
        # Quy tắc 1: Đầu phải ở trên vai
        if 0 in pts and 5 in pts and 6 in pts:
            nose_y = pts[0]['y']
            shoulder_y = min(pts[5]['y'], pts[6]['y'])
            if nose_y < shoulder_y - 10: score += 0.2
        
        # Quy tắc 2: Hông phải dưới vai
        if 5 in pts and 6 in pts and 11 in pts and 12 in pts:
            shoulder_y = min(pts[5]['y'], pts[6]['y'])
            hip_y = max(pts[11]['y'], pts[12]['y'])
            if hip_y > shoulder_y + 20: score += 0.2
        
        # Quy tắc 3: Trọng tâm keypoints nằm trong bounding box
        if len(pts) > 3:
            center_x = sum(p['x'] for p in pts.values()) / len(pts)
            center_y = sum(p['y'] for p in pts.values()) / len(pts)
            if (bx <= center_x <= bx + bw and by <= center_y <= by + bh):
                score += 0.3
            else: score -= 0.2
        
        # Quy tắc 4: Không có keypoints nào bay quá xa
        outliers = 0
        for p in pts.values():
            dist_to_center = math.sqrt((p['x'] - bx - bw/2)**2 + (p['y'] - by - bh/2)**2)
            max_allowed = math.sqrt(bw**2 + bh**2) * 0.8
            if dist_to_center > max_allowed: outliers += 1
        
        if outliers == 0: score += 0.3
        elif outliers <= 2: score += 0.1
        else: score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def _symmetry_score(self, kpts):
        left_right_pairs = [(5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16)]
        valid_pairs = 0
        symmetry_score = 0.0
        for left, right in left_right_pairs:
            idx_l, idx_r = left * 3, right * 3
            if (idx_l + 2 < len(kpts) and idx_r + 2 < len(kpts) and
                kpts[idx_l + 2] > 0.1 and kpts[idx_r + 2] > 0.1):
                y_l, y_r = kpts[idx_l + 1], kpts[idx_r + 1]
                height_diff = abs(y_l - y_r)
                pair_score = max(0, 1.0 - height_diff / 50)
                symmetry_score += pair_score
                valid_pairs += 1
        return symmetry_score / valid_pairs if valid_pairs > 0 else 0.5
    
    def _kinematic_score(self, kpts, box_height):
        bone_ratios = {
            (5, 7): 0.16, (7, 9): 0.14, (6, 8): 0.16, (8, 10): 0.14,
            (11, 13): 0.23, (13, 15): 0.20, (12, 14): 0.23, (14, 16): 0.20
        }
        valid_bones = 0
        kinematic_score = 0.0
        for (j1, j2), target_ratio in bone_ratios.items():
            idx1, idx2 = j1 * 3, j2 * 3
            if (idx1 + 2 < len(kpts) and idx2 + 2 < len(kpts) and
                kpts[idx1 + 2] > 0.3 and kpts[idx2 + 2] > 0.3):
                x1, y1 = kpts[idx1], kpts[idx1 + 1]
                x2, y2 = kpts[idx2], kpts[idx2 + 1]
                bone_length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
                ideal_length = box_height * target_ratio
                ratio = bone_length / ideal_length if ideal_length > 0 else 1
                if 0.5 <= ratio <= 2.0:
                    bone_score = 1.0 - abs(ratio - 1.0)
                    kinematic_score += bone_score
                    valid_bones += 1
        return kinematic_score / valid_bones if valid_bones > 0 else 0.5
    
    def _temporal_score(self, curr_kpts, prev_kpts):
        if len(curr_kpts) != len(prev_kpts): return 0.5
        total_movement = 0
        valid_points = 0
        for i in range(0, len(curr_kpts), 3):
            if i + 2 >= len(curr_kpts) or i + 2 >= len(prev_kpts): continue
            if curr_kpts[i+2] > 0.1 and prev_kpts[i+2] > 0.1:
                dx = curr_kpts[i] - prev_kpts[i]
                dy = curr_kpts[i+1] - prev_kpts[i+1]
                total_movement += math.sqrt(dx*dx + dy*dy)
                valid_points += 1
        if valid_points == 0: return 0.5
        avg_movement = total_movement / valid_points
        if avg_movement < 5: return 1.0
        elif avg_movement < 20: return 0.8
        elif avg_movement < 50: return 0.5
        else: return 0.2
    
    def _coverage_score(self, kpts):
        total_points = 17
        detected_points = sum(1 for i in range(0, len(kpts), 3) if kpts[i+2] > 0.1)
        coverage_ratio = detected_points / total_points
        if coverage_ratio >= 0.8: return 1.0
        elif coverage_ratio >= 0.6: return 0.8
        elif coverage_ratio >= 0.4: return 0.6
        elif coverage_ratio >= 0.2: return 0.4
        else: return 0.2
    
    def _assign_grade(self, score):
        if score >= 0.8: return "EXCELLENT"
        elif score >= 0.6: return "GOOD"
        elif score >= 0.4: return "FAIR"
        elif score >= 0.2: return "POOR"
        else: return "INVALID"

class VectorScorer:
    """
    Thuật toán so sánh cấu trúc hình học dựa trên Cosine Similarity của các vector xương.
    (Chuyển thể từ code Python/Numpy sang Pure Python cho MaixCam)
    """
    def __init__(self):
        # Định nghĩa các cặp nối xương chuẩn COCO (17 điểm)
        self.SKELETON_EDGES = [
            (15, 13), (13, 11), (16, 14), (14, 12), (11, 12), (5, 11), (6, 12), (5, 6),
            (5, 7), (7, 9), (6, 8), (8, 10), (1, 2), (0, 1), (0, 2), (1, 3), (2, 4)
        ]

    def compute(self, curr_kpts, target_kpts):
        """
        Tính điểm tương đồng giữa pose hiện tại và pose mục tiêu (frame trước).
        Output: 0.0 -> 100.0
        """
        if not curr_kpts or not target_kpts: return 0.0
        
        scores = []
        for u, v in self.SKELETON_EDGES:
            # Kiểm tra index an toàn
            if (u*3+2 >= len(curr_kpts) or v*3+2 >= len(curr_kpts) or
                u*3+2 >= len(target_kpts) or v*3+2 >= len(target_kpts)): continue

            # Chỉ tính nếu cả 2 đầu xương đều được detect ở cả 2 frame
            if (curr_kpts[u*3+2] > 0 and curr_kpts[v*3+2] > 0 and
                target_kpts[u*3+2] > 0 and target_kpts[v*3+2] > 0):
                
                # Vector U (Current)
                ux, uy = curr_kpts[v*3] - curr_kpts[u*3], curr_kpts[v*3+1] - curr_kpts[u*3+1]
                # Vector V (Target/Previous)
                vx, vy = target_kpts[v*3] - target_kpts[u*3], target_kpts[v*3+1] - target_kpts[u*3+1]
                
                # Dot product & Norm
                dot = ux*vx + uy*vy
                norm_u = math.sqrt(ux*ux + uy*uy)
                norm_v = math.sqrt(vx*vx + vy*vy)
                
                if norm_u > 0 and norm_v > 0:
                    sim = dot / (norm_u * norm_v)
                    scores.append(sim)
        
        # Trả về trung bình cộng * 100
        return (sum(scores) / len(scores)) * 100 if scores else 0.0

class PoseFilter:
    def __init__(self):
        # Quản lý bộ lọc cho từng đối tượng
        self.filters = {} 
        
        # --- Nạp cấu hình từ config.py ---
        self.kpt_conf_thresh = config.POSE_CONF_THRESHOLD
        self.edge_conf_thresh = config.EDGE_CONF_THRESHOLD
        self.min_valid_kpts = config.MIN_VALID_KEYPOINTS
        self.max_jump_ratio = config.MAX_KPT_JUMP_RATIO # [MỚI]
        kinematic_tolerance = config.KINEMATIC_TOLERANCE
        kinematic_del_multiplier = config.KINEMATIC_DELETION_MULTIPLIER
        
        # [TUNING] Tinh chỉnh bộ lọc cho Box
        # [RESET] Cấu hình chuẩn, cân bằng
        self.box_cfg = {'min_cutoff': 0.1, 'beta': 0.1, 'd_cutoff': 1.0}
        
        # [TUNING] Tinh chỉnh bộ lọc cho Keypoints
        # [BALANCED] Beta = 0.05: Đủ để chống rung nhưng vẫn bám theo tay
        self.kpt_cfg = {'min_cutoff': 0.5, 'beta': 0.05, 'd_cutoff': 1.0}
        
        # --- Khởi tạo các bộ lọc phụ với cấu hình đã nạp ---
        self.kinematics = {} # Sẽ được tạo cho mỗi ID mới
        self.kinematic_template = KinematicFilter(
            tolerance=kinematic_tolerance, 
            deletion_multiplier=kinematic_del_multiplier
        )
        self.anatomy = AnatomyFilter(min_valid_keypoints=self.min_valid_kpts)
        
        # [MỚI] Bộ đánh giá chất lượng
        self.quality_scorer = PoseQualityScorer()
        self.pose_history = {} # Lưu lịch sử pose để tính điểm Temporal
        
        # [MỚI] Bộ đánh giá Vector (Geometry Structure)
        self.vector_scorer = VectorScorer()
        
    def filter_box(self, oid, t, box):
        if oid not in self.filters:
            self.filters[oid] = {
                'box': [OneEuroFilter(t, x, **self.box_cfg) for x in box],
                'kpts': {}
            }
        
        return [f(t, x) for f, x in zip(self.filters[oid]['box'], box)]

    def filter_kpts(self, oid, t, kpts, box):
        if oid not in self.filters: 
            self.filters[oid] = {'box': [], 'kpts': {}}
            # Trả về raw và quality rỗng cho frame đầu tiên để tránh lỗi unpack
            return kpts, {'total': 0.0, 'grade': 'INVALID', 'breakdown': {}}
        
        bx, by, bw, bh = box
        
        filtered = []
        for i in range(0, len(kpts), 3):
            idx = i // 3
            x, y, conf = kpts[i], kpts[i+1], kpts[i+2]

            # [FIX] Gỡ bỏ Center Bias vì nó làm mất tay khi dang rộng.
            
            # [LỚP 1] Dynamic Thresholding -> ĐÃ GỠ BỎ
            # Sử dụng ngưỡng cố định thấp từ config để đảm bảo hiện đủ 17 điểm
            required_conf = self.kpt_conf_thresh
            
            # Nếu độ tin cậy thấp hơn mức yêu cầu -> Bỏ
            if conf < required_conf:
                filtered.extend([x, y, 0.0])
                continue

            # [ALGO 2] Ràng buộc Hình học Hộp (Bounding Box Constraint)
            # [ACTIVE] Bật lại để loại bỏ điểm ma nằm xa Box
            if idx in [0, 1, 2, 3, 4, 5, 6, 11, 12]: # Core -> Siết chặt
                margin_x = bw * 0.1
                margin_y = bh * 0.1
            elif idx in [7, 8, 13, 14]: # Khuỷu/Gối -> Vừa phải
                margin_x = bw * 0.3 
                margin_y = bh * 0.3
            else: # Cổ tay/chân -> Nới lỏng (cho phép vươn ra ngoài 50% chiều rộng box)
                margin_x = bw * 0.5 
                margin_y = bh * 0.5
                
            if x < bx - margin_x or x > bx + bw + margin_x or \
               y < by - margin_y or y > by + bh + margin_y:
                filtered.extend([x, y, 0.0])
                continue

            # [RAW MODE] Tắt toàn bộ các bộ lọc logic (Zone, Edge, Teleport)
            # Để đảm bảo mọi điểm AI nhìn thấy đều được hiển thị
            if idx in self.filters[oid]['kpts']:
                pass 

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
            
        # [ACTIVE] Bật lại Kinematic để loại bỏ các điểm nối sai (tay dài bất thường)
        kpts_kinematic = self.kinematics[oid].update(filtered, bh)
        
        # --- GIAI ĐOẠN 3: ANATOMY CHECK & REFINE (Global Check) ---
        # Hàm này sẽ trả về danh sách các điểm đã được tinh lọc
        # [BYPASS] Tạm tắt kiểm tra giải phẫu để tránh trả về danh sách rỗng nếu ít điểm
        refined_kpts = kpts_kinematic
        
        # [MỚI] Tính điểm chất lượng (Quality Score)
        prev_kpts = self.pose_history.get(oid, None)
        quality = self.quality_scorer.score_pose(refined_kpts, box, prev_kpts)
        
        # Lưu lại lịch sử cho frame sau
        if refined_kpts:
            self.pose_history[oid] = refined_kpts
            
        return refined_kpts, quality

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