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
        if not kpts:
            return []

        # Accuracy-first mode:
        # Keep keypoints close to raw detections to preserve motion dynamics.
        stride = 3 if len(kpts) % 3 == 0 else 2
        filtered_kpts = []
        num_points = len(kpts) // stride

        # Bo sung occlusion handling cho 2 tay de tranh co rut dot ngot.
        if oid not in self.object_filters:
            self.object_filters[oid] = {"prev_points": {}, "missing": {}}
        state = self.object_filters[oid]
        prev_points = state["prev_points"]
        missing = state["missing"]

        left_arm_hold_frames = getattr(config, "LEFT_ARM_HOLD_FRAMES", 2)
        left_arm_conf_floor = getattr(config, "LEFT_ARM_CONF_FLOOR", 0.18)
        right_arm_hold_frames = getattr(config, "RIGHT_ARM_HOLD_FRAMES", 2)
        right_arm_conf_floor = getattr(config, "RIGHT_ARM_CONF_FLOOR", 0.18)

        bx = by = bw = bh = None
        if bbox and len(bbox) >= 4:
            bx, by, bw, bh = bbox[0], bbox[1], bbox[2], bbox[3]

        for i in range(num_points):
            base = i * stride
            x = float(kpts[base])
            y = float(kpts[base + 1])
            conf = float(kpts[base + 2]) if stride == 3 else 1.0

            # Khop tay trai/phai:
            # - Left: 7 (L-Elb), 9 (L-Wri)
            # - Right: 8 (R-Elb), 10 (R-Wri)
            # Neu AI mat diem ngan han -> giu diem cu trong vai frame.
            if stride == 3 and i in (7, 8, 9, 10):
                if i in (7, 9):
                    conf_floor = left_arm_conf_floor
                    hold_frames = left_arm_hold_frames
                else:
                    conf_floor = right_arm_conf_floor
                    hold_frames = right_arm_hold_frames

                if conf <= conf_floor:
                    prev = prev_points.get(i)
                    miss_count = missing.get(i, 0)
                    if prev and miss_count < hold_frames:
                        x, y, prev_conf = prev
                        conf = max(conf_floor, prev_conf * 0.75)
                        missing[i] = miss_count + 1
                    else:
                        missing[i] = miss_count + 1
                else:
                    missing[i] = 0

            if stride == 3 and conf < config.POSE_CONF_THRESHOLD:
                conf = 0.0

            if bx is not None:
                x = max(bx, min(bx + bw - 1, x))
                y = max(by, min(by + bh - 1, y))

            if stride == 3 and conf > 0.0:
                prev_points[i] = (x, y, conf)

            filtered_kpts.extend([x, y])
            if stride == 3:
                filtered_kpts.append(conf)

        return filtered_kpts
