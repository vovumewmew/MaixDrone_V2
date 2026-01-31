import socket
import time
import sys

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
DRONE_IP = '10.89.70.1' 
MSG_PORT = 8888

def main():
    print(f"🔌 Đang kết nối tới Server (Local) tại {DRONE_IP}:{MSG_PORT}...")
    
    try:
        # Tạo Socket TCP
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2) # Timeout kết nối
        client.connect((DRONE_IP, MSG_PORT))
        
        print("✅ Đã kết nối thành công! Đang chờ thông báo...")
        
        # Loop nhận dữ liệu
        client.settimeout(0.1) # [IMPORTANT] Timeout ngắn để vòng lặp chạy liên tục (check timer)
        current_msg = None
        last_speak_time = 0
        
        while True:
            try:
                # Nhận dữ liệu (tối đa 1024 bytes)
                # [FIX] Tăng buffer lên 4096 để đọc sạch dữ liệu tồn đọng
                data = client.recv(4096)
                if not data:
                    print("⚠️ Server đã đóng kết nối.")
                    break
                
                # [FIX] Lấy tin nhắn mới nhất trong buffer (nếu có nhiều dòng)
                raw_text = data.decode('utf-8', errors='ignore').strip()
                if not raw_text: continue # Bỏ qua nếu chỉ nhận được khoảng trắng
                
                lines = raw_text.split('\n')
                msg = lines[-1].strip()
                
                # [LOGIC] Cập nhật trạng thái hiện tại
                if msg == "None":
                    if current_msg is not None:
                        print("🛑 Đã dừng hành động (Nhận tín hiệu None).")
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
                    print(f"[DEBUG] 🕒 Kích hoạt đọc lại (Trễ: {time_diff:.2f}s)")
                    try:
                        # [FIX] Luôn khởi tạo mới engine mỗi lần đọc để tránh lỗi "chỉ đọc 1 lần"
                        print("[DEBUG] ⚙️ Đang khởi tạo Engine tạm thời...")
                        temp_engine = pyttsx3.init()
                        temp_engine.setProperty('rate', 150)
                            
                        print(f"[DEBUG] 🗣️ Bắt đầu đọc: '{current_msg}'")
                        temp_engine.say(current_msg)
                        print("[DEBUG] ▶️ Đang chạy runAndWait...")
                        temp_engine.runAndWait()
                        temp_engine.stop()
                        del temp_engine # Giải phóng tài nguyên
                        print("[DEBUG] ✅ Đã đọc xong.")
                    except Exception as e:
                        print(f"[DEBUG] ❌ Lỗi nghiêm trọng khi đọc: {e}")
                    
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
