# config.py

# --- CẤU HÌNH MẠNG ---
HOST = "0.0.0.0"
PORT = 80
TIMEOUT = 3.0

# --- CẤU HÌNH CAMERA (CHẾ ĐỘ HD) ---
CAM_WIDTH = 640     # <--- Tăng lên 640 (Nét hơn)
CAM_HEIGHT = 480    # <--- Tăng lên 480
JPEG_QUALITY = 25   
FPS_LIMIT = 30      

# --- CẤU HÌNH AI ---
ENABLE_AI = True   
MODEL_PATH = "/root/models/yolov8n_pose.mud"        # 1 Model duy nhất (Vừa Detect vừa Pose)

# Ngưỡng tin cậy cho Detect (thường Detect nhạy hơn nên để cao chút cho chắc)
CONF_THRESHOLD = 0.5