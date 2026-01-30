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
        # Quản lý bộ lọc cho từng đối tượng: { oid: { index: OneEuroFilter } }
        self.object_filters = {}
        # [UPDATE] Tăng Beta lên 0.3 để giảm độ trễ (Lag) khi di chuyển tay nhanh
        self.min_cutoff = 0.5
        self.beta = 0.3 
        self.d_cutoff = 1.0

    def filter_kpts(self, oid, t, kpts, bbox_h=1.0):
        if not kpts: return []
        
        # [DYNAMIC STRIDE] Tự động xác định stride (2 hoặc 3) dựa trên độ dài dữ liệu
        # Nếu chia hết cho 3 -> [x, y, conf]. Nếu không -> [x, y]
        stride = 3 if len(kpts) % 3 == 0 else 2
        
        if oid not in self.object_filters:
            self.object_filters[oid] = {}
            
        filters = self.object_filters[oid]
        filtered_kpts = []
        
        num_points = len(kpts) // stride
        
        for i in range(num_points):
            base = i * stride
            
            # Lọc tọa độ X
            if base not in filters:
                filters[base] = OneEuroFilter(t, kpts[base], min_cutoff=self.min_cutoff, beta=self.beta, d_cutoff=self.d_cutoff)
            fx = filters[base](t, kpts[base])
            
            # Lọc tọa độ Y
            if (base+1) not in filters:
                filters[base+1] = OneEuroFilter(t, kpts[base+1], min_cutoff=self.min_cutoff, beta=self.beta, d_cutoff=self.d_cutoff)
            fy = filters[base+1](t, kpts[base+1])
            
            filtered_kpts.extend([fx, fy])
            
            # Giữ nguyên Confidence Score (nếu có)
            if stride == 3:
                filtered_kpts.append(kpts[base+2])
                
        return filtered_kpts