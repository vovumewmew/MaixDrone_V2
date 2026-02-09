import socket
import time
import datetime # [NEW] Để lấy giờ hiện tại
import os       # [NEW] Để chạy lệnh set giờ hệ thống

class TinkerClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None
        self.last_connect_time = 0
        self.connect_cooldown = 3.0 # Thử lại sau mỗi 3s nếu mất kết nối
        self.last_send_time = 0     # [NEW] Biến lưu thời gian gửi tin cuối cùng

    def connect(self):
        """Thiết lập kết nối Socket"""
        if self.sock: return True
        
        # Tránh spam kết nối liên tục gây lag
        if time.time() - self.last_connect_time < self.connect_cooldown:
            return False

        self.last_connect_time = time.time()
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(0.1) # Non-blocking connect (quan trọng để không treo Drone)
            self.sock.connect((self.host, self.port))
            print(f"✅ [TinkerClient] Connected to {self.host}:{self.port}")
            
            # [NEW] Đồng bộ thời gian ngay khi kết nối thành công
            self.sync_clock()
            
            return True
        except Exception as e:
            print(f"⚠️ [TinkerClient] Connect failed: {e}") # [DEBUG] Bật lên để xem lỗi
            self.sock = None
            return False

    def sync_clock(self):
        """Hỏi giờ từ TinkerBoard và cập nhật cho MaixCam"""
        try:
            self.sock.sendall(b"SYNC_REQ")
            # Tăng timeout tạm thời để chờ phản hồi
            self.sock.settimeout(1.0)
            data = self.sock.recv(1024)
            self.sock.settimeout(0.1) # Trả về timeout ngắn
            
            msg = data.decode('utf-8').strip()
            if msg.startswith("SYNC_TIME:"):
                ts = float(msg.split(":")[1])
                # Format lệnh date của Linux: date -s "YYYY-MM-DD HH:MM:SS"
                dt_str = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                print(f"⏰ Syncing system time to: {dt_str}")
                os.system(f'date -s "{dt_str}"')
        except Exception as e:
            print(f"⚠️ Time sync failed: {e}")
            # Reset timeout nếu lỗi
            if self.sock: self.sock.settimeout(0.1)

    def send_pose(self, objects):
        # Tự động kết nối nếu chưa có
        if not self.sock:
            if not self.connect(): return

        # [UPDATE] Rate Limit: Chỉ gửi 1 lần mỗi giây (Delay 1s)
        if time.time() - self.last_send_time < 1.0:
            return

        # [UPDATE] Chỉ gửi các thông báo đặc biệt (Special Notifications)
        messages = []
        for obj in objects:
            gestures = obj.get('gestures', [])
            
            # Mapping cử chỉ sang thông báo đặc biệt (giống logic trong ui.py)
            special_msg = None
            if "Cheo Tay Tren Dau" in gestures:
                special_msg = "EMERGENCY STOP"
            elif "Vay Tay Phai" in gestures:
                special_msg = "URGENT ATTENTION"
            elif "Trai Cao" in gestures:
                special_msg = "SHORTAGE OF MATERIAL"
            elif "Phai Cao" in gestures:
                special_msg = "TECHNICAL OR QUALITY ISSUE"
            
            if special_msg:
                # [UPDATE] Thêm thời gian gửi từ MaixCam (Send Time)
                # Format: [HH:MM:SS.ms] ACTION: Message
                timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                messages.append(f"[{timestamp}] ACTION: {special_msg}")

        if not messages: return # Không có thông báo đặc biệt thì không gửi

        try:
            # Gửi các dòng thông báo, ngăn cách bằng xuống dòng
            msg = "\n".join(messages) + "\n"
            self.sock.sendall(msg.encode('utf-8'))
            
            # [UPDATE] Cập nhật thời gian gửi và in ra Terminal MaixCam
            self.last_send_time = time.time()
            print(f"[MaixCam Sent] {msg.strip()}")
        except Exception as e:
            print(f"[TinkerClient] Send error: {e}")
            self.close()

    def close(self):
        if self.sock:
            try: self.sock.close()
            except: pass
            self.sock = None