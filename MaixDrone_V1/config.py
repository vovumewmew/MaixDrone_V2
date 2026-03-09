# config.py

# --- CẤU HÌNH MẠNG ---
HOST = "0.0.0.0"
PORT = 80
TIMEOUT = 3.0
NETWORK_MODE = "wifi"  # "wifi" | "lan" (doi 1 dong nay khi demo)

# --- CẤU HÌNH WIFI (Sửa Wifi tại đây) ---
WIFI_SSID = "HUTECH STAFF"
WIFI_PASS = "staff@@hutech"

# --- CẤU HÌNH TINKERBOARD ---
TINKER_IP_WIFI = "10.60.5.238" # IP Tinker khi MaixCam chay qua Wi-Fi
TINKER_IP_LAN = "10.60.5.238"  # IP Tinker khi MaixCam chay qua LAN
TINKER_IP = TINKER_IP_WIFI      # [BACKWARD COMPAT] fallback cho code cu
TINKER_PORT = 9999          # Port mà Tinkerboard đang lắng nghe
ENABLE_TINKER = False      # [USER REQUEST] True: Mở kết nối, False: Tắt kết nối

# --- CẤU HÌNH CAMERA (CHẾ ĐỘ HD) ---
CAM_WIDTH = 320     # Chiều rộng (Width) - [REVERT] Về mức tối ưu cho AI
CAM_HEIGHT = 240    # Chiều cao (Height)
JPEG_QUALITY = 30   # Chất lượng ảnh stream vừa phải
FPS_LIMIT = 30      # Giới hạn FPS để ổn định nhiệt độ

# --- CẤU HÌNH AI ---
ENABLE_AI = True   
MODEL_PATH = "/root/models/yolo11n_pose.mud"        # Hỗ trợ đuôi .mud (ưu tiên) hoặc .cvimodel
AI_LETTERBOX_MODE = True    # [MAX ACCURACY] True: Dùng CPU chèn viền đen (Chuẩn hình); False: Kéo giãn (Nhanh)

# Ngưỡng tin cậy cho Detect (thường Detect nhạy hơn nên để cao chút cho chắc)
CONF_THRESHOLD = 0.15 # [UPDATE] Giảm sâu hơn (0.20 -> 0.15) để bắt tốt hơn ở xa (2.5m-3m)
KEYPOINT_THRESHOLD = 0.0 # [RAW] Lấy tất cả điểm AI trả về (Trust AI)

# --- ADAPTIVE DETECT THRESHOLD (THEO KHOANG CACH) ---
ADAPTIVE_THRESH_ENABLE = True
ADAPTIVE_NEAR_HEIGHT_RATIO = 0.42
ADAPTIVE_FAR_HEIGHT_RATIO = 0.22
ADAPTIVE_CONF_NEAR = 0.26
ADAPTIVE_CONF_MID = 0.20
ADAPTIVE_CONF_FAR = 0.12 # [UPDATE] Giảm ngưỡng xa xuống 0.12 để không mất điểm
ADAPTIVE_IOU_NEAR = 0.50
ADAPTIVE_IOU_MID = 0.45
ADAPTIVE_IOU_FAR = 0.38
ADAPTIVE_KPT_TH_NEAR = 0.05
ADAPTIVE_KPT_TH_MID = 0.02
ADAPTIVE_KPT_TH_FAR = 0.00
ADAPTIVE_DIST_EMA_ALPHA = 0.35
ADAPTIVE_MISS_FORCE_FAR_FRAMES = 3
ADAPTIVE_RESCUE_ENABLE = True
ADAPTIVE_RESCUE_CONF_DELTA = 0.04
ADAPTIVE_RESCUE_IOU_DELTA = 0.05
ADAPTIVE_RESCUE_CONF_MIN = 0.10
ADAPTIVE_RESCUE_IOU_MIN = 0.30
ADAPTIVE_TOP_EDGE_ENABLE = True
ADAPTIVE_TOP_EDGE_PX = 14
ADAPTIVE_TOP_EDGE_BOOST_FRAMES = 6
ADAPTIVE_TOP_EDGE_CONF_DELTA = 0.03
ADAPTIVE_TOP_EDGE_IOU_DELTA = 0.03

