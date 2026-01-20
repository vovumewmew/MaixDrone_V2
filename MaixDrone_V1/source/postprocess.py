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
        # Quản lý bộ lọc cho từng đối tượng
        self.filters = {}
        self.kpt_conf_thresh = config.POSE_CONF_THRESHOLD
        # [TUNING] Tinh chỉnh bộ lọc cho Keypoints
        # [SMOOTH & FAST] Beta=0.15: Cân bằng hoàn hảo giữa độ mượt (chống rung) và tốc độ bám
        self.kpt_cfg = {'min_cutoff': 0.5, 'beta': 0.15, 'd_cutoff': 1.0}
        
    def filter_kpts(self, oid, t, kpts):
        if oid not in self.filters:
            self.filters[oid] = {}
        
        filtered = []
        for i in range(0, len(kpts), 3):
            idx = i // 3
            x, y, conf = kpts[i], kpts[i+1], kpts[i+2]

            # [POLISH] Chỉ lọc bỏ nếu độ tin cậy quá thấp (Noise)
            if conf < self.kpt_conf_thresh:
                filtered.extend([x, y, 0.0])
                continue

            # Khởi tạo bộ lọc OneEuro cho điểm mới
            if idx not in self.filters[oid]:
                self.filters[oid][idx] = [
                    OneEuroFilter(t, x, **self.kpt_cfg),
                    OneEuroFilter(t, y, **self.kpt_cfg)
                ]
            
            # Áp dụng làm mượt (Smoothing)
            fx = self.filters[oid][idx][0](t, x)
            fy = self.filters[oid][idx][1](t, y)
            filtered.extend([fx, fy, conf])
                
        return filtered