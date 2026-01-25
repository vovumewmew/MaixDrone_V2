# config.py

# --- CẤU HÌNH MẠNG ---
HOST = "0.0.0.0"
PORT = 80
TIMEOUT = 3.0

# --- CẤU HÌNH CAMERA (CHẾ ĐỘ HD) ---
CAM_WIDTH = 320     # Chiều rộng (Width)
CAM_HEIGHT = 240    # Chiều cao (Height)
JPEG_QUALITY = 25   
FPS_LIMIT = 30      

# --- CẤU HÌNH AI ---
ENABLE_AI = True   
MODEL_PATH = "/root/models/yolo11n_pose.mud"        # Hỗ trợ đuôi .mud (ưu tiên) hoặc .cvimodel

# Ngưỡng tin cậy cho Detect (thường Detect nhạy hơn nên để cao chút cho chắc)
CONF_THRESHOLD = 0.5 # [STANDARD] Tăng lên mức chuẩn để khung bao ổn định
KEYPOINT_THRESHOLD = 0.0 # [RAW] Lấy tất cả điểm AI trả về (Trust AI)

# --- CẤU HÌNH BỘ LỌC (FILTERING & POST-PROCESSING) ---
POSE_CONF_THRESHOLD = 0.0       # [RAW] Không lọc điểm yếu
STICKY_DEADZONE = 0.0           # [RAW] Tắt chống rung