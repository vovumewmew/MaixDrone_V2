import math
import time
from source.postprocess import PoseFilter

class ObjectTracker:
    def __init__(self):
        # Lưu danh sách các đối tượng đang theo dõi
        # Format: { object_id: {'box': [x,y,w,h], 'miss': 0} }
        self.objects = {}
        self.next_id = 1
        self.max_miss_count = 10  # Mất dấu 10 frame mới xóa
        self.dist_threshold = 100 # Khoảng cách tối đa để coi là cùng 1 người (pixel)
        self.filter = PoseFilter() # Sử dụng One Euro Filter

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
            cx = box[0] + box[2] / 2
            cy = box[1] + box[3] / 2
            object_centroids.append((cx, cy))

        # Đánh dấu đã dùng
        used_input = [False] * len(input_centroids)
        used_object = [False] * len(object_ids)

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
                
                # Update thông tin
                # --- [CHIẾN LƯỢC MỚI] Ổn định Box (EMA + Fixed Ratio + Padding) ---
                
                # 1. Lấy dữ liệu thô từ AI
                raw_x, raw_y, raw_w, raw_h = res['x'], res['y'], res['w'], res['h']
                raw_cx = raw_x + raw_w / 2
                raw_cy = raw_y + raw_h / 2
                
                # 2. Chiến thuật "Vùng đệm an toàn" (Padding 5%)
                target_h = raw_h * 1.05
                target_w = raw_w * 1.05 # [ACCURACY] Dùng chiều rộng thật từ AI thay vì ép tỷ lệ
                
                # 3. Lấy trạng thái cũ
                old_box = self.objects[oid]['box']
                old_w, old_h = old_box[2], old_box[3]
                old_cx = old_box[0] + old_w / 2
                old_cy = old_box[1] + old_h / 2
                
                # 4. Chiến thuật "Chống sốc" (Clamp Rate of Change)
                # Giới hạn thay đổi tối đa mỗi frame (ví dụ 10px) để tránh giật cục
                def clamp(curr, target, max_step):
                    delta = target - curr
                    if delta > max_step: return curr + max_step
                    if delta < -max_step: return curr - max_step
                    return target

                target_h = clamp(old_h, target_h, 10)
                target_w = clamp(old_w, target_w, 10) # [ACCURACY] Chống sốc cho chiều rộng
                target_cx = clamp(old_cx, raw_cx, 20) # Cho phép di chuyển nhanh hơn chút (20px)
                target_cy = clamp(old_cy, raw_cy, 20)

                # 5. Chiến thuật "Bộ giảm xóc" (EMA Smoothing)
                # Công thức: Old * 0.7 + New * 0.3 (Tạo quán tính lớn)
                alpha = 0.3
                smooth_h = old_h * (1 - alpha) + target_h * alpha
                smooth_w = old_w * (1 - alpha) + target_w * alpha # [ACCURACY] Smooth chiều rộng độc lập
                smooth_cx = old_cx * (1 - alpha) + target_cx * alpha
                smooth_cy = old_cy * (1 - alpha) + target_cy * alpha
                
                # Tái tạo Box hiển thị
                filtered_box = [
                    smooth_cx - smooth_w / 2,
                    smooth_cy - smooth_h / 2,
                    smooth_w,
                    smooth_h
                ]
                
                # [MỚI] Tính vận tốc (Momentum) để dự đoán cho các frame bị skip
                # Lấy vị trí mới - vị trí cũ
                old_box = self.objects[oid]['box']
                
                # [FIX] Giảm hệ số quán tính (0.4 -> 0.2) để bớt nhạy
                # [FIX] Kẹp biên (Clamp): Không cho vận tốc vượt quá 10 pixel/frame
                # Điều này ngăn chặn việc Box bay vèo ra ngoài nếu AI bị giật
                raw_vel = [(n - o) * 0.2 for n, o in zip(filtered_box, old_box)]
                self.objects[oid]['vel'] = [max(-10, min(10, v)) for v in raw_vel]
                
                self.objects[oid]['box'] = filtered_box
                
                self.objects[oid]['score'] = res['score']
                
                # [KÍCH HOẠT LẠI] Lọc Pose để đảm bảo điểm chấm chính xác, mượt mà
                raw_points = res.get('points', [])
                self.objects[oid]['points'] = self.filter.filter_kpts(oid, t_now, raw_points, filtered_box)
                # self.objects[oid]['points'] = raw_points 
                
                self.objects[oid]['miss'] = 0 # Reset biến đếm mất dấu
                
                used_input[best_match_idx] = True
                used_object[i] = True
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
        raw_h = res['h'] * 1.05     # Padding 5%
        raw_w = res['w'] * 1.05     # [ACCURACY] Dùng width thật
        cx = res['x'] + res['w'] / 2
        cy = res['y'] + res['h'] / 2
        
        self.objects[self.next_id] = {
            'box': [cx - raw_w/2, cy - raw_h/2, raw_w, raw_h],
            'score': res['score'],
            'points': res.get('points', []),
            'miss': 0,
            'vel': [0, 0, 0, 0] # [MỚI] Khởi tạo vận tốc = 0
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
                    'points': data.get('points', [])
                })
        return results
    
    def predict(self):
        # [MỚI] Dự đoán vị trí dựa trên quán tính (Momentum)
        # Giúp Box di chuyển mượt mà trong các frame bị skip thay vì đứng im
        for oid in self.objects:
            if self.objects[oid]['miss'] == 0:
                # Di chuyển box theo vận tốc hiện tại
                for i in range(4):
                    self.objects[oid]['box'][i] += self.objects[oid]['vel'][i]
                
                # [FIX] Tăng ma sát (0.6 -> 0.4): Phanh gấp hơn!
                # Hộp sẽ chỉ nhích nhẹ một chút rồi dừng hẳn, thay vì trôi đi xa.
                self.objects[oid]['vel'] = [v * 0.4 for v in self.objects[oid]['vel']]
                
        return self.get_display_objects()