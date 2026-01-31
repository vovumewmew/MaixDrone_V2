# main.py
import time
import gc
import sys      # [NEW] Để đọc dữ liệu từ Serial (stdin)
import select   # [NEW] Để kiểm tra dữ liệu không chặn (Non-blocking)
import config
from maix import display # [NEW] Chạy trực tiếp trên MaixVision
from source.camera import CameraManager
from source.ai import AIEngine
from source.stream import StreamServer, MessageServer # [UPDATE] Import thêm MessageServer
from source.ui import HUD
from source.tracker import ObjectTracker

def main():
    print("--- 🚁 MAIX DRONE V12: NETWORK MODE (LCD + SOCKET) ---")
    
    cam_mgr = CameraManager(config.CAM_WIDTH, config.CAM_HEIGHT)
    disp = display.Display() # [FIX] Khởi tạo đối tượng Display
    
    # [UPDATE] Khởi tạo StreamServer để hỗ trợ Web Dashboard
    streamer = StreamServer(config.HOST, config.PORT, config.TIMEOUT)
    # [NEW] Khởi tạo Server tin nhắn (Port 8888)
    msg_server = MessageServer(8888)
    
    ai_engine = AIEngine(config.MODEL_PATH, config.CONF_THRESHOLD)
    hud = HUD(config.CAM_WIDTH, config.CAM_HEIGHT)
    tracker = ObjectTracker()
    
    cam_mgr.start()
    streamer.start() # [UPDATE] Bắt đầu lắng nghe kết nối Web
    msg_server.start() # [NEW] Bắt đầu lắng nghe máy tính
    
    SKIP_FRAMES = 3
    
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
            if frame_cnt % (SKIP_FRAMES + 1) == 0:
                _, ai_results = ai_engine.process(img)
                current_results = tracker.update(ai_results)
            else:
                current_results = tracker.predict()

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