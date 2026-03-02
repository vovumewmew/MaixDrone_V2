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

        # Tính cutoff
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        
        # Khóa trần Cutoff (Không cho mở bộ lọc quá to)
        cutoff = min(cutoff, 4.0)

        a = self.smoothing_factor(t_e, cutoff)
        
        # [STABILITY TUNING] Giảm trần Alpha để ưu tiên độ mượt
        # Giảm từ 0.85 xuống 0.50 để cắt bỏ rung động tần số cao
        a = max(0.001, min(0.50, a))
        
        x_hat = self.exponential_smoothing(a, x, self.x_prev)

        self.x_prev = x_hat
        self.dx_prev = dx_hat
        self.t_prev = t
        return x_hat


class PoseFilter:
    def __init__(self):
        self.object_filters = {}
        self.d_cutoff = 1.0

    def filter_kpts(self, oid, t, kpts, bbox=None):
        if not kpts: return []
        
        stride = 3 if len(kpts) % 3 == 0 else 2

        bbox_h = 1.0
        if bbox and len(bbox) >= 4:
            bbox_h = max(1.0, float(bbox[3]))

        self.d_cutoff = 0.8

        # [STABILITY TUNING] Giảm Beta và Min_Cutoff để bộ lọc đầm hơn
        if bbox_h < 150:
            min_cutoff = 0.002
            beta = 0.8
        else:
            min_cutoff = 0.005
            beta = 2.0
        
        if oid not in self.object_filters:
            self.object_filters[oid] = {}
            
        filters = self.object_filters[oid]
        filtered_kpts = []
        num_points = len(kpts) // stride
        
        for i in range(num_points):
            base = i * stride
            target_x = kpts[base]
            target_y = kpts[base+1]
            conf = kpts[base+2] if stride == 3 else 1.0

            # --- [SMART ASYMMETRIC CONFIDENCE (Fast Attack, Slow Decay)] ---
            smooth_conf = conf
            is_reconstructed = False
            
            if stride == 3:
                conf_key = f"{base}_conf"
                prev_conf = filters.get(conf_key, conf)
                
                if conf == 0.0:
                    # [PHANH KHẨN CẤP] Từ ai.py: Bắt buộc tuân thủ
                    smooth_conf = 0.0
                elif conf == 0.85 or (conf > 0.75 and prev_conf < 0.2):
                    # [KINEMATIC BYPASS] Tái tạo động học: Tin tưởng tuyệt đối
                    smooth_conf = conf
                    is_reconstructed = True
                elif conf >= prev_conf:
                    # [FAST ATTACK] Tín hiệu tốt lên -> Bắt nhịp nhanh (Quán tính thấp: 30% cũ, 70% mới)
                    # Giúp khung xương lập tức bám sát khi thoát khỏi vùng nhiễu
                    smooth_conf = prev_conf * 0.30 + conf * 0.70
                else:
                    # [SLOW DECAY] Tín hiệu rớt đột ngột -> Rất lỳ lợm (Quán tính cao: 95% cũ, 5% mới)
                    # Xóa sổ hiện tượng nhấp nháy/giật cục khi AI mất nét tạm thời
                    smooth_conf = prev_conf * 0.95 + conf * 0.05
                    
                filters[conf_key] = smooth_conf

            if base not in filters:
                filters[base] = OneEuroFilter(t, target_x, min_cutoff=min_cutoff, beta=beta, d_cutoff=self.d_cutoff)
            if (base+1) not in filters:
                filters[base+1] = OneEuroFilter(t, target_y, min_cutoff=min_cutoff, beta=beta, d_cutoff=self.d_cutoff)

            # --- [DYNAMIC BIOLOGICAL CLAMPING] ---
            if base in filters and (base+1) in filters:
                # Nếu ai.py ép conf=0 (tay T-Rex), khóa bán kính tối đa xuống cực nhỏ (1%)
                # Nếu bình thường, cho phép di chuyển 15%
                max_step = bbox_h * (0.01 if smooth_conf == 0.0 else 0.15)
                
                dx = target_x - filters[base].x_prev
                dy = target_y - filters[base+1].x_prev
                dist = math.sqrt(dx**2 + dy**2)
                
                if dist > max_step:
                    ratio = max_step / dist
                    target_x = filters[base].x_prev + dx * ratio
                    target_y = filters[base+1].x_prev + dy * ratio

            filters[base].d_cutoff = self.d_cutoff
            filters[base+1].d_cutoff = self.d_cutoff

            # Tính toán OneEuro theo smooth_conf
            c_weight = max(0.0, min(1.0, smooth_conf))
            c_min_cutoff = min_cutoff * (0.05 + 0.95 * c_weight)
            c_beta = beta * (0.05 + 0.95 * c_weight)

            filters[base].min_cutoff = c_min_cutoff
            filters[base].beta = c_beta
            filters[base+1].min_cutoff = c_min_cutoff
            filters[base+1].beta = c_beta

            fx = filters[base](t, target_x)
            fy = filters[base+1](t, target_y)

            if bbox and len(bbox) >= 4:
                bx, by, bw, bh = bbox[0], bbox[1], bbox[2], bbox[3]
                fx = max(bx, min(bx + bw - 1, fx))
                fy = max(by, min(by + bh - 1, fy))
            
            filtered_kpts.extend([fx, fy])
            
            if stride == 3:
                filtered_kpts.append(smooth_conf)
                
        return filtered_kpts