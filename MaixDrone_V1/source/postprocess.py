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

    def _dist(self, p1, p2):
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        return math.sqrt(dx * dx + dy * dy)

    def _head_y(self, points):
        head_ids = (1, 2, 0, 3, 4)
        ys = []
        for idx in head_ids:
            p = points.get(idx)
            if p and p[2] > 0.12:
                ys.append(p[1])
        if ys:
            return sum(ys) / float(len(ys))

        l_sho = points.get(5)
        r_sho = points.get(6)
        if l_sho and r_sho and l_sho[2] > 0.10 and r_sho[2] > 0.10:
            return ((l_sho[1] + r_sho[1]) * 0.5) - 20.0
        return None

    def _suppress_bbox_topleft_snap(self, idx, x, y, conf, prev_points, bbox):
        if not bbox or len(bbox) < 4:
            return x, y, conf

        bx, by, bw, bh = bbox[0], bbox[1], bbox[2], bbox[3]
        if bw <= 1 or bh <= 1:
            return x, y, conf

        snap_px = float(getattr(config, "BBOX_TOPLEFT_SNAP_PX", 12))
        conf_max = float(getattr(config, "BBOX_TOPLEFT_SNAP_CONF_MAX", 0.78))
        jump_ratio = float(getattr(config, "BBOX_TOPLEFT_SNAP_JUMP_RATIO", 0.18))
        near_tl = (x <= (bx + snap_px) and y <= (by + snap_px))
        if not near_tl:
            return x, y, conf

        prev = prev_points.get(idx)
        if prev:
            px, py, pconf = prev[0], prev[1], prev[2]
            prev_near_tl = (px <= (bx + snap_px) and py <= (by + snap_px))
            jump_th = max(6.0, bh * jump_ratio)
            jump_dist = self._dist((x, y), (px, py))
            # Snap outlier: frame hien tai nhay manh vao top-left bbox.
            if (not prev_near_tl) and jump_dist >= jump_th and conf <= conf_max:
                return px, py, max(conf, pconf * 0.70)
        else:
            # Frame dau ma da o dung goc top-left va conf khong cao -> cat bo.
            if conf <= min(conf_max, 0.55):
                return x, y, 0.0

        return x, y, conf

    def _arm_fix(self, side, points, prev_points, arm_refs, bbox):
        if side == "left":
            s_idx, e_idx, w_idx = 5, 7, 9
            conf_floor = float(getattr(config, "LEFT_ARM_CONF_FLOOR", 0.18))
        else:
            s_idx, e_idx, w_idx = 6, 8, 10
            conf_floor = float(getattr(config, "RIGHT_ARM_CONF_FLOOR", 0.18))

        p_s = points.get(s_idx)
        p_e = points.get(e_idx)
        p_w = points.get(w_idx)
        if not p_s or not p_e or not p_w:
            return
        if p_s[2] <= 0.10:
            return

        # Torso scale de chuan hoa nguong.
        torso = 1.0
        l_sho = points.get(5)
        r_sho = points.get(6)
        l_hip = points.get(11)
        r_hip = points.get(12)
        if l_sho and r_sho and l_hip and r_hip and l_sho[2] > 0.10 and r_sho[2] > 0.10 and l_hip[2] > 0.10 and r_hip[2] > 0.10:
            mid_sho = ((l_sho[0] + r_sho[0]) * 0.5, (l_sho[1] + r_sho[1]) * 0.5)
            mid_hip = ((l_hip[0] + r_hip[0]) * 0.5, (l_hip[1] + r_hip[1]) * 0.5)
            torso = max(1.0, self._dist(mid_sho, mid_hip))

        upper = self._dist(p_s, p_e)
        lower = self._dist(p_e, p_w)
        full = self._dist(p_s, p_w)

        ref_min_conf = float(getattr(config, "ARM_REF_MIN_CONF", 0.22))
        alpha = float(getattr(config, "ARM_REF_UPDATE_ALPHA", 0.25))

        # Cap nhat tham chieu khi du tin cay.
        if p_e[2] >= ref_min_conf and p_w[2] >= ref_min_conf and full >= (0.14 * torso):
            ref = arm_refs.get(side)
            if ref is None:
                arm_refs[side] = {"upper": upper, "lower": lower, "full": full}
            else:
                ref["upper"] = (alpha * upper) + ((1.0 - alpha) * ref["upper"])
                ref["lower"] = (alpha * lower) + ((1.0 - alpha) * ref["lower"])
                ref["full"] = (alpha * full) + ((1.0 - alpha) * ref["full"])

        ref = arm_refs.get(side)
        if not ref:
            return

        head_y = self._head_y(points)
        head_margin = float(getattr(config, "ARM_SHRINK_HEAD_MARGIN_RATIO", 0.16)) * torso
        top_edge_px = float(getattr(config, "ARM_TOP_EDGE_PX", 14))
        is_high = False
        if head_y is not None:
            is_high = (p_w[1] < (head_y + head_margin)) and (p_e[1] < (p_s[1] + 0.10 * torso))
        if (not is_high) and bbox and len(bbox) >= 4:
            by = bbox[1]
            is_high = (p_w[1] <= (by + top_edge_px)) or (p_e[1] <= (by + top_edge_px))
        if not is_high:
            return

        # Neu joint arm mat conf, uu tien lay joint frame truoc de tranh roi canh tay.
        if p_e[2] <= conf_floor:
            prev_e = prev_points.get(e_idx)
            if prev_e:
                p_e[0], p_e[1], p_e[2] = prev_e[0], prev_e[1], max(conf_floor, prev_e[2] * 0.70)
        if p_w[2] <= conf_floor:
            prev_w = prev_points.get(w_idx)
            if prev_w:
                p_w[0], p_w[1], p_w[2] = prev_w[0], prev_w[1], max(conf_floor, prev_w[2] * 0.70)

        # Re-calc segment lengths sau buoc rescue.
        upper = self._dist(p_s, p_e)
        lower = self._dist(p_e, p_w)
        full = self._dist(p_s, p_w)

        # Segment-level anti-shrink: giu on dinh tung khuc xuong.
        seg_min_ratio = float(getattr(config, "ARM_SEG_MIN_RATIO", 0.70))
        seg_target_ratio = float(getattr(config, "ARM_SEG_TARGET_RATIO", 0.96))
        ref_upper = max(1e-3, ref["upper"])
        ref_lower = max(1e-3, ref["lower"])
        prev_w = prev_points.get(w_idx)

        # On dinh vai->khuyu.
        if upper < (ref_upper * seg_min_ratio):
            if prev_w:
                vx = prev_w[0] - p_s[0]
                vy = prev_w[1] - p_s[1]
            else:
                vx = p_w[0] - p_s[0]
                vy = p_w[1] - p_s[1]
            norm = math.sqrt(vx * vx + vy * vy)
            if norm < 1e-3:
                vx, vy, norm = 0.0, -1.0, 1.0
            ux, uy = vx / norm, vy / norm
            if uy > -0.12:
                ux, uy = 0.0, -1.0
            upper_target = max(upper, ref_upper * seg_target_ratio)
            p_e[0] = p_s[0] + (ux * upper_target)
            p_e[1] = p_s[1] + (uy * upper_target)
            p_e[2] = max(p_e[2], conf_floor)

        # On dinh khuyu->co tay.
        upper = self._dist(p_s, p_e)
        lower = self._dist(p_e, p_w)
        if lower < (ref_lower * seg_min_ratio):
            if prev_w:
                vx = prev_w[0] - p_e[0]
                vy = prev_w[1] - p_e[1]
            else:
                vx = p_w[0] - p_e[0]
                vy = p_w[1] - p_e[1]
            norm = math.sqrt(vx * vx + vy * vy)
            if norm < 1e-3:
                vx, vy, norm = 0.0, -1.0, 1.0
            ux, uy = vx / norm, vy / norm
            if uy > -0.12:
                ux, uy = 0.0, -1.0
            lower_target = max(lower, ref_lower * seg_target_ratio)
            p_w[0] = p_e[0] + (ux * lower_target)
            p_w[1] = p_e[1] + (uy * lower_target)
            p_w[2] = max(p_w[2], conf_floor)

        full = self._dist(p_s, p_w)
        ref_full = max(1e-3, ref["full"])
        shrink_ratio = full / ref_full
        min_ratio = float(getattr(config, "ARM_SHRINK_MIN_RATIO", 0.68))
        if shrink_ratio >= min_ratio:
            points[e_idx] = [p_e[0], p_e[1], p_e[2]]
            points[w_idx] = [p_w[0], p_w[1], p_w[2]]
            return

        # Lay huong tham chieu tu frame truoc; fallback tu frame hien tai.
        if prev_w:
            vx = prev_w[0] - p_s[0]
            vy = prev_w[1] - p_s[1]
        else:
            vx = p_w[0] - p_s[0]
            vy = p_w[1] - p_s[1]

        norm = math.sqrt(vx * vx + vy * vy)
        if norm < 1e-3:
            vx, vy, norm = 0.0, -1.0, 1.0
        ux, uy = vx / norm, vy / norm

        # Tay cao thi vector phai huong len; neu huong sai thi ep theo truc Y am.
        if uy > -0.12:
            ux, uy = 0.0, -1.0

        target_ratio = float(getattr(config, "ARM_SHRINK_TARGET_RATIO", 0.92))
        target_upper = max(ref["upper"] * target_ratio, upper)
        target_full = max(ref["full"] * target_ratio, full)

        new_e_x = p_s[0] + (ux * target_upper)
        new_e_y = p_s[1] + (uy * target_upper)
        new_w_x = p_s[0] + (ux * target_full)
        new_w_y = p_s[1] + (uy * target_full)

        if head_y is not None:
            new_w_y = min(new_w_y, head_y + head_margin)
            new_e_y = min(new_e_y, p_s[1] - 0.05 * torso)

        if bbox and len(bbox) >= 4:
            bx, by, bw, bh = bbox[0], bbox[1], bbox[2], bbox[3]
            max_x = bx + bw - 1
            max_y = by + bh - 1
            new_e_x = max(bx, min(max_x, new_e_x))
            new_e_y = max(by, min(max_y, new_e_y))
            new_w_x = max(bx, min(max_x, new_w_x))
            new_w_y = max(by, min(max_y, new_w_y))

        points[e_idx] = [new_e_x, new_e_y, max(p_e[2], conf_floor)]
        points[w_idx] = [new_w_x, new_w_y, max(p_w[2], conf_floor)]

    def filter_kpts(self, oid, t, kpts, bbox=None):
        if not kpts:
            return []

        stride = 3 if len(kpts) % 3 == 0 else 2
        num_points = len(kpts) // stride

        if oid not in self.object_filters:
            self.object_filters[oid] = {"prev_points": {}, "missing": {}, "arm_refs": {}}
        state = self.object_filters[oid]
        prev_points = state["prev_points"]
        missing = state["missing"]
        arm_refs = state.get("arm_refs", {})
        if not isinstance(arm_refs, dict):
            arm_refs = {}
        state["arm_refs"] = arm_refs

        left_arm_hold_frames = getattr(config, "LEFT_ARM_HOLD_FRAMES", 2)
        left_arm_conf_floor = getattr(config, "LEFT_ARM_CONF_FLOOR", 0.18)
        right_arm_hold_frames = getattr(config, "RIGHT_ARM_HOLD_FRAMES", 2)
        right_arm_conf_floor = getattr(config, "RIGHT_ARM_CONF_FLOOR", 0.18)
        high_hold_bonus = int(getattr(config, "ARM_HIGH_HOLD_BONUS_FRAMES", 2))

        bx = by = bw = bh = None
        if bbox and len(bbox) >= 4:
            bx, by, bw, bh = bbox[0], bbox[1], bbox[2], bbox[3]

        points = {}
        for i in range(num_points):
            base = i * stride
            x = float(kpts[base])
            y = float(kpts[base + 1])
            conf = float(kpts[base + 2]) if stride == 3 else 1.0

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
                    if prev and by is not None and bh and prev[1] < (by + 0.45 * bh):
                        hold_frames += high_hold_bonus
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

            if bx is not None and bw > 1 and bh > 1:
                x = max(bx, min(bx + bw - 1, x))
                y = max(by, min(by + bh - 1, y))
                if stride == 3 and conf > 0.0:
                    x, y, conf = self._suppress_bbox_topleft_snap(i, x, y, conf, prev_points, bbox)

            points[i] = [x, y, conf]

        if stride == 3 and getattr(config, "ARM_SHRINK_FIX_ENABLE", True):
            self._arm_fix("left", points, prev_points, arm_refs, bbox)
            self._arm_fix("right", points, prev_points, arm_refs, bbox)

        filtered_kpts = []
        for i in range(num_points):
            p = points.get(i, [0.0, 0.0, 0.0 if stride == 3 else 1.0])
            x, y, conf = p[0], p[1], p[2]
            if stride == 3 and conf > 0.0:
                prev_points[i] = (x, y, conf)
            filtered_kpts.extend([x, y])
            if stride == 3:
                filtered_kpts.append(conf)

        return filtered_kpts
