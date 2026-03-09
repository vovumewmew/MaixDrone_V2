from maix import nn, image
import math # [NEW] Cần dùng math để tính khoảng cách xương
import config # Import config để lấy KEYPOINT_THRESHOLD
import time # [NEW] Để kiểm soát spam log

class AIEngine:
    def __init__(self, model_path, conf_threshold):
        self.model_path = model_path
        self.threshold = conf_threshold
        self.model = None
        self.input_w = 0 # [AUTO] Sẽ tự cập nhật theo Model
        self.input_h = 0 # [AUTO] Sẽ tự cập nhật theo Model
        self.first_run = True # [DEBUG] Biến cờ để chỉ in log 1 lần
        self.last_warning_time = 0 # [DEBUG] Chống spam cảnh báo
        self.dist_ratio_ema = None
        self.missed_frames = 0
        self.top_edge_bias_frames = 0

    def _select_detect_thresholds(self):
        if not getattr(config, "ADAPTIVE_THRESH_ENABLE", True):
            return self.threshold, 0.45, config.KEYPOINT_THRESHOLD

        ratio = self.dist_ratio_ema
        near_ratio = float(getattr(config, "ADAPTIVE_NEAR_HEIGHT_RATIO", 0.42))
        far_ratio = float(getattr(config, "ADAPTIVE_FAR_HEIGHT_RATIO", 0.22))

        # Mat dau lien tiep -> uu tien profile "far" de bat lai doi tuong o xa.
        if self.missed_frames >= int(getattr(config, "ADAPTIVE_MISS_FORCE_FAR_FRAMES", 3)):
            band = "far"
        elif ratio is None:
            band = "mid"
        elif ratio >= near_ratio:
            band = "near"
        elif ratio <= far_ratio:
            band = "far"
        else:
            band = "mid"

        if band == "near":
            conf_th = float(getattr(config, "ADAPTIVE_CONF_NEAR", self.threshold))
            iou_th = float(getattr(config, "ADAPTIVE_IOU_NEAR", 0.50))
            kpt_th = float(getattr(config, "ADAPTIVE_KPT_TH_NEAR", config.KEYPOINT_THRESHOLD))
        elif band == "far":
            conf_th = float(getattr(config, "ADAPTIVE_CONF_FAR", self.threshold))
            iou_th = float(getattr(config, "ADAPTIVE_IOU_FAR", 0.38))
            kpt_th = float(getattr(config, "ADAPTIVE_KPT_TH_FAR", 0.0))
        else:
            conf_th = float(getattr(config, "ADAPTIVE_CONF_MID", self.threshold))
            iou_th = float(getattr(config, "ADAPTIVE_IOU_MID", 0.45))
            kpt_th = float(getattr(config, "ADAPTIVE_KPT_TH_MID", config.KEYPOINT_THRESHOLD))

        # Top-edge boost: khi tay giơ cao sat mép trên, nới threshold tạm thời để tránh rớt.
        if self.top_edge_bias_frames > 0 and getattr(config, "ADAPTIVE_TOP_EDGE_ENABLE", True):
            conf_th -= float(getattr(config, "ADAPTIVE_TOP_EDGE_CONF_DELTA", 0.03))
            iou_th -= float(getattr(config, "ADAPTIVE_TOP_EDGE_IOU_DELTA", 0.03))

        conf_th = max(
            float(getattr(config, "ADAPTIVE_RESCUE_CONF_MIN", 0.10)),
            min(0.60, conf_th)
        )
        iou_th = max(
            float(getattr(config, "ADAPTIVE_RESCUE_IOU_MIN", 0.30)),
            min(0.75, iou_th)
        )

        return conf_th, iou_th, kpt_th

    def _get_bbox_padding(self):
        ratio = self.dist_ratio_ema
        near_ratio = float(getattr(config, "ADAPTIVE_NEAR_HEIGHT_RATIO", 0.42))
        far_ratio = float(getattr(config, "ADAPTIVE_FAR_HEIGHT_RATIO", 0.22))

        # Default (mid)
        pad_w_ratio = 0.18
        pad_top_ratio = 0.42
        pad_bottom_ratio = 0.12

        if ratio is not None:
            if ratio <= far_ratio:
                pad_w_ratio = 0.22
                pad_top_ratio = 0.56
                pad_bottom_ratio = 0.14
            elif ratio >= near_ratio:
                pad_w_ratio = 0.14
                pad_top_ratio = 0.34
                pad_bottom_ratio = 0.10

        if self.top_edge_bias_frames > 0:
            pad_top_ratio += 0.08
            pad_w_ratio += 0.02

        return pad_w_ratio, pad_top_ratio, pad_bottom_ratio

    def _detect_with_adaptive_thresholds(self, img_input):
        conf_th, iou_th, kpt_th = self._select_detect_thresholds()
        objs = self.model.detect(img_input, conf_th=conf_th, iou_th=iou_th, keypoint_th=kpt_th)

        # Rescue pass: chi kich hoat khi khong co ket qua.
        if (not objs) and getattr(config, "ADAPTIVE_RESCUE_ENABLE", True):
            rescue_conf = max(
                float(getattr(config, "ADAPTIVE_RESCUE_CONF_MIN", 0.10)),
                conf_th - float(getattr(config, "ADAPTIVE_RESCUE_CONF_DELTA", 0.04))
            )
            rescue_iou = max(
                float(getattr(config, "ADAPTIVE_RESCUE_IOU_MIN", 0.30)),
                iou_th - float(getattr(config, "ADAPTIVE_RESCUE_IOU_DELTA", 0.05))
            )
            objs = self.model.detect(
                img_input,
                conf_th=rescue_conf,
                iou_th=rescue_iou,
                keypoint_th=float(getattr(config, "ADAPTIVE_KPT_TH_FAR", 0.0))
            )

        return objs

    def _update_distance_state(self, img_h, results):
        if not results:
            self.missed_frames += 1
            if self.missed_frames > 30:
                self.missed_frames = 30
            if self.top_edge_bias_frames > 0:
                self.top_edge_bias_frames -= 1
            return

        self.missed_frames = 0
        dom_h = 0.0
        for r in results:
            h = float(r.get("h", 0.0))
            if h > dom_h:
                dom_h = h
        if dom_h <= 0.0 or img_h <= 0:
            return

        ratio = dom_h / float(img_h)
        alpha = float(getattr(config, "ADAPTIVE_DIST_EMA_ALPHA", 0.35))
        if self.dist_ratio_ema is None:
            self.dist_ratio_ema = ratio
        else:
            self.dist_ratio_ema = (alpha * ratio) + ((1.0 - alpha) * self.dist_ratio_ema)

        # Cap nhat co "top-edge contact" de boost detect trong vai frame tiep theo.
        if getattr(config, "ADAPTIVE_TOP_EDGE_ENABLE", True):
            edge_px = int(getattr(config, "ADAPTIVE_TOP_EDGE_PX", 14))
            hit_top = False
            for r in results:
                if float(r.get("y", 9999.0)) <= edge_px:
                    hit_top = True
                    break
            if hit_top:
                self.top_edge_bias_frames = int(getattr(config, "ADAPTIVE_TOP_EDGE_BOOST_FRAMES", 6))
            elif self.top_edge_bias_frames > 0:
                self.top_edge_bias_frames -= 1

    def _suppress_top_screen_ghosts(self, points, bx, by, bw, bh, img_h):
        if not points:
            return

        top_strip = int(getattr(config, "TOP_SCREEN_GHOST_STRIP_PX", 18))
        if top_strip <= 0:
            return
        top_strip = max(4, min(top_strip, max(8, int(img_h * 0.20))))

        conf_cut = float(getattr(config, "TOP_SCREEN_GHOST_CONF_MAX", 0.92))
        keep_arm_conf = float(getattr(config, "TOP_SCREEN_GHOST_KEEP_ARM_CONF_MIN", 0.60))
        keep_head_conf = float(getattr(config, "TOP_SCREEN_GHOST_KEEP_HEAD_CONF_MIN", 0.75))
        tl_px = float(getattr(config, "BBOX_TOPLEFT_SNAP_PX", 12))
        bh_ref = max(1.0, bh)
        head_ids = (0, 1, 2, 3, 4)

        for idx in range(len(points)):
            x, y, conf = points[idx]
            if conf <= 0.0 or y > top_strip:
                continue

            keep = False

            # Giu lai tay gio cao neu lien ket vai-hop ly va conf du cao.
            if idx in (7, 8, 9, 10):
                shoulder_idx = 5 if idx in (7, 9) else 6
                if shoulder_idx < len(points):
                    sx, sy, sc = points[shoulder_idx]
                    if sc > 0.18 and conf >= keep_arm_conf:
                        d = math.sqrt((x - sx) * (x - sx) + (y - sy) * (y - sy))
                        d_min = 0.06 * bh_ref if idx in (7, 8) else 0.12 * bh_ref
                        d_max = 1.35 * bh_ref
                        if d_min <= d <= d_max:
                            if not (x <= (bx + tl_px) and y <= (by + tl_px)):
                                keep = True

            # Giu lai cum dau neu co diem lan can xac nhan.
            elif idx in head_ids and conf >= keep_head_conf:
                neighbor = 0
                for oid in head_ids:
                    if oid == idx or oid >= len(points):
                        continue
                    ox, oy, oc = points[oid]
                    if oc <= 0.0 or oy > (top_strip + 6):
                        continue
                    if oc < (keep_head_conf * 0.70):
                        continue
                    if math.sqrt((x - ox) * (x - ox) + (y - oy) * (y - oy)) <= max(5.0, bh_ref * 0.20):
                        neighbor += 1
                if neighbor >= 1:
                    keep = True

            if (not keep) and conf <= conf_cut:
                points[idx][2] = 0.0

    def load(self):
        try:
            print(f"🧠 Loading Model: {self.model_path}")
            
            # [AUTO-DETECT] Tự động chọn class phù hợp với phiên bản YOLO
            path_lower = self.model_path.lower()
            # [UPDATE] Loại bỏ YOLOv5, tập trung vào YOLO11. YOLOv8 là phụ.
            if "yolov8" in path_lower:
                self.model = nn.YOLOv8(self.model_path, dual_buff=True)
            else:
                # Mặc định là YOLO11 (cho cả yolo11n, yolo11s...)
                self.model = nn.YOLO11(self.model_path, dual_buff=True)
            
            # [NEW] Tự động lấy kích thước input từ Model
            self.input_w = self.model.input_width()
            self.input_h = self.model.input_height()
            print(f"📏 Model Input Size: {self.input_w}x{self.input_h}")
            
            return True
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def process(self, img_hd):
        if not self.model: return img_hd, []
        
        results = []
        
        try:
            # --- GIAI ĐOẠN 1: TÌM NGƯỜI (GLOBAL DETECTION) ---
            
            scale_x = 1.0
            scale_y = 1.0
            pad_w = 0
            pad_h = 0
            
            # [MAX ACCURACY] LETTERBOX MODE
            if getattr(config, "AI_LETTERBOX_MODE", False):
                img_w = img_hd.width()
                img_h = img_hd.height()
                
                # 1. Tính tỷ lệ scale giữ nguyên aspect ratio (r)
                r = min(self.input_w / img_w, self.input_h / img_h)
                new_unpad_w = int(img_w * r)
                new_unpad_h = int(img_h * r)
                
                # 2. Resize ảnh gốc về kích thước mới (vẫn giữ tỷ lệ)
                img_resized = img_hd.resize(new_unpad_w, new_unpad_h)
                
                # 3. Tạo ảnh nền xám (padding)
                img_input = image.Image(self.input_w, self.input_h, image.Format.FMT_RGB888)
                img_input.draw_rect(0, 0, self.input_w, self.input_h, image.Color(114, 114, 114), -1)
                
                # 4. Dán ảnh đã resize vào giữa (Dùng CPU copy memory)
                pad_w = (self.input_w - new_unpad_w) // 2
                pad_h = (self.input_h - new_unpad_h) // 2
                # [FIX] draw_image(x, y, img) - Đúng chuẩn MaixPy
                img_input.draw_image(pad_w, pad_h, img_resized)
                
                # Lưu thông số để map ngược
                scale_x = r
                scale_y = r
                
                if self.first_run:
                    print(f"🚀 [MAX ACCURACY] Letterbox ON: Scale={r:.3f}, Pad=({pad_w},{pad_h})")
                    self.first_run = False
            else:
                # [PERFORMANCE] FAST RESIZE (Méo hình nhẹ)
                if img_hd.width() != self.input_w or img_hd.height() != self.input_h:
                    img_input = img_hd.resize(self.input_w, self.input_h)
                else:
                    img_input = img_hd
                scale_x = img_hd.width() / self.input_w
                scale_y = img_hd.height() / self.input_h
                
                if self.first_run:
                    print(f"🚀 [PERFORMANCE] Fast Resize ON: {scale_x:.2f}x{scale_y:.2f}")
                    self.first_run = False

            # [ADAPTIVE DETECT] conf_th/iou_th thay doi theo khoang cach uoc luong.
            objs = self._detect_with_adaptive_thresholds(img_input)
            
            for obj in objs:
                if getattr(config, "AI_LETTERBOX_MODE", False):
                    # Map Box (Letterbox): (Val - Pad) / Scale
                    bx = (obj.x - pad_w) / scale_x
                    by = (obj.y - pad_h) / scale_y
                    bw = obj.w / scale_x
                    bh = obj.h / scale_y
                else:
                    # Map Box (Resize): Val * Scale
                    bx = obj.x * scale_x
                    by = obj.y * scale_y
                    bw = obj.w * scale_x
                    bh = obj.h * scale_y

                # [PADDING ACCURACY-FIRST] Padding dong theo khoang cach + top-edge.
                pad_w_ratio, pad_top_ratio, pad_bottom_ratio = self._get_bbox_padding()
                pad_w_val = bw * pad_w_ratio
                pad_top_val = bh * pad_top_ratio
                pad_bottom_val = bh * pad_bottom_ratio

                bx -= pad_w_val / 2
                by -= pad_top_val
                bw += pad_w_val
                bh += (pad_top_val + pad_bottom_val)

                # Map Points (Lấy dữ liệu trực tiếp từ AI Global)
                final_points = []
                if obj.points:
                    # [FIX CRITICAL] Tự động xác định stride để tránh lỗi lệch pha dữ liệu
                    # Nếu độ dài chia hết cho 3 -> [x, y, conf]. Nếu không -> [x, y]
                    stride = 3 if len(obj.points) % 3 == 0 else 2
                    num_points = len(obj.points) // stride
                    img_w = img_hd.width()
                    corner_px = int(getattr(config, "GHOST_POINT_CORNER_PX", 12))
                    tl_ignore = int(getattr(config, "BBOX_TL_IGNORE_PX", 6))
                    mapped_points = []

                    for i in range(num_points):
                        base = i * stride
                        # Map Points
                        if getattr(config, "AI_LETTERBOX_MODE", False):
                            px = (obj.points[base] - pad_w) / scale_x
                            py = (obj.points[base+1] - pad_h) / scale_y
                        else:
                            px = obj.points[base] * scale_x
                            py = obj.points[base+1] * scale_y
                            
                        conf = obj.points[base+2] if stride == 3 else 1.0

                        # Kẹp biên ảnh trước khi xử lý tiếp để giảm outlier.
                        px = max(0.0, min(img_hd.width() - 1, px))
                        py = max(0.0, min(img_hd.height() - 1, py))

                        # [NEW STRICT GHOST KILLER] Out-of-FOV Clamp Killer
                        # Bất kỳ điểm nào bị ép chặt vào 2 pixel trên cùng của màn hình (do đứng gần bị lọt ra ngoài) -> Tiêu diệt (Ép conf = 0)!
                        if py <= 2.0:
                            conf = 0.0

                        # [CORNER TRAP SAFER] Không triệt khớp tay (7,8,9,10)
                        # để tránh co rút tay khi giơ cao chạm góc bbox.
                        if conf > 0 and i not in (7, 8, 9, 10) and conf < 0.35:
                            corner_thresh = max(bw, bh) * 0.06
                            d_tl = math.sqrt((px - bx)**2 + (py - by)**2)
                            d_tr = math.sqrt((px - (bx + bw))**2 + (py - by)**2)
                            if d_tl < corner_thresh or d_tr < corner_thresh:
                                conf = 0.0

                        # [GHOST FIX] Loai bo diem ma o goc tren man hinh/box.
                        if conf > 0 and i not in (7, 8, 9, 10):
                            # Diem sat goc tren box (thuong la outlier).
                            if px <= (bx + tl_ignore) and py <= (by + tl_ignore):
                                conf = 0.0
                            else:
                                # Diem sat goc tren man hinh nhung qua xa tam doi tuong.
                                near_img_top_corner = (
                                    py <= corner_px and
                                    (px <= corner_px or px >= (img_w - 1 - corner_px))
                                )
                                if near_img_top_corner:
                                    cx = bx + (bw * 0.5)
                                    cy = by + (bh * 0.5)
                                    d_center = math.sqrt((px - cx)**2 + (py - cy)**2)
                                    if d_center > (max(bw, bh) * 0.85):
                                        conf = 0.0

                        mapped_points.append([px, py, conf])

                    # [HEAD GHOST FIX] Cat diem ma "bay" o top-band ngay tren dau.
                    if stride == 3 and mapped_points:
                        box_top = max(0.0, by)
                        box_h = max(1.0, bh)
                        
                        # [DYNAMIC GHOST] Nếu đối tượng ở gần (Box to > 45% ảnh), mở rộng vùng quét ma
                        base_ghost_ratio = float(getattr(config, "GHOST_HEAD_TOP_BAND_RATIO", 0.15))
                        if box_h > img_hd.height() * 0.45: # [UPDATE] 0.60 -> 0.45: Kích hoạt sớm hơn
                            base_ghost_ratio *= 2.0 # [UPDATE] 1.5 -> 2.0: Quét rộng gấp đôi vùng trên đầu
                        
                        head_top_band = box_top + (box_h * base_ghost_ratio)
                        body_top_band = box_top + (box_h * float(getattr(config, "GHOST_BODY_TOP_BAND_RATIO", 0.05)))
                        head_conf_max = float(getattr(config, "GHOST_HEAD_CONF_MAX", 0.80))
                        body_conf_max = float(getattr(config, "GHOST_BODY_CONF_MAX", 0.28))
                        iso_dist = max(4.0, box_h * float(getattr(config, "GHOST_HEAD_ISO_DIST_RATIO", 0.14)))

                        shoulder_y = None
                        sy_vals = []
                        for sid in (5, 6):
                            if sid < len(mapped_points):
                                sx, sy, sc = mapped_points[sid]
                                if sc > 0.10:
                                    sy_vals.append(sy)
                        if sy_vals:
                            shoulder_y = sum(sy_vals) / float(len(sy_vals))

                        # 1) Head cluster ghost: diem don le sat top-band.
                        head_ids = (0, 1, 2, 3, 4)
                        for hid in head_ids:
                            if hid >= len(mapped_points):
                                continue
                            hx, hy, hc = mapped_points[hid]
                            if hc <= 0.0:
                                continue
                            if hy > head_top_band:
                                continue

                            neighbor_count = 0
                            for oid in head_ids:
                                if oid == hid or oid >= len(mapped_points):
                                    continue
                                ox, oy, oc = mapped_points[oid]
                                if oc <= 0.0:
                                    continue
                                if math.sqrt((hx - ox) * (hx - ox) + (hy - oy) * (hy - oy)) <= iso_dist:
                                    neighbor_count += 1

                            # Diem don le o top-band, khong co cum head hop le -> loai.
                            if neighbor_count == 0 and hc <= head_conf_max:
                                if shoulder_y is None or hy < (shoulder_y - box_h * 0.06):
                                    mapped_points[hid][2] = 0.0

                        # 2) Body ghost sat top-band (khong ap dung cho arm de tranh co rut tay).
                        for bid in range(len(mapped_points)):
                            if bid in (0, 1, 2, 3, 4, 7, 8, 9, 10):
                                continue
                            bxp, byp, bcp = mapped_points[bid]
                            if bcp > 0.0 and bcp <= body_conf_max and byp <= body_top_band:
                                mapped_points[bid][2] = 0.0

                        # 3) Top-screen ghost killer: quet truc tiep vung sat mep tren man hinh.
                        self._suppress_top_screen_ghosts(
                            mapped_points, bx, by, bw, bh, img_hd.height()
                        )

                    for p in mapped_points:
                        final_points.extend([p[0], p[1], p[2]])

                # Convert sang int và kẹp biên
                bx = int(max(0, bx))
                by = int(max(0, by))
                bw = int(min(img_hd.width() - bx, bw))
                bh = int(min(img_hd.height() - by, bh))

                results.append({
                    "x": bx, "y": by, "w": bw, "h": bh, # [STABLE] Vẫn trả về Box gốc ổn định
                    "score": obj.score,
                    "class_id": 0,
                    # [OFFICIAL] Trả về nguyên bản points để dùng hàm draw_pose nếu cần
                    # Lưu ý: final_points của ta đã map về ảnh gốc, rất tốt.
                    "points": final_points 
                })

            self._update_distance_state(img_hd.height(), results)
        except Exception as e:
            print(f"⚠️ AI Error: {e}")
        
        return img_hd, results
