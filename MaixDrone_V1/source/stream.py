# source/stream.py
import socket
import time
import select # [NEW] Dùng để kiểm tra kết nối không chặn (Non-blocking)

class StreamServer:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.conn = None
        
    def start(self):
        """Khởi tạo Socket Server (Có cơ chế thử lại nếu cổng bị kẹt)"""
        while True:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind((self.host, self.port))
                self.sock.listen(1)
                
                print(f"📡 Video Stream: http://{self.host}:{self.port}/stream")
                break
            except Exception as e:
                print(f"⚠️ Cổng mạng đang bận ({e}), thử lại sau 2s...")
                time.sleep(2)

    def wait_for_client(self):
        """Chờ kết nối và xử lý HTTP Request (Dashboard hoặc Stream)"""
        while True:
            try:
                self.close_client()
                print("⏳ Đang chờ kết nối...")
                conn, addr = self.sock.accept()
                conn.settimeout(self.timeout)
                
                # Đọc Header để biết trình duyệt muốn gì
                request = conn.recv(1024).decode('utf-8', errors='ignore')
                
                # [ROUTER] Phân loại yêu cầu
                if "GET /stream" in request:
                    # Yêu cầu luồng Video -> Chấp nhận và giữ kết nối
                    print(f"🔗 Stream Connected: {addr}")
                    conn.sendall(b"HTTP/1.1 200 OK\r\n"
                                 b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n")
                    self.conn = conn
                    return True
                
                else:
                    # [UPDATE] Bỏ HTML Dashboard, trả về thông báo text đơn giản
                    response = (b"HTTP/1.1 200 OK\r\n"
                                b"Content-Type: text/plain\r\n\r\n"
                                b"MaixDrone Video Streamer Ready.")
                    conn.sendall(response)
                    conn.close() # Đóng ngay để trình duyệt gọi tiếp /stream
                    
            except Exception as e:
                print(f"⚠️ Lỗi kết nối: {e}")
                return False

    def check_new_client(self):
        """[NEW] Kiểm tra kết nối mới (Non-blocking) dùng cho main.py"""
        try:
            # Kiểm tra xem có ai đang gọi cổng 80 không?
            readable, _, _ = select.select([self.sock], [], [], 0)
            if readable:
                conn, addr = self.sock.accept()
                conn.settimeout(self.timeout)
                request = conn.recv(1024).decode('utf-8', errors='ignore')
                
                if "GET /stream" in request:
                    print(f"🔗 Stream Connected: {addr}")
                    conn.sendall(b"HTTP/1.1 200 OK\r\n"
                                 b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n")
                    self.close_client() # Đóng kết nối cũ (chỉ hỗ trợ 1 client stream)
                    self.conn = conn
                else:
                    # [UPDATE] Bỏ HTML Dashboard
                    response = (b"HTTP/1.1 200 OK\r\n"
                                b"Content-Type: text/plain\r\n\r\n"
                                b"MaixDrone Video Streamer Ready.")
                    conn.sendall(response)
                    conn.close()
        except Exception as e:
            pass # Không in lỗi để tránh spam terminal

    def send_frame(self, img_obj, quality):
        """Nén và gửi ảnh (Bắt lỗi kỹ càng)"""

        if not self.conn: return False
        
        try:
            # Nén ảnh
            jpg_bytes = img_obj.to_jpeg(quality=quality).to_bytes()
            
            # Gửi Header + Data
            # Gộp chung thành 1 gói tin lớn để giảm số lần gọi lệnh send -> Ổn định hơn
            packet = (b"--frame\r\n"
                      b"Content-Type: image/jpeg\r\n"
                      b"Content-Length: " + str(len(jpg_bytes)).encode() + b"\r\n\r\n" + 
                      jpg_bytes + b"\r\n")
            
            self.conn.sendall(packet)
            return True
            
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            print("👋 Client ngắt kết nối hoặc mạng quá yếu.")
            return False
        except Exception as e:
            print(f"⚠️ Lỗi gửi frame: {e}")
            return False

    def close_client(self):
        if self.conn:
            try: 
                self.conn.shutdown(socket.SHUT_RDWR)
                self.conn.close()
            except: pass
            self.conn = None

class MessageServer:
    """Server riêng để gửi thông báo Text qua cổng 8888"""
    def __init__(self, port=8888):
        self.port = port
        self.sock = None
        self.client = None
    
    def start(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('0.0.0.0', self.port))
            self.sock.listen(1)
            self.sock.setblocking(False) # Non-blocking
            print(f"💬 Message Server đang chạy tại Port {self.port}")
        except Exception as e:
            print(f"❌ Lỗi khởi tạo Message Server: {e}")

    def check_client(self):
        """Kiểm tra xem máy tính có kết nối vào không"""
        if not self.sock: return
        try:
            readable, _, _ = select.select([self.sock], [], [], 0)
            if readable:
                conn, addr = self.sock.accept()
                print(f"🔗 Máy tính đã kết nối nhận tin nhắn: {addr}")
                conn.settimeout(0.05) # [FIX] Timeout gửi cực ngắn (50ms) để không làm treo Drone
                if self.client: 
                    try: self.client.close()
                    except: pass
                self.client = conn
        except: pass

    def send(self, msg):
        """Gửi tin nhắn xuống máy tính"""
        if not self.client: return
        try:
            # Gửi kèm ký tự xuống dòng để bên nhận biết hết câu
            data = (str(msg) + "\n").encode('utf-8')
            self.client.sendall(data)
        except socket.timeout:
            pass # [FIX] Nếu máy tính bận đọc không nhận kịp -> Bỏ qua, không chờ
        except:
            print("👋 Máy tính đã ngắt kết nối tin nhắn.")
            self.client = None