# --- CẤU HÌNH BỘ LỌC (FILTERING & POST-PROCESSING) ---
POSE_CONF_THRESHOLD = 0.0       # [RAW] Không lọc điểm yếu
STICKY_DEADZONE = 0.0           # [RAW] Tắt chống rung
BBOX_TL_IGNORE_PX = 6           # [REVERT] 12 -> 6
BBOX_TOPLEFT_SNAP_PX = 12       # [REVERT] 24 -> 12
BBOX_TOPLEFT_SNAP_CONF_MAX = 0.78  # [FILTER] Chi xu ly snap khi conf khong thuc su manh
BBOX_TOPLEFT_SNAP_JUMP_RATIO = 0.18  # [FILTER] Muc nhay toi thieu (theo bbox_h) de coi la outlier
GHOST_POINT_CORNER_PX = 12      # [REVERT] 24 -> 12
GHOST_HEAD_TOP_BAND_RATIO = 0.18  # [UPDATE] 0.15 -> 0.18: Quét sâu hơn xuống trán để diệt ma
GHOST_HEAD_CONF_MAX = 0.85        # [UPDATE] 0.80 -> 0.85: Gần như diệt mọi điểm cô lập trên đầu
GHOST_HEAD_ISO_DIST_RATIO = 0.22  # [UPDATE] 0.18 -> 0.22: Tăng bán kính tìm bạn (cô lập là diệt)
GHOST_BODY_TOP_BAND_RATIO = 0.05  # [FILTER] Vung top de cat body-point ma
GHOST_BODY_CONF_MAX = 0.28        # [FILTER] Gioi han conf cho body-point ma sat top
TOP_SCREEN_GHOST_STRIP_PX = 18    # [REVERT] 36 -> 18
TOP_SCREEN_GHOST_CONF_MAX = 0.92  # [FILTER] Nguong conf toi da de cat diem ghost top-strip
TOP_SCREEN_GHOST_KEEP_ARM_CONF_MIN = 0.60  # [FILTER] Giu lai tay cao that neu conf du cao
TOP_SCREEN_GHOST_KEEP_HEAD_CONF_MIN = 0.75 # [FILTER] Giu lai cum dau neu conf du cao

# --- CẤU HÌNH BẢO TOÀN TAY PHẢI KHI GIƠ CAO ---
RIGHT_ARM_HOLD_FRAMES = 10      # [UPDATE] 4 -> 10: Tăng độ lì cho tay phải, giữ vị trí lâu hơn khi bị nhiễu
RIGHT_ARM_CONF_FLOOR = 0.18     # Ngưỡng conf tối thiểu để kích hoạt cơ chế giữ tay phải

# --- CẤU HÌNH BẢO TOÀN TAY TRÁI KHI GIƠ CAO ---
LEFT_ARM_HOLD_FRAMES = 10       # [FIX] 4 -> 10: Đồng bộ độ lì với tay phải để chống co rút tay trái
LEFT_ARM_CONF_FLOOR = 0.18      # Ngưỡng conf tối thiểu để kích hoạt cơ chế giữ tay trái

# --- CHONG CO RUT TAY KHI GIO CAO ---
ARM_SHRINK_FIX_ENABLE = True
ARM_SHRINK_MIN_RATIO = 0.95     # [TUNE] 0.92 -> 0.95: Siêu nhạy, ngắn đi 5% là Fix ngay
ARM_SHRINK_TARGET_RATIO = 1.20  # [UPDATE] 1.15 -> 1.20: Kéo dài tay 120% (bù trừ cực mạnh cho góc nhìn xa)
ARM_SHRINK_HEAD_MARGIN_RATIO = 0.16
ARM_REF_UPDATE_ALPHA = 0.08     # [UPDATE] 0.15 -> 0.08: Học cực chậm, ưu tiên độ dài tay lúc duỗi thẳng
ARM_REF_MIN_CONF = 0.14         # [TUNE] 0.22 -> 0.14: Quan trọng! Cho phép học độ dài tay ở xa (conf thấp)
ARM_SEG_MIN_RATIO = 0.85        # [TUNE] 0.80 -> 0.85: Giữ độ dài từng đoạn xương (khuỷu/cổ tay) chặt hơn
ARM_SEG_TARGET_RATIO = 1.05     # [TUNE] 0.99 -> 1.05: Kéo giãn từng đoạn xương
ARM_TOP_EDGE_PX = 14            # [REVERT] 28 -> 14
ARM_HIGH_HOLD_BONUS_FRAMES = 4

# --- CẤU HÌNH TRACKING ACCURACY/SPEED ---
TRACK_MAX_MISS = 12             # Số frame cho phép mất dấu trước khi xóa track
TRACK_DIST_THRESHOLD = 100      # [REVERT] 200 -> 100
TRACK_COST_THRESHOLD = 1.20     # Ngưỡng cost tối đa để chấp nhận ghép cặp
POSE_MIN_VISIBLE_RATIO = 0.35   # Tối thiểu tỉ lệ điểm rõ để chạy nhận diện động tác

# --- CẤU HÌNH NHẬN DIỆN TAY CAO (LEFT/RIGHT HIGH) ---
HIGH_HAND_WRIST_CONF_MIN = 0.12     # Ngưỡng conf cổ tay tối thiểu để xét trạng thái tay cao
HIGH_HAND_HEAD_MARGIN_RATIO = 0.10  # Cho phép cổ tay thấp hơn đầu một chút (theo torso_len)
HIGH_HAND_ELBOW_LIFT_RATIO = 0.20   # Mức khuỷu cần nâng lên so với vai (theo HORIZ_TOL)
HIGH_HAND_EXT_RATIO = 0.30          # Độ vươn tay cơ bản
HIGH_HAND_EXT_RATIO_LOOSE = 0.16    # Độ vươn tay tối thiểu cho nhánh tay cao
