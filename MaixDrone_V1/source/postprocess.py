import math

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
    def __init__(self):
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
        points = {}
        for i in range(0, len(out_kpts), 3):
            if i + 2 >= len(out_kpts): break # [FIX] Kiểm tra an toàn
            points[i//3] = {'x': out_kpts[i], 'y': out_kpts[i+1], 'c': out_kpts[i+2]}

        for child, parent in self.parents.items():
            if child not in points or parent not in points: continue
            
            pc = points[child]
            pp = points[parent]
            
            # Chỉ xử lý nếu cả 2 điểm có độ tin cậy > 0 (đã được detect)
            if pc['c'] <= 0 or pp['c'] <= 0: continue
            
            dx = pc['x'] - pp['x']
            dy = pc['y'] - pp['y']
            curr_dist = math.sqrt(dx*dx + dy*dy)
            
            if curr_dist == 0: continue
            
            bone_id = (child, parent)
            
            # [NẮN XƯƠNG] Tính độ dài chuẩn dựa trên chiều cao Box
            target_len = box_h * self.ratios.get(bone_id, 0.2)
            
            # Cho phép sai số linh hoạt (30%) để phù hợp với phối cảnh 2D
            min_len = target_len * 0.7
            max_len = target_len * 1.3
            
            scale = 1.0
            if curr_dist < min_len: scale = min_len / curr_dist
            elif curr_dist > max_len: scale = max_len / curr_dist
            
            if scale != 1.0:
                # [FIX] Nếu sai số quá lớn (> 50% max_len) -> Điểm sai hoàn toàn -> Xóa
                # Ví dụ: Cổ tay bị chấm xuống tận gót chân -> Xóa ngay
                # [CÂN BẰNG] Mức 2.0: Chấp nhận tay dài gấp đôi chuẩn (tránh mất tay khi với)
                if curr_dist > max_len * 2.0:
                    out_kpts[child*3+2] = 0.0 # Gán conf = 0 để ẩn đi
                else:
                    # Kéo điểm con về vị trí hợp lý (giữ nguyên hướng, chỉ chỉnh độ dài)
                    pc['x'] = pp['x'] + dx * scale
                    pc['y'] = pp['y'] + dy * scale
                    out_kpts[child*3] = pc['x']
                    out_kpts[child*3+1] = pc['y']
                    
        return out_kpts

class AnatomyFilter:
    def __init__(self):
        pass
        
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
        # Nếu cả bộ xương chỉ có < 4 điểm -> Khả năng cao là nhiễu (vết ố trên tường)
        valid_cnt = sum(1 for p in pts.values() if p['c'] > 0.30) # [CÂN BẰNG] Hạ xuống 0.30
        if valid_cnt < 4: 
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
                sum_x += p['x'] # Lưu ý: pts ở trên chưa lưu x, cần sửa lại logic parse
                sum_y += p['y'] # pts chỉ lưu y, c. Cần sửa đoạn parse ở trên
                count += 1
        
        # (Logic này sẽ được tích hợp lại ở đoạn parse bên dưới để tối ưu)
                
        return True

class PoseFilter:
    def __init__(self):
        # Quản lý bộ lọc cho từng đối tượng
        self.filters = {} 
        
        # [TỐC ĐỘ] Tăng Beta cực cao để Box bám dính lấy đối tượng (giảm trễ tối đa)
        # beta=0.7: Ưu tiên tốc độ phản hồi, chấp nhận rung nhẹ để bắt kịp chuyển động
        self.box_cfg = {'min_cutoff': 0.01, 'beta': 0.7, 'd_cutoff': 1.0}
        
        # [TỐC ĐỘ] Tăng Beta cho Pose để điểm chấm theo kịp tốc độ của Box
        # beta=0.1: Tăng độ nhạy để không bị tụt lại phía sau
        self.kpt_cfg = {'min_cutoff': 0.1, 'beta': 0.1, 'd_cutoff': 1.0}
        
        # Bộ lọc Kinematic (Xương khớp)
        self.kinematics = {} 
        self.anatomy = AnatomyFilter()

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
            
            # [ALGO 1] Cổng Gác (Confidence Thresholding)
            # [CÂN BẰNG] Mức 0.30: Chấp nhận điểm yếu nhưng có thực
            # Các điểm nhiễu thường < 0.25
            if conf < 0.30:
                filtered.extend([x, y, 0.0])
                continue

            # [ALGO 2] Ràng buộc Hình học Hộp (Bounding Box Constraint)
            # [PHÂN CẤP] Áp dụng margin khác nhau cho từng bộ phận
            if idx in [0, 1, 2, 3, 4, 5, 6, 11, 12]: # Đầu, Vai, Hông (Core) -> Siết chặt
                margin_x = bw * 0.05 
                margin_y = bh * 0.05
            elif idx in [7, 8, 13, 14]: # Khuỷu, Gối -> Vừa phải
                margin_x = bw * 0.1
                margin_y = bh * 0.1
            else: # Cổ tay, Cổ chân -> Nới lỏng
                margin_x = bw * 0.2
                margin_y = bh * 0.2
                
            if x < bx - margin_x or x > bx + bw + margin_x or \
               y < by - margin_y or y > by + bh + margin_y:
                filtered.extend([x, y, 0.0]) # Gán conf=0 để không vẽ
                continue

            # [ALGO 5] Zone Constraint (Phân vùng cơ thể - Chống đầu cắm đất)
            # Nếu người đang đứng (cao > rộng), các điểm thân trên không thể nằm dưới chân
            if bh > bw:
                # Các điểm thân trên: 0-6 (Mũi, Mắt, Tai, Vai)
                if idx <= 6:
                    # Nếu nằm ở 40% dưới cùng của box -> Vô lý -> Xóa
                    if y > by + bh * 0.6:
                        filtered.extend([x, y, 0.0])
                        continue
                
                # [ALGO 6] Wrist vs Ankle Check (Tay không thể thấp hơn chân)
                # Nếu là Cổ tay (9, 10)
                if idx in [9, 10]:
                    # Nếu nằm ở 15% dưới cùng của Box (khu vực bàn chân) -> Xóa
                    if y > by + bh * 0.85:
                        filtered.extend([x, y, 0.0])
                        continue
                    
                    # Nếu thấp hơn (Y lớn hơn) Cổ chân tương ứng (nếu Cổ chân tin cậy)
                    # Logic này phức tạp vì cần truy xuất điểm khác, tạm thời dùng Zone 85% ở trên là đủ hiệu quả
                    pass

            # [ALGO 4] Edge Penalty (Phạt điểm ở mép - Chống kẹt dưới đất)
            # Nếu điểm nằm sát mép Box (vùng 5% ngoài cùng), đòi hỏi độ tin cậy cực cao
            # Đây là nơi thường xuất hiện các điểm "ma" do AI đoán mò ở viền ảnh
            edge_dist_x = min(abs(x - bx), abs(bx + bw - x))
            edge_dist_y = min(abs(y - by), abs(by + bh - y))
            is_near_edge = (edge_dist_x < bw * 0.05) or (edge_dist_y < bh * 0.05)
            
            # Đặc biệt siết chặt mép dưới (chân tường) - Nơi dễ bị chấm sai nhất
            if y > by + bh * 0.95:
                if conf < 0.85: # Đòi hỏi tin cậy cực cao mới được vẽ ở sát đất
                    filtered.extend([x, y, 0.0])
                    continue
            
            # Nếu sát mép mà tin cậy < 0.75 -> Xóa thẳng tay
            if is_near_edge and conf < 0.75:
                filtered.extend([x, y, 0.0])
                continue

            if idx not in self.filters[oid]['kpts']:
                self.filters[oid]['kpts'][idx] = [
                    OneEuroFilter(t, x, **self.kpt_cfg),
                    OneEuroFilter(t, y, **self.kpt_cfg)
                ]
            
            # Chỉ lọc nếu điểm tin cậy
            if conf > 0.0:
                fx = self.filters[oid]['kpts'][idx][0](t, x)
                fy = self.filters[oid]['kpts'][idx][1](t, y)
                filtered.extend([fx, fy, conf])
            else:
                filtered.extend([x, y, conf])
                
        # --- GIAI ĐOẠN 2: KINEMATIC FILTER (Ràng buộc xương) ---
        # Nắn chỉnh lại xương dựa trên độ dài vật lý
        if oid not in self.kinematics:
            self.kinematics[oid] = KinematicFilter()
            
        kpts_kinematic = self.kinematics[oid].update(filtered, bh)
        
        # --- GIAI ĐOẠN 3: ANATOMY CHECK (Global Check) ---
        # Cập nhật hàm check để truyền thêm box và kiểm tra kỹ hơn
        if not self.check_anatomy_v2(kpts_kinematic, box):
            return [] # Nếu cấu trúc vô lý, trả về rỗng để không vẽ bậy
        
        return kpts_kinematic

    def check_anatomy_v2(self, kpts, box):
        bx, by, bw, bh = box
        # Tính trọng tâm các điểm tin cậy
        sum_x, sum_y, count = 0, 0, 0
        for i in range(0, len(kpts), 3):
            if i + 2 >= len(kpts): break # [FIX] Safety check
            # [ĐỒNG BỘ] Hạ xuống 0.30 để khớp với bộ lọc đầu vào (tránh việc lọc xong lại bị chặn ở đây)
            if kpts[i+2] > 0.30:
                sum_x += kpts[i]
                sum_y += kpts[i+1]
                count += 1
        
        if count < 4: return False # Quá ít điểm
        
        # [MỚI] Kiểm tra logic đứng (Vertical Consistency)
        # Nếu Box cao hơn rộng (người đứng) -> Vai phải cao hơn Hông (Y nhỏ hơn)
        if bh > bw * 1.1:
            # Lấy Y trung bình của Vai (5,6) và Hông (11,12)
            y_shoulders = []
            # [FIX] Kiểm tra độ dài mảng trước khi truy cập index lớn
            if len(kpts) > 6*3+2:
                if kpts[5*3+2] > 0.30: y_shoulders.append(kpts[5*3+1])
                if kpts[6*3+2] > 0.30: y_shoulders.append(kpts[6*3+1])
            
            y_hips = []
            if len(kpts) > 12*3+2:
                if kpts[11*3+2] > 0.30: y_hips.append(kpts[11*3+1])
                if kpts[12*3+2] > 0.30: y_hips.append(kpts[12*3+1])
            
            if y_shoulders and y_hips:
                avg_s = sum(y_shoulders)/len(y_shoulders)
                avg_h = sum(y_hips)/len(y_hips)
                # Nếu Vai thấp hơn Hông (Y lớn hơn) quá nhiều -> Sai tư thế hoặc detect ngược
                if avg_s > avg_h + 10: return False

        # Trọng tâm xương
        center_x = sum_x / count
        center_y = sum_y / count
        
        # Tâm Box
        box_cx = bx + bw / 2
        box_cy = by + bh / 2
        
        # Nếu trọng tâm xương lệch quá 40% so với tâm Box -> Vô lý (Ghost)
        dist = math.sqrt((center_x - box_cx)**2 + (center_y - box_cy)**2)
        max_dist = math.sqrt(bw**2 + bh**2) * 0.4
        
        if dist > max_dist: return False
        
        return True