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
MODEL_PATH = "/root/models/yolov8n_pose.mud"        # 1 Model duy nhất (Vừa Detect vừa Pose)

# Ngưỡng tin cậy cho Detect (thường Detect nhạy hơn nên để cao chút cho chắc)
CONF_THRESHOLD = 0.4 # [TUNING] Hạ xuống chút để bắt người dễ hơn

# --- CẤU HÌNH BỘ LỌC (FILTERING & POST-PROCESSING) ---
POSE_CONF_THRESHOLD = 0.15      # [LOW] Hạ thấp để bắt được các điểm mờ (tay/chân)
EDGE_CONF_THRESHOLD = 0.10      # Ngưỡng tin cậy cho điểm ở mép ảnh
MIN_VALID_KEYPOINTS = 5         # Số điểm tối thiểu để coi là người
MAX_KPT_JUMP_RATIO = 0.3        # Tỷ lệ nhảy tối đa (chống teleport)
KINEMATIC_TOLERANCE = 0.2       # Dung sai độ dài xương
KINEMATIC_DELETION_MULTIPLIER = 1.3 # Hệ số xóa điểm sai lệch