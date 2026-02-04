import socket
import time
import sys
import os
import base64
from datetime import datetime

try:
    import pyttsx3 # [UPDATE] Thư viện chuyển văn bản thành giọng nói
except ImportError:
    print(f"❌ Lỗi: Không tìm thấy thư viện 'pyttsx3'.")
    print(f"ℹ️  Bạn đang chạy Python tại: {sys.executable}")
    print("💡 Gợi ý: Hãy dùng lệnh 'py' thay vì 'python' để chạy script này.")
    sys.exit(1)

# --- CẤU HÌNH ---
# IP mặc định của MaixCam khi cắm USB (RNDIS) thường là 10.89.70.1
# Nếu không được, hãy thử 192.168.2.1 hoặc kiểm tra IP trên màn hình Drone
DRONE_IP = '10.89.70.1' # [LƯU Ý] Thay đổi IP này nếu bạn dùng Wifi (VD: 192.168.1.x)
MSG_PORT = 8888

# [NEW] Tạo thư mục lưu ảnh nếu chưa có
SAVE_DIR = "captured_images"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

def main():
    print(f"🔌 Đang kết nối tới Server (Local) tại {DRONE_IP}:{MSG_PORT}...")
    
    try:
        # Tạo Socket TCP
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2) # Timeout kết nối
        client.connect((DRONE_IP, MSG_PORT))
        
        print(f"✅ Đã kết nối tới {DRONE_IP}! Đang chờ tín hiệu từ Drone...")
        
        # Loop nhận dữ liệu
        client.settimeout(0.1) # [IMPORTANT] Timeout ngắn để vòng lặp chạy liên tục (check timer)
        current_msg = None
        last_speak_time = 0
        buffer = "" # [NEW] Bộ đệm để ghép nối dữ liệu bị cắt
        
        while True:
            try:
                # Nhận dữ liệu (tối đa 1024 bytes)
                # [FIX] Tăng buffer lên 4096 để đọc sạch dữ liệu tồn đọng
                data = client.recv(4096)
                if not data:
                    print("⚠️ Server đã đóng kết nối.")
                    break
                
                # [BUFFER LOGIC] Ghép dữ liệu mới vào bộ đệm
                raw_chunk = data.decode('utf-8', errors='ignore')
                buffer += raw_chunk
                
                # Xử lý từng dòng lệnh (phân tách bởi \n)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    msg = line.strip()
                    if not msg: continue

                    # [IMAGE HANDLER] Nếu là dữ liệu ảnh
                    if msg.startswith("IMG:"):
                        try:
                            b64_data = msg[4:] # Cắt bỏ tiền tố "IMG:"
                            img_data = base64.b64decode(b64_data)
                            
                            # Tạo tên file theo thời gian
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            filename = f"{SAVE_DIR}/alert_{timestamp}.jpg"
                            
                            with open(filename, "wb") as f:
                                f.write(img_data)
                            print(f"📸 Đã lưu ảnh bằng chứng: {filename}")
                        except Exception as e:
                            print(f"❌ Lỗi lưu ảnh: {e}")
                        continue # Xử lý xong ảnh thì bỏ qua logic đọc loa bên dưới
                    
                    # [LOGIC] Cập nhật trạng thái hiện tại (Di chuyển vào trong vòng lặp)
                    # Để đảm bảo chỉ xử lý khi không phải là ảnh
                    if msg == "None":
                        if current_msg is not None:
                            print("🛑 Đã dừng hành động.")
                        current_msg = None
                    elif msg != current_msg:
                        # Chỉ in và reset timer nếu thông báo KHÁC với hiện tại
                        print(f"📥 CẢNH BÁO MỚI: {msg}")
                        current_msg = msg
                        last_speak_time = 0 # Reset để đọc ngay lập tức
                
            except (socket.timeout, TimeoutError):
                pass # Hết 0.1s mà không có tin mới -> Chạy tiếp xuống dưới để check timer
            except Exception as e:
                print(f"❌ Lỗi nhận dữ liệu: {e}")
                break
            
            # [SPEECH] Kiểm tra timer để đọc lặp lại mỗi 1 giây
            if current_msg:
                time_diff = time.time() - last_speak_time
                if time_diff > 1.0:
                    try:
                        # [SIMPLE] Khởi tạo và đọc trực tiếp (Blocking nhưng ổn định)
                        engine = pyttsx3.init()
                        engine.setProperty('rate', 150)
                        engine.say(current_msg)
                        engine.runAndWait()
                        engine.stop()
                        del engine
                    except Exception: pass
                    last_speak_time = time.time()
    
    except KeyboardInterrupt:
        print("\n🛑 Đã dừng chương trình (User Interrupt).")
        
    except Exception as e:
        print(f"⏳ Không thể kết nối ({e}). Thử lại sau 2s...")
        time.sleep(2)
        
    finally:
        try: client.close()
        except: pass

if __name__ == "__main__":
    main()
