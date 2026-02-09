import socket
import datetime # [NEW]

# --- CẤU HÌNH ---
HOST = '0.0.0.0'  # Lắng nghe mọi IP
PORT = 9999       # Phải trùng với TINKER_PORT trong config.py của MaixCam

def main():
    print(f"--- 🎧 TINKERBOARD SIMPLE MONITOR (Port {PORT}) ---")
    
    # Khởi tạo Server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((HOST, PORT))
        server.listen(1)
        print(f"Đang chờ tín hiệu từ MaixCam...")
    except Exception as e:
        print(f"Lỗi khởi tạo: {e}")
        return

    try:
        while True:
            conn, addr = server.accept()
            print(f"\nKẾT NỐI MỚI: {addr}")
            
            with conn:
                while True:
                    data = conn.recv(4096)
                    if not data: break
                    # In ngay lập tức mọi thứ nhận được ra màn hình
                    
                    # [NEW] Xử lý yêu cầu đồng bộ thời gian từ MaixCam
                    msg_raw = data.decode('utf-8').strip()
                    if msg_raw == "SYNC_REQ":
                        now_ts = datetime.datetime.now().timestamp()
                        conn.sendall(f"SYNC_TIME:{now_ts}".encode('utf-8'))
                        print(f"Đã gửi thời gian đồng bộ cho MaixCam: {now_ts}")
                        continue

                    # [UPDATE] Thêm thời gian nhận thực tế tại TinkerBoard
                    recv_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    msg = data.decode('utf-8').strip()
                    print(f"[Recv: {recv_time}] {msg}")
            
            print("Mất kết nối. Đang chờ lại...")
    except KeyboardInterrupt:
        print("\nĐã dừng Server (User Interrupt).")
    finally:
        server.close()

if __name__ == "__main__":
    main()