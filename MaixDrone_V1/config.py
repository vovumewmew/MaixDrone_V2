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
CAM_WIDTH = 320     # Chiều rộng (Width)
CAM_HEIGHT = 240    # Chiều cao (Height)
JPEG_QUALITY = 25   
FPS_LIMIT = 30      

# --- CẤU HÌNH AI ---
ENABLE_AI = True   
MODEL_PATH = "/root/models/yolo11n_pose.mud"        # Hỗ trợ đuôi .mud (ưu tiên) hoặc .cvimodel

# Ngưỡng tin cậy cho Detect (thường Detect nhạy hơn nên để cao chút cho chắc)
CONF_THRESHOLD = 0.20 # [UPDATE] Giảm sâu hơn để bắt vật thể xa/bị che khuất
KEYPOINT_THRESHOLD = 0.0 # [RAW] Lấy tất cả điểm AI trả về (Trust AI)

# --- ADAPTIVE DETECT THRESHOLD (THEO KHOANG CACH) ---
ADAPTIVE_THRESH_ENABLE = True
ADAPTIVE_NEAR_HEIGHT_RATIO = 0.42
ADAPTIVE_FAR_HEIGHT_RATIO = 0.22
ADAPTIVE_CONF_NEAR = 0.26
ADAPTIVE_CONF_MID = 0.20
ADAPTIVE_CONF_FAR = 0.14
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
BBOX_TL_IGNORE_PX = 6           # [FILTER] Bỏ điểm quá gần góc trên-trái của bbox
BBOX_TOPLEFT_SNAP_PX = 12       # [FILTER] Nhan dien diem snap vao goc tren-trai cua bbox
BBOX_TOPLEFT_SNAP_CONF_MAX = 0.78  # [FILTER] Chi xu ly snap khi conf khong thuc su manh
BBOX_TOPLEFT_SNAP_JUMP_RATIO = 0.18  # [FILTER] Muc nhay toi thieu (theo bbox_h) de coi la outlier
GHOST_POINT_CORNER_PX = 12      # [FILTER] Bo diem ma o 2 goc tren man hinh
GHOST_HEAD_TOP_BAND_RATIO = 0.12  # [FILTER] Vung top cua bbox de tim ghost head-point
GHOST_HEAD_CONF_MAX = 0.65        # [FILTER] Gioi han conf de loai head-point don le
GHOST_HEAD_ISO_DIST_RATIO = 0.14  # [FILTER] Ban kinh lang gieng hop le cua cum head
GHOST_BODY_TOP_BAND_RATIO = 0.05  # [FILTER] Vung top de cat body-point ma
GHOST_BODY_CONF_MAX = 0.28        # [FILTER] Gioi han conf cho body-point ma sat top
TOP_SCREEN_GHOST_STRIP_PX = 18    # [FILTER] Vung sat mep tren man hinh de quet ghost
TOP_SCREEN_GHOST_CONF_MAX = 0.92  # [FILTER] Nguong conf toi da de cat diem ghost top-strip
TOP_SCREEN_GHOST_KEEP_ARM_CONF_MIN = 0.60  # [FILTER] Giu lai tay cao that neu conf du cao
TOP_SCREEN_GHOST_KEEP_HEAD_CONF_MIN = 0.75 # [FILTER] Giu lai cum dau neu conf du cao

# --- CẤU HÌNH BẢO TOÀN TAY PHẢI KHI GIƠ CAO ---
RIGHT_ARM_HOLD_FRAMES = 4       # Giữ tạm keypoint khuỷu/cổ tay phải khi mất điểm ngắn hạn
RIGHT_ARM_CONF_FLOOR = 0.18     # Ngưỡng conf tối thiểu để kích hoạt cơ chế giữ tay phải

# --- CẤU HÌNH BẢO TOÀN TAY TRÁI KHI GIƠ CAO ---
LEFT_ARM_HOLD_FRAMES = 4        # Giữ tạm keypoint khuỷu/cổ tay trái khi mất điểm ngắn hạn
LEFT_ARM_CONF_FLOOR = 0.18      # Ngưỡng conf tối thiểu để kích hoạt cơ chế giữ tay trái

# --- CHONG CO RUT TAY KHI GIO CAO ---
ARM_SHRINK_FIX_ENABLE = True
ARM_SHRINK_MIN_RATIO = 0.78
ARM_SHRINK_TARGET_RATIO = 0.98
ARM_SHRINK_HEAD_MARGIN_RATIO = 0.16
ARM_REF_UPDATE_ALPHA = 0.25
ARM_REF_MIN_CONF = 0.22
ARM_SEG_MIN_RATIO = 0.80
ARM_SEG_TARGET_RATIO = 0.99
ARM_TOP_EDGE_PX = 14
ARM_HIGH_HOLD_BONUS_FRAMES = 4

# --- CẤU HÌNH TRACKING ACCURACY/SPEED ---
TRACK_MAX_MISS = 12             # Số frame cho phép mất dấu trước khi xóa track
TRACK_DIST_THRESHOLD = 100      # Ngưỡng khoảng cách cơ sở cho matching
TRACK_COST_THRESHOLD = 1.20     # Ngưỡng cost tối đa để chấp nhận ghép cặp
POSE_MIN_VISIBLE_RATIO = 0.35   # Tối thiểu tỉ lệ điểm rõ để chạy nhận diện động tác

# --- CẤU HÌNH NHẬN DIỆN TAY CAO (LEFT/RIGHT HIGH) ---
HIGH_HAND_WRIST_CONF_MIN = 0.12     # Ngưỡng conf cổ tay tối thiểu để xét trạng thái tay cao
HIGH_HAND_HEAD_MARGIN_RATIO = 0.10  # Cho phép cổ tay thấp hơn đầu một chút (theo torso_len)
HIGH_HAND_ELBOW_LIFT_RATIO = 0.20   # Mức khuỷu cần nâng lên so với vai (theo HORIZ_TOL)
HIGH_HAND_EXT_RATIO = 0.30          # Độ vươn tay cơ bản
HIGH_HAND_EXT_RATIO_LOOSE = 0.16    # Độ vươn tay tối thiểu cho nhánh tay cao
