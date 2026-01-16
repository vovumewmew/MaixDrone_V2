# source/stream.py
import socket
import time

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
                print(f"📡 Server đang chạy tại: http://10.89.70.1:{self.port}")
                break
            except Exception as e:
                print(f"⚠️ Cổng mạng đang bận ({e}), thử lại sau 2s...")
                time.sleep(2)

    def wait_for_client(self):
        """Chờ kết nối từ trình duyệt"""
        try:
            # Nếu đã có kết nối cũ chưa đóng sạch, đóng nó đi
            self.close_client()
            
            print("⏳ Đang chờ kết nối...")
            self.conn, addr = self.sock.accept()
            self.conn.settimeout(self.timeout)
            print(f"🔗 Đã kết nối: {addr}")
            
            self.conn.sendall(b"HTTP/1.1 200 OK\r\n"
                              b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n")
            return True
        except Exception as e:
            # print(f"⚠️ Lỗi chờ kết nối: {e}") 
            return False

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