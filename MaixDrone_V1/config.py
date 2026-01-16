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

# --- CẤU HÌNH BỘ LỌC (FILTERING & POST-PROCESSING) ---
# Đây là các tham số quan trọng để cân bằng giữa việc "lọc nhiễu" và "giữ lại điểm".
# Tinh chỉnh các giá trị này nếu bạn thấy các điểm bị mất hoặc bị "ma".

# 1. Ngưỡng tin cậy tối thiểu cho một điểm (keypoint) được chấp nhận.
#    - Giá trị cao (vd: 0.6) -> Rất khắt khe, chỉ giữ lại điểm cực kỳ chắc chắn, nhưng có thể mất điểm tay/chân.
#    - Giá trị thấp (vd: 0.25) -> Dễ dãi, giữ lại nhiều điểm hơn, nhưng có thể bị nhiễu (điểm ma).
POSE_CONF_THRESHOLD = 0.2

# 2. Ngưỡng tin cậy tối thiểu khi điểm nằm gần mép của hộp phát hiện (bounding box).
#    Điểm ở gần mép thường dễ bị sai, nên ta đòi hỏi độ tin cậy cao hơn ở khu vực này.
EDGE_CONF_THRESHOLD = 0.80

# 3. Số lượng điểm tối thiểu phải nhìn thấy để coi là một bộ xương hợp lệ.
#    Giúp loại bỏ các trường hợp AI "nhìn nhầm" một vết bẩn trên tường thành người.
MIN_VALID_KEYPOINTS = 5

# 4. Dung sai cho bộ lọc Cinematic (nắn xương).
#    Giá trị này cho phép chiều dài của xương có thể sai lệch một chút so với tỷ lệ chuẩn.
#    - Giá trị nhỏ (vd: 0.15) -> Siết chặt, xương phải gần như đúng tỷ lệ.
#    - Giá trị lớn (vd: 0.3) -> Nới lỏng, cho phép tay/chân co duỗi nhiều hơn.
KINEMATIC_TOLERANCE = 0.25

# 5. Ngưỡng xóa điểm bất thường trong bộ lọc Cinematic.
#    Nếu một điểm bị lệch quá nhiều (chiều dài xương sai quá lớn), nó sẽ bị xóa.
#    Giá trị này là một hệ số nhân với `max_len` (chiều dài xương tối đa cho phép).
#    - Giá trị nhỏ (vd: 1.5) -> Dễ xóa điểm sai hơn.
#    - Giá trị lớn (vd: 2.0) -> Ít xóa hơn, giữ lại nhiều điểm hơn.
KINEMATIC_DELETION_MULTIPLIER = 1.3