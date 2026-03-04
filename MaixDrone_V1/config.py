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
ENABLE_TINKER = True      # [USER REQUEST] True: Mở kết nối, False: Tắt kết nối

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

# --- CẤU HÌNH BỘ LỌC (FILTERING & POST-PROCESSING) ---
POSE_CONF_THRESHOLD = 0.0       # [RAW] Không lọc điểm yếu
STICKY_DEADZONE = 0.0           # [RAW] Tắt chống rung
BBOX_TL_IGNORE_PX = 6           # [FILTER] Bỏ điểm quá gần góc trên-trái của bbox

# --- CẤU HÌNH BẢO TOÀN TAY PHẢI KHI GIƠ CAO ---
RIGHT_ARM_HOLD_FRAMES = 2       # Giữ tạm keypoint khuỷu/cổ tay phải khi mất điểm ngắn hạn
RIGHT_ARM_CONF_FLOOR = 0.18     # Ngưỡng conf tối thiểu để kích hoạt cơ chế giữ tay phải

# --- CẤU HÌNH BẢO TOÀN TAY TRÁI KHI GIƠ CAO ---
LEFT_ARM_HOLD_FRAMES = 2        # Giữ tạm keypoint khuỷu/cổ tay trái khi mất điểm ngắn hạn
LEFT_ARM_CONF_FLOOR = 0.18      # Ngưỡng conf tối thiểu để kích hoạt cơ chế giữ tay trái

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
