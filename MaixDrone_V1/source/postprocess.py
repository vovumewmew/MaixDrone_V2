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

class PoseFilter:
    def __init__(self):
        self.object_filters = {}
        # [UPDATE] Cấu hình "Siêu Mượt" (Heavy Smoothing) để chống nhảy điểm
        # [NOISE REDUCTION] Giảm mạnh các thông số để ưu tiên độ ổn định (chấp nhận trễ nhẹ)
        self.min_cutoff = 0.004 # [TUNING] Rất nhỏ (0.004) để khử rung triệt để khi đứng yên
        self.beta = 0.05        # [TUNING] Nhỏ (0.05) để chuyển động đầm, không bị giật
        self.d_cutoff = 1.0

    def filter_kpts(self, oid, t, kpts, bbox=None):
        if not kpts: return []
        
        # [DYNAMIC STRIDE] Tự động xác định stride (2 hoặc 3) dựa trên độ dài dữ liệu
        # Nếu chia hết cho 3 -> [x, y, conf]. Nếu không -> [x, y]
        stride = 3 if len(kpts) % 3 == 0 else 2

        # Adaptive theo khoảng cách (bbox_h)
        bbox_h = 1.0
        if bbox and len(bbox) >= 4:
            bbox_h = max(1.0, float(bbox[3]))

        if bbox_h < 100:
            min_cutoff = 0.002 # [XA] Khóa cứng điểm khi ở xa
            beta = 0.02        # [XA] Rất đầm
        elif bbox_h < 200:
            min_cutoff = 0.005
            beta = 0.05
        else:
            min_cutoff = 0.01
            # [FIX LAG] Tăng beta từ 0.1 lên 0.4 để tay bám sát chuyển động nhanh (giảm hiện tượng níu)
            beta = 0.4 
        
        if oid not in self.object_filters:
            self.object_filters[oid] = {}
            
        filters = self.object_filters[oid]
        filtered_kpts = []
        
        num_points = len(kpts) // stride
        
        for i in range(num_points):
            base = i * stride
            
            # Confidence-weighted smoothing
            conf = kpts[base+2] if stride == 3 else 1.0
            if conf < config.KEYPOINT_THRESHOLD:
                conf = 0.0

            c_weight = max(0.0, min(1.0, conf))
            c_min_cutoff = min_cutoff * (0.6 + 0.4 * c_weight)
            c_beta = beta * (0.6 + 0.4 * c_weight)

            # [FIX] Joint Locking: Nếu độ tin cậy thấp, giữ nguyên vị trí cũ
            # Ngăn chặn hiện tượng "co rút" hoặc điểm xương bay loạn xạ khi AI mất dấu
            target_x = kpts[base]
            target_y = kpts[base+1]
            
            if conf == 0.0 and base in filters:
                target_x = filters[base].x_prev
                target_y = filters[base+1].x_prev

            # Lọc tọa độ X
            if base not in filters:
                filters[base] = OneEuroFilter(t, target_x, min_cutoff=c_min_cutoff, beta=c_beta, d_cutoff=self.d_cutoff)
            else:
                filters[base].min_cutoff = c_min_cutoff
                filters[base].beta = c_beta
            fx = filters[base](t, target_x)
            
            # Lọc tọa độ Y
            if (base+1) not in filters:
                filters[base+1] = OneEuroFilter(t, target_y, min_cutoff=c_min_cutoff, beta=c_beta, d_cutoff=self.d_cutoff)
            else:
                filters[base+1].min_cutoff = c_min_cutoff
                filters[base+1].beta = c_beta
            fy = filters[base+1](t, target_y)

            # Clamp vào bbox nếu có
            if bbox and len(bbox) >= 4:
                bx, by, bw, bh = bbox[0], bbox[1], bbox[2], bbox[3]
                fx = max(bx, min(bx + bw - 1, fx))
                fy = max(by, min(by + bh - 1, fy))
                # Bỏ điểm nhiễu ở góc trên-trái bbox
                tl_px = getattr(config, "BBOX_TL_IGNORE_PX", 6)
                if abs(fx - bx) <= tl_px and abs(fy - by) <= tl_px:
                    conf = 0.0
            
            filtered_kpts.extend([fx, fy])
            
            # Giữ nguyên Confidence Score (nếu có)
            if stride == 3:
                filtered_kpts.append(conf)
                
        return filtered_kpts
