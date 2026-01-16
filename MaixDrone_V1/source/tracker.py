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
                # [ONE EURO] Lọc Box thông minh (Nhanh khi động, Mượt khi tĩnh)
                raw_box = [res['x'], res['y'], res['w'], res['h']]
                filtered_box = self.filter.filter_box(oid, t_now, raw_box)
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
        self.objects[self.next_id] = {
            'box': [res['x'], res['y'], res['w'], res['h']],
            'score': res['score'],
            'points': res.get('points', []),
            'miss': 0
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
        # Đơn giản là trả về vị trí cũ
        return self.get_display_objects()