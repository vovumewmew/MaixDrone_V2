import math
import time
import config
from source.postprocess import PoseFilter # [RESTORE] Import bộ lọc
from source.gesture import PoseEstimator # [NEW] Import bộ phân tích cử chỉ
from source.st_gcn import STGCN_Recognizer # [NEW] Import thuật toán ST-GCN

class ObjectTracker:
    def __init__(self):
        # Lưu danh sách các đối tượng đang theo dõi
        # Format: { object_id: {'box': [x,y,w,h], 'miss': 0} }
        self.objects = {}
        self.next_id = 1
        self.max_miss_count = getattr(config, "TRACK_MAX_MISS", 12)
        self.dist_threshold = getattr(config, "TRACK_DIST_THRESHOLD", 100)
        self.max_cost_threshold = getattr(config, "TRACK_COST_THRESHOLD", 1.20)
        self.min_visible_ratio = getattr(config, "POSE_MIN_VISIBLE_RATIO", 0.35)
        self.filter = PoseFilter() # [RESTORE] Khởi tạo bộ lọc

    def update(self, ai_results):
        """
        Matching accuracy-first:
        - Ghep cap theo chi phi toan cuc (distance + IoU)
        - Uu tien du lieu thuc te, giam du doan/lam muot
        """
        t_now = time.time()

        # 1. Chuan hoa detections dau vao
        detections = []
        for res in ai_results:
            raw_box = [float(res['x']), float(res['y']), float(res['w']), float(res['h'])]
            cx, cy = self._box_center(raw_box)
            raw_points = res.get('points', [])
            detections.append({
                'box': raw_box,
                'cx': cx,
                'cy': cy,
                'res': res,
                'anchor': self._pose_anchor(raw_points),
                'visible_ratio': self._visible_ratio(raw_points)
            })

        # 2. Neu chua co object nao -> dang ky moi
        if not self.objects:
            for det in detections:
                self.register(det['res'])
            return self.get_display_objects()

        # 3. Tao tat ca cap ung vien (cost thap la tot)
        object_ids = list(self.objects.keys())
        pairs = []
        for oid in object_ids:
            data = self.objects[oid]
            old_box = data['box']
            old_vel = data.get('velocity', [0.0, 0.0, 0.0, 0.0])

            dt_match = t_now - data.get('last_time', t_now)
            if dt_match < 0.0 or dt_match > 0.35:
                dt_match = 0.0

            old_cx, old_cy = self._box_center(old_box)
            pred_cx = old_cx + old_vel[0] * dt_match
            pred_cy = old_cy + old_vel[1] * dt_match

            size_ref = max(1.0, max(old_box[2], old_box[3]))
            dynamic_th = max(40.0, min(220.0, max(self.dist_threshold, 0.8 * size_ref)))

            for det_idx, det in enumerate(detections):
                dx = pred_cx - det['cx']
                dy = pred_cy - det['cy']
                iou = self._box_iou(old_box, det['box'])

                if (abs(dx) > dynamic_th or abs(dy) > dynamic_th) and iou < 0.05:
                    continue

                dist = math.sqrt(dx * dx + dy * dy)
                if dist > dynamic_th and iou < 0.05:
                    continue

                norm_dist = dist / dynamic_th
                cost = (0.70 * norm_dist) + (0.30 * (1.0 - iou))

                # Them rang buoc "pose anchor" de giam nham ID khi cat nhau.
                old_anchor = data.get('pose_anchor')
                new_anchor = det.get('anchor')
                if old_anchor and new_anchor:
                    pose_th = max(30.0, min(180.0, 0.7 * size_ref))
                    pdx = old_anchor[0] - new_anchor[0]
                    pdy = old_anchor[1] - new_anchor[1]
                    pose_dist = math.sqrt(pdx * pdx + pdy * pdy)
                    norm_pose = min(1.5, pose_dist / pose_th)
                    cost = (0.55 * norm_dist) + (0.25 * (1.0 - iou)) + (0.20 * norm_pose)

                pairs.append((cost, oid, det_idx))

        pairs.sort(key=lambda x: x[0])

        used_objects = set()
        used_detections = set()

        # 4. Gan cap theo thu tu cost tang dan
        for cost, oid, det_idx in pairs:
            if oid in used_objects or det_idx in used_detections:
                continue
            if cost > self.max_cost_threshold:
                continue

            det = detections[det_idx]
            res = det['res']
            raw_box = det['box']
            old_data = self.objects[oid]
            old_box = old_data['box']

            dt = t_now - old_data.get('last_time', t_now)
            if dt <= 0.0:
                dt = 1e-3

            old_cx, old_cy = self._box_center(old_box)
            new_cx, new_cy = self._box_center(raw_box)
            vx = (new_cx - old_cx) / dt
            vy = (new_cy - old_cy) / dt

            prev_vel = old_data.get('velocity', [0.0, 0.0, 0.0, 0.0])
            v_alpha = 0.60
            old_data['velocity'] = [
                vx * v_alpha + prev_vel[0] * (1.0 - v_alpha),
                vy * v_alpha + prev_vel[1] * (1.0 - v_alpha),
                0.0,
                0.0
            ]

            # Accuracy-first: update box directly from detector
            old_data['box'] = raw_box
            old_data['prev_raw_box'] = raw_box
            old_data['last_time'] = t_now
            if det.get('anchor'):
                old_data['pose_anchor'] = det['anchor']

            raw_points = res.get('points', [])
            if raw_points:
                filtered_points = self.filter.filter_kpts(oid, t_now, raw_points, bbox=raw_box)
                pose_input_points = raw_points
                quality_points = filtered_points if filtered_points else raw_points
                pose_score = self._calculate_quality(raw_points, quality_points, res['score'], raw_box[3])
            else:
                filtered_points = []
                pose_input_points = []
                pose_score = 0.0

            old_data['points'] = filtered_points
            old_data['pose_score'] = pose_score

            # Motion recognition accuracy + speed:
            # chi phan tich khi do phu keypoint du cao.
            if pose_input_points and det.get('visible_ratio', 0.0) >= self.min_visible_ratio:
                gestures = old_data['estimator'].update(pose_input_points)
                st_action = old_data['st_gcn'].update(pose_input_points)
            else:
                gestures = []
                st_action = None

            if st_action == "Vay Tay Phai":
                if "Phai Cao" in gestures:
                    gestures.remove("Phai Cao")
                if "Vay Tay Phai" not in gestures:
                    gestures.append("Vay Tay Phai")

            old_data['gestures'] = gestures
            old_data['score'] = res['score']
            old_data['miss'] = 0

            used_objects.add(oid)
            used_detections.add(det_idx)

        # 5. Tang miss cho object khong duoc ghep
        for oid in object_ids:
            if oid not in used_objects:
                self.objects[oid]['miss'] += 1
                self.objects[oid]['gestures'] = []
                self.objects[oid]['points'] = []

        # 6. Dang ky detection moi chua co chu
        for det_idx, det in enumerate(detections):
            if det_idx not in used_detections:
                self.register(det['res'])

        # 7. Xoa object mat dau qua lau
        self.clean_up()

        return self.get_display_objects()

    def _box_center(self, box):
        return box[0] + box[2] / 2.0, box[1] + box[3] / 2.0

    def _box_iou(self, box_a, box_b):
        ax1, ay1 = box_a[0], box_a[1]
        ax2, ay2 = box_a[0] + box_a[2], box_a[1] + box_a[3]
        bx1, by1 = box_b[0], box_b[1]
        bx2, by2 = box_b[0] + box_b[2], box_b[1] + box_b[3]

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        area_a = max(0.0, box_a[2]) * max(0.0, box_a[3])
        area_b = max(0.0, box_b[2]) * max(0.0, box_b[3])
        union_area = area_a + area_b - inter_area

        if union_area <= 0.0:
            return 0.0
        return inter_area / union_area

    def _visible_ratio(self, points):
        if not points or len(points) < 3:
            return 0.0
        stride = 3 if len(points) % 3 == 0 else 2
        if stride != 3:
            return 1.0
        total = len(points) // 3
        if total <= 0:
            return 0.0
        visible = 0
        for i in range(total):
            conf = points[i * 3 + 2]
            if conf >= 0.15:
                visible += 1
        return visible / float(total)

    def _pose_anchor(self, points):
        if not points or len(points) < 3:
            return None
        stride = 3 if len(points) % 3 == 0 else 2
        ids = [5, 6, 11, 12]  # shoulders + hips
        xs = []
        ys = []
        for idx in ids:
            base = idx * stride
            if base + 1 >= len(points):
                continue
            conf = points[base + 2] if stride == 3 and (base + 2) < len(points) else 1.0
            if conf >= 0.20:
                xs.append(points[base])
                ys.append(points[base + 1])
        if not xs:
            return None
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def register(self, res):
        # [INIT] Áp dụng Padding và Ratio ngay từ đầu để Box đẹp ngay frame đầu tiên
        raw_h = res['h']
        raw_w = res['w']
        raw_x = res['x']
        raw_y = res['y']
        
        # [METRIC] Tính Pose Score ban đầu
        raw_points = res.get('points', [])
        # Với frame đầu tiên, filtered = raw, nên jitter = 0 -> Score cao
        pose_score = self._calculate_quality(raw_points, raw_points, res['score'], res['h'])
        
        self.objects[self.next_id] = {
            'box': [raw_x, raw_y, raw_w, raw_h],
            'score': res['score'],
            'miss': 0,
            'velocity': [0.0, 0.0, 0.0, 0.0], # px/s
            'last_time': time.time(),
            'pose_score': pose_score, # [NEW] Lưu độ tin cậy Pose
            'prev_raw_box': [raw_x, raw_y, raw_w, raw_h],
            'points': res.get('points', []), # [RAW] Lưu điểm thô
            'pose_anchor': self._pose_anchor(raw_points),
            'estimator': PoseEstimator(), # [NEW] Khởi tạo bộ phân tích cử chỉ riêng
            'gestures': [],
            'st_gcn': STGCN_Recognizer(), # [ST-GCN] Khởi tạo bộ nhận diện hành động
        }
        self.next_id += 1

    def clean_up(self):
        to_delete = []
        for oid, data in self.objects.items():
            if data['miss'] > self.max_miss_count:
                to_delete.append(oid)
        for oid in to_delete:
            del self.objects[oid]
            # [MEMORY LEAK FIX] Giải phóng 1EF của đối tượng đã mất dấu
            if oid in self.filter.object_filters:
                del self.filter.object_filters[oid]

    def get_display_objects(self):
        # Trả về định dạng để UI vẽ
        results = []
        for oid, data in self.objects.items():
            if data['miss'] == 0: # Chỉ hiện những người đang thấy
                results.append({
                    'id': oid,
                    'box': data['box'],
                    'score': data.get('score', 0.0),
                    'pose_score': data.get('pose_score', 0.0), # [NEW] Truyền ra UI
                    'points': data.get('points', []), # Truyền điểm ra UI
                    'gestures': data.get('gestures', []) # Truyền cử chỉ ra UI
                })
        return results
    
    def _calculate_quality(self, raw_points, filtered_points, det_score=0.0, bbox_height=1.0):
        """
        Tính điểm chất lượng Pose (Hybrid OKS/MPJPE Proxy):
        Formula: Accuracy = DetectScore * (0.45 * PoseConf + 0.35 * Stability + 0.20 * Visibility)
        """
        # Các khớp quan trọng: Vai, Khuỷu, Cổ tay, Hông, Gối, Cổ chân
        target_indices = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        
        sum_conf = 0.0
        sum_jitter = 0.0
        count = 0
        
        for i in target_indices:
            base = i * 3
            if base + 2 >= len(raw_points) or base + 2 >= len(filtered_points): 
                continue
                
            # Raw (x, y, conf) vs Filtered (x, y, conf)
            rx, ry, rc = raw_points[base], raw_points[base+1], raw_points[base+2]
            fx, fy = filtered_points[base], filtered_points[base+1]
            
            if rc > 0:
                sum_conf += rc
                # [MPJPE Proxy] Tính khoảng cách giữa điểm thô và điểm đã lọc (Jitter)
                dist = math.sqrt((rx - fx)**2 + (ry - fy)**2)
                
                # [NORMALIZE] Chuẩn hóa Jitter theo kích thước người (Scale Invariant)
                # Người to (gần) rung 5px là ít, người nhỏ (xa) rung 5px là nhiều.
                norm_dist = dist / (bbox_height + 1e-6)
                sum_jitter += norm_dist
                count += 1
                
        if count == 0: return 0.0
        
        avg_conf = sum_conf / count
        # [CLAMP & SCALE] Kẹp giá trị max 1.0 và tăng độ nhạy (căn bậc 2)
        avg_conf = min(avg_conf, 1.0) ** 0.5
        
        avg_jitter = sum_jitter / count
        
        # [OKS Formula] Mô phỏng hàm mũ của OKS: exp(-error^2 / 2*sigma^2)
        # [UPDATE] Sigma = 0.1 (tương đương 10% chiều cao cơ thể)
        stability_score = math.exp(-(avg_jitter**2) / (2 * (0.1**2)))
        
        # [VISIBILITY] Tỷ lệ số điểm nhìn thấy trên tổng số điểm quan trọng
        visibility = count / len(target_indices)

        # [DISTANCE FIX] Nếu vật thể nhỏ (xa, cao < 100px), ưu tiên độ ổn định hơn độ tin cậy
        if bbox_height < 100:
            # Giảm trọng số avg_conf (vì xa AI nhìn mờ), tăng stability
            final_score = det_score * (0.30 * avg_conf + 0.50 * stability_score + 0.20 * visibility)
        else:
            # Công thức chuẩn cho cự ly gần/trung bình
            final_score = det_score * (0.45 * avg_conf + 0.35 * stability_score + 0.20 * visibility)
        
        return final_score
