# main.py
import time
import gc
import os       # [NEW] Để chạy lệnh hệ thống (Wifi)
import sys      # [NEW] Để đọc dữ liệu từ Serial (stdin)
import select   # [NEW] Để kiểm tra dữ liệu không chặn (Non-blocking)
import config
from maix import display, image # [UPDATE] Import thêm image để load font
from source.camera import CameraManager
from source.ai import AIEngine
from source.stream import StreamServer, MessageServer # [UPDATE] Import thêm MessageServer
from source.ui import HUD
from source.tracker import ObjectTracker
from source.tinker_client import TinkerClient # [NEW] Import Client gửi tin

def connect_wifi_linux(ssid, password):
    """Hàm tự động kết nối Wifi cho Linux nhúng (MaixCam)"""
    # [OPTIMIZE] Kiểm tra nhanh: Nếu đã có IP thì không cần kết nối lại (tiết kiệm 5s khởi động)
    try:
        # ifconfig wlan0 thường chứa dòng "inet addr:10.x.x.x" hoặc "inet 10.x.x.x"
        if_status = os.popen("ifconfig wlan0").read()
        if "inet " in if_status:
            print(f"✅ Wifi đã có IP (Sẵn sàng). Bỏ qua bước kết nối lại.")
            return
    except Exception:
        pass # Nếu lỗi thì cứ chạy kết nối bình thường

    print(f"📶 Auto Connecting to Wifi: {ssid}...")
    # 1. Tạo file cấu hình
    conf_content = f'ctrl_interface=/var/run/wpa_supplicant\nupdate_config=1\n\nnetwork={{\n    ssid="{ssid}"\n    psk="{password}"\n}}\n'
    os.system(f"echo '{conf_content}' > /etc/wpa_supplicant.conf")
    
    # 2. Khởi động lại tiến trình Wifi
    os.system("killall wpa_supplicant 2> /dev/null")
    os.system("ifconfig wlan0 down && ifconfig wlan0 up")
    time.sleep(1)
    os.system("wpa_supplicant -B -i wlan0 -c /etc/wpa_supplicant.conf")
    time.sleep(2) # Chờ kết nối
    os.system("udhcpc -i wlan0") # Xin IP
    print("✅ Wifi setup done.")

def main():
    print("--- 🚁 MAIX DRONE V12: NETWORK MODE (LCD + SOCKET) ---")
    print("⚡ MODE: REAL-TIME FULL PROCESSING (EVERY FRAME)")
    
    # [AUTO WIFI] Tự động kết nối mạng Lab khi chạy chương trình
    connect_wifi_linux(config.WIFI_SSID, config.WIFI_PASS)
    
    # Dùng font mặc định (nhanh nhất)
    image.set_default_font("sourcehansans")

    cam_mgr = CameraManager(config.CAM_WIDTH, config.CAM_HEIGHT)
    disp = display.Display() # [FIX] Khởi tạo đối tượng Display
    
    # [UPDATE] Khởi tạo StreamServer để hỗ trợ Web Dashboard
    streamer = StreamServer(config.HOST, config.PORT, config.TIMEOUT)
    # [NEW] Khởi tạo Server tin nhắn (Port 8888)
    msg_server = MessageServer(8888)
    
    # [NEW] Khởi tạo Client gửi dữ liệu sang Tinkerboard
    tinker_client = TinkerClient(config.TINKER_IP, config.TINKER_PORT)
    
    ai_engine = AIEngine(config.MODEL_PATH, config.CONF_THRESHOLD)
    hud = HUD(config.CAM_WIDTH, config.CAM_HEIGHT)
    tracker = ObjectTracker()
    
    cam_mgr.start()
    streamer.start() # [UPDATE] Bắt đầu lắng nghe kết nối Web
    msg_server.start() # [NEW] Bắt đầu lắng nghe máy tính
    
    # [TEST PERFORMANCE] Chuyển sang chế độ xử lý toàn vẹn (Full AI)
    # SKIP_FRAMES = 0 nghĩa là không bỏ frame nào, chạy AI liên tục
    SKIP_FRAMES = 0
    
    if config.ENABLE_AI:
        if not ai_engine.load():
            config.ENABLE_AI = False

    frame_cnt = 0
    t_last = time.time()
    fps_show = 0
    last_sent_msg = None # [NEW] Lưu tin nhắn cuối cùng đã gửi
    
    while True:
        img = cam_mgr.get_frame()
        if img is None:
            time.sleep(0.001)
            continue
        
        t_now = time.time()
        dt = t_now - t_last
        if dt > 0:
            fps_show = (fps_show * 0.9) + ((1.0/dt) * 0.1)
        t_last = t_now

        if config.ENABLE_AI:
            # [FULL PROCESSING] Chạy AI trên mọi khung hình
            # Loại bỏ hoàn toàn logic dự đoán (Hybrid) để đảm bảo dữ liệu thực tế nhất
            _, ai_results = ai_engine.process(img)
            current_results = tracker.update(ai_results)
            
            # [NEW] Gửi dữ liệu Pose sang Tinkerboard
            tinker_client.send_pose(current_results)

        hud.draw_fps(img, fps_show)
        if config.ENABLE_AI:
            hud.draw_ai_result(img, current_results)

        # [UPDATE] Xử lý Web Stream (Non-blocking)
        streamer.check_new_client()      # Kiểm tra xem có ai vào Web không
        streamer.send_frame(img, config.JPEG_QUALITY) # Gửi ảnh (nếu có người xem)

        # [NEW] Xử lý gửi tin nhắn qua mạng
        msg_server.check_client() # Chấp nhận kết nối từ PC
        # Kiểm tra nếu HUD có thông báo mới thì gửi đi
        if hud.last_action_msg != last_sent_msg:
            msg_server.send(hud.last_action_msg)
            
            # [CAPTURE] Nếu là cảnh báo thật (không phải None), chụp và gửi ảnh ngay
            if hud.last_action_msg is not None:
                msg_server.send_image(img)
                
            last_sent_msg = hud.last_action_msg

        # [NEW] Xử lý Lệnh từ Serial (PC gửi xuống)
        # Kiểm tra xem có dữ liệu ở cổng stdin không (timeout=0 để không chặn)
        if select.select([sys.stdin], [], [], 0)[0]:
            cmd = sys.stdin.readline().strip()
            if cmd:
                print(f"💻 PC Command: {cmd}") # Phản hồi lại để PC biết đã nhận
                
                # Xử lý lệnh
                if cmd == 'q':
                    print("🛑 Received Quit Command.")
                    break
                elif cmd == 'd': # Debug toggle
                    config.ENABLE_AI = not config.ENABLE_AI
                    print(f"🔧 AI Enabled: {config.ENABLE_AI}")

        # [MAIXVISION] Hiển thị trực tiếp
        disp.show(img) # [FIX] Dùng đối tượng disp để hiển thị
        
        frame_cnt += 1
        if frame_cnt % 30 == 0: gc.collect()

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n🛑 Stop.")
