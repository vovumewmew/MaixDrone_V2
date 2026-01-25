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
        self.miss_counts = {} # [NEW] Đếm số frame bị mất dấu để xử lý Ghosting
        self.kpt_conf_thresh = config.POSE_CONF_THRESHOLD
        self.deadzone = config.STICKY_DEADZONE
        
        # [SPECIALIZED CONFIG] Cấu hình riêng cho từng nhóm bộ phận
        # [SOLID MODE] Cấu hình ưu tiên độ "Đầm" (Solid) giống Official Demo
        # Beta thấp (0.1) -> Rất mượt, ít rung, tạo cảm giác khung xương chắc chắn
        # Min_cutoff (0.5) -> Lọc rung mạnh khi đứng yên
        
        self.cfg_core = {'min_cutoff': 0.5, 'beta': 0.1, 'd_cutoff': 1.0}
        self.cfg_limb = {'min_cutoff': 0.5, 'beta': 0.1, 'd_cutoff': 1.0}
        
        self.core_ids = [5, 6, 11, 12] # Vai trái/phải, Hông trái/phải
        
    def filter_kpts(self, oid, t, kpts):
        # [BYPASS] Tắt toàn bộ bộ lọc, trả về dữ liệu thô từ AI
        return kpts