import math
import time
import config
from source.postprocess import PoseFilter # [FIX] Import bộ lọc
from source.gesture import PoseEstimator # [NEW] Import bộ phân tích cử chỉ

class ObjectTracker:
    def __init__(self):
        # Lưu danh sách các đối tượng đang theo dõi
        # Format: { object_id: {'box': [x,y,w,h], 'miss': 0} }
        self.objects = {}
        self.next_id = 1
        self.max_miss_count = 30  # [UPDATE] Tăng lên 30 frame (1s) để chịu được vật cản che khuất
        self.dist_threshold = 100 # Khoảng cách tối đa để coi là cùng 1 người (pixel)
        self.filter = PoseFilter() # [FIX] Khởi tạo bộ lọc

    def update(self, ai_results):
        """
        Thuật toán Centroid Tracking cơ bản:
        So sánh tâm của Box mới với Box cũ để gán ID.
        """
        t_now = time.time()
        
        # 1. Tính tâm của các Box mới từ AI
        input_centroids = []
        for res in ai_results:
            cx = res['x'] + res['w'] / 2
            cy = res['y'] + res['h'] / 2
            input_centroids.append((cx, cy, res))

        # 2. Nếu chưa có đối tượng nào -> Đăng ký mới hết
        if not self.objects:
            for _, _, res in input_centroids:
                self.register(res)
            return self.get_display_objects()

        # 3. So sánh khoảng cách để update ID
        # Tạo danh sách ID hiện có và tâm của chúng
        object_ids = list(self.objects.keys())
        object_centroids = []
        for oid in object_ids:
            box = self.objects[oid]['box']
            vel = self.objects[oid].get('velocity', [0,0,0,0])
            
            # [FIX 1] Predictive Matching (Bắt cặp dựa trên Dự đoán)
            # Dự đoán vị trí hiện tại dựa trên vận tốc, giúp tránh nhầm lẫn khi 2 người đi qua nhau
            dt_match = t_now - self.objects[oid].get('last_time', t_now)
            if dt_match > 1.0: dt_match = 0 # Safety check
            
            pred_cx = box[0] + box[2]/2 + vel[0] * dt_match
            pred_cy = box[1] + box[3]/2 + vel[1] * dt_match
            object_centroids.append((pred_cx, pred_cy))

        # Đánh dấu đã dùng
        used_input = [False] * len(input_centroids)

        # Duyệt qua từng object cũ, tìm input mới gần nhất
        for i, (old_cx, old_cy) in enumerate(object_centroids):
            min_dist = 999999
            best_match_idx = -1

            for j, (new_cx, new_cy, _) in enumerate(input_centroids):
                if used_input[j]: continue
                
                dist = math.sqrt((old_cx - new_cx)**2 + (old_cy - new_cy)**2)
                # [DYNAMIC] Ngưỡng theo kích thước box (tránh nhầm ID khi xa/gần)
                dynamic_th = self.dist_threshold
                if i < len(object_ids):
                    obox = self.objects[object_ids[i]]['box']
                    dynamic_th = max(60, min(200, 0.6 * max(obox[2], obox[3])))
                if dist < min_dist and dist < dynamic_th:
                    min_dist = dist
                    best_match_idx = j
            
            # Nếu tìm thấy cặp đôi hoàn hảo
            if best_match_idx != -1:
                oid = object_ids[i]
                res = input_centroids[best_match_idx][2]
                
                raw_box = [res['x'], res['y'], res['w'], res['h']]
                old_data = self.objects[oid]
                old_box = old_data['box']

                # [EMA SMOOTHING] Adaptive Alpha (Làm mượt thích ứng)
                # Tính khoảng cách di chuyển của tâm Box so với frame trước
                center_dist = math.sqrt(((raw_box[0]+raw_box[2]/2) - (old_box[0]+old_box[2]/2))**2 + 
                                      ((raw_box[1]+raw_box[3]/2) - (old_box[1]+old_box[3]/2))**2)
                
                # Logic: 
                # - Đứng yên (dist < 3px): Alpha cực nhỏ (0.05) -> Khóa cứng, chống rung tuyệt đối
                # - Di chuyển (> 3px): Alpha tăng dần lên 0.4 -> Bám sát chuyển động
                # - Di chuyển nhanh (> 20px): Alpha = 0.5 -> Phản hồi tức thì
                alpha = 0.05 if center_dist < 3.0 else min(0.5, 0.05 + (center_dist / 20.0) * 0.45)
                
                smooth_box = [r * alpha + o * (1 - alpha) for r, o in zip(raw_box, old_box)]
                
                # [UPDATE] Tính vận tốc để dự đoán hướng đi khi bị che khuất
                dt = t_now - old_data['last_time']
                if dt > 0:
                    vx = (smooth_box[0] - old_box[0]) / dt
                    vy = (smooth_box[1] - old_box[1]) / dt
                    old_vel = old_data.get('velocity', [0,0,0,0])
                    # Lọc mạnh (alpha nhỏ) để tránh nhiễu do rung lắc ở xa
                    v_alpha = 0.2
                    svx = vx * v_alpha + old_vel[0] * (1 - v_alpha)
                    svy = vy * v_alpha + old_vel[1] * (1 - v_alpha)
                    self.objects[oid]['velocity'] = [svx, svy, 0, 0]
                
                self.objects[oid]['box'] = smooth_box
                self.objects[oid]['prev_raw_box'] = raw_box
                self.objects[oid]['last_time'] = t_now
                
                # [FILTERING] Chỉ lọc điểm (Points) để chống rung
                raw_points = res.get('points', [])
                
                old_points = self.objects[oid].get('points', [])
                
                # [ROBUST] Nếu điểm trống/yếu -> giữ điểm cũ vài frame
                if not raw_points:
                    filtered_points = self.objects[oid].get('points', [])
                else:
                    filtered_points = self.filter.filter_kpts(oid, t_now, raw_points, bbox=smooth_box)

                self.objects[oid]['points'] = filtered_points
                
                # [METRIC ADVANCED] Tính điểm chất lượng dựa trên OKS & MPJPE (Proxy)
                # So sánh độ lệch giữa Raw và Filtered để đánh giá độ ổn định
                # [UPDATE] Truyền thêm chiều cao (h) để chuẩn hóa Jitter theo kích thước người
                pose_score = self._calculate_quality(raw_points, filtered_points, res['score'], smooth_box[3])
                self.objects[oid]['pose_score'] = pose_score
                
                # [GESTURE] Phân tích cử chỉ bằng RAW POINTS (để lấy độ tin cậy gốc)
                # Filtered points chỉ dùng để vẽ cho mượt, còn logic cần biết AI chắc chắn đến đâu
                gestures = self.objects[oid]['estimator'].update(raw_points)
                self.objects[oid]['gestures'] = gestures
                
                self.objects[oid]['score'] = res['score']
                self.objects[oid]['miss'] = 0 # Reset biến đếm mất dấu
                
                used_input[best_match_idx] = True
            else:
                # Không tìm thấy input mới cho object này -> Tăng biến mất dấu
                self.objects[object_ids[i]]['miss'] += 1

        # 4. Đăng ký các input mới chưa có chủ
        for i, used in enumerate(used_input):
            if not used:
                self.register(input_centroids[i][2])

        # 5. Xóa các object mất dấu quá lâu
        self.clean_up()

        return self.get_display_objects()

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
            'estimator': PoseEstimator(), # [NEW] Khởi tạo bộ phân tích cử chỉ riêng
            'gestures': []
        }
        self.next_id += 1

    def clean_up(self):
        # Xóa ID nếu miss > max_miss_count
        to_delete = []
        for oid, data in self.objects.items():
            if data['miss'] > self.max_miss_count:
                to_delete.append(oid)
        for oid in to_delete:
            del self.objects[oid]

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
    
    def predict(self):
        # [PREDICTION] Dự đoán vị trí trong các frame bị skip
        # Giúp tăng FPS (bằng cách tăng SKIP_FRAMES) mà hình ảnh vẫn mượt
        
        # [TEST] Tắt tính toán dự đoán (Zero Order Hold) để kiểm tra độ ổn định
        # Box sẽ đứng yên trong các frame bị skip
        return self.get_display_objects()

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
