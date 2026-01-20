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
        self.max_miss_count = 10  # Mất dấu 10 frame mới xóa
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
                if dist < min_dist and dist < self.dist_threshold:
                    min_dist = dist
                    best_match_idx = j
            
            # Nếu tìm thấy cặp đôi hoàn hảo
            if best_match_idx != -1:
                oid = object_ids[i]
                res = input_centroids[best_match_idx][2]
                
                raw_box = [res['x'], res['y'], res['w'], res['h']]
                old_data = self.objects[oid]
                old_box = old_data['box']

                # [EMA SMOOTHING] Bật lại làm mượt để chống rung (Jitter)
                # [TUNING] Tăng Alpha lên 0.6 để Box bám nhanh hơn (giảm độ trễ)
                alpha = 0.6
                smooth_box = [r * alpha + o * (1 - alpha) for r, o in zip(raw_box, old_box)]
                
                self.objects[oid]['box'] = smooth_box
                self.objects[oid]['velocity'] = [0,0,0,0] # Reset velocity, không dùng nữa
                self.objects[oid]['prev_raw_box'] = raw_box
                self.objects[oid]['last_time'] = t_now
                
                # [FILTERING] Chỉ lọc điểm (Points) để chống rung
                raw_points = res.get('points', [])
                old_points = self.objects[oid].get('points', [])
                
                filtered_points = self.filter.filter_kpts(oid, t_now, raw_points)

                self.objects[oid]['points'] = filtered_points
                
                # [GESTURE] Phân tích cử chỉ
                gestures = self.objects[oid]['estimator'].update(filtered_points)
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
        
        self.objects[self.next_id] = {
            'box': [raw_x, raw_y, raw_w, raw_h],
            'score': res['score'],
            'miss': 0,
            'velocity': [0.0, 0.0, 0.0, 0.0], # px/s
            'last_time': time.time(),
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