# config.py

# --- CẤU HÌNH MẠNG ---
HOST = "0.0.0.0"
PORT = 80
TIMEOUT = 3.0

# --- CẤU HÌNH CAMERA (CHẾ ĐỘ HD) ---
CAM_WIDTH = 320     # [FIX] Giảm về 320 để tránh lỗi Out of Memory (OOM)
CAM_HEIGHT = 224    # [FIX] Khớp với Input AI -> Tốc độ cao nhất, không cần Resize
JPEG_QUALITY = 25   
FPS_LIMIT = 30      

# --- CẤU HÌNH AI ---
ENABLE_AI = True   
MODEL_PATH = "/root/models/yolo11n_pose.mud"        # 1 Model duy nhất (Vừa Detect vừa Pose)

# Ngưỡng tin cậy cho Detect (thường Detect nhạy hơn nên để cao chút cho chắc)
CONF_THRESHOLD = 0.4 # [TUNING] Hạ xuống chút để bắt người dễ hơn
KEYPOINT_THRESHOLD = 0.10 # [TRUST AI] Hạ xuống 0.10 để bắt mọi điểm có thể

# --- CẤU HÌNH BỘ LỌC (FILTERING & POST-PROCESSING) ---
POSE_CONF_THRESHOLD = 0.10      # [TRUST AI] Hạ thấp ngưỡng lọc đầu ra