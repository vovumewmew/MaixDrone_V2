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
CONF_THRESHOLD = 0.4 # [TUNING] Hạ xuống chút để bắt người dễ hơn
KEYPOINT_THRESHOLD = 0.10 # [TRUST AI] Hạ xuống 0.10 để bắt mọi điểm có thể

# --- CẤU HÌNH BỘ LỌC (FILTERING & POST-PROCESSING) ---
POSE_CONF_THRESHOLD = 0.10      # [TRUST AI] Hạ thấp ngưỡng lọc đầu ra
STICKY_DEADZONE = 2.0           # [ACCURACY] Giảm Deadzone để bắt được chuyển động nhỏ