# main.py
import time
import gc
import config
from source.camera import CameraManager
from source.stream import StreamServer
from source.ai import AIEngine
from source.ui import HUD
from source.tracker import ObjectTracker # Tracker mới

def main():
    print("--- 🚁 MAIX DRONE V12: SINGLE-STAGE FAST TRACKING ---")
    
    cam_mgr = CameraManager(config.CAM_WIDTH, config.CAM_HEIGHT)
    streamer = StreamServer(config.HOST, config.PORT, config.TIMEOUT)
    ai_engine = AIEngine(config.MODEL_PATH, config.CONF_THRESHOLD)
    hud = HUD(config.CAM_WIDTH, config.CAM_HEIGHT)
    tracker = ObjectTracker()
    
    cam_mgr.start()
    streamer.start()
    
    # [CÂN BẰNG] Để Tracker làm mượt chuyển động giữa các lần AI chạy
    SKIP_FRAMES = 2
    
    if config.ENABLE_AI:
        if not ai_engine.load():
            config.ENABLE_AI = False

    while True:
        if streamer.wait_for_client():
            frame_cnt = 0
            current_results = []
            t_last = time.time()
            fps_show = 0
            
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

                # --- LOGIC HYBRID ---
                if config.ENABLE_AI:
                    if frame_cnt % (SKIP_FRAMES + 1) == 0:
                        # [QUAY VỀ LOGIC CŨ] Chạy AI 1 lần duy nhất trên toàn ảnh
                        # Nhanh, Mượt, Ổn định. Tracker sẽ lo phần làm mịn.
                        _, ai_results = ai_engine.process(img)
                        
                        # Cập nhật Tracker (Tracker đã có sẵn EMA + Momentum để làm mượt)
                        current_results = tracker.update(ai_results)
                    else:
                        # Frame phụ: Tracker tự đoán
                        current_results = tracker.predict()

                hud.draw_fps(img, fps_show)
                if config.ENABLE_AI:
                    hud.draw_ai_result(img, current_results)

                success = streamer.send_frame(img, config.JPEG_QUALITY)
                if not success: break 
                
                frame_cnt += 1
                if frame_cnt % 30 == 0: gc.collect()
            
            streamer.close_client()
            print("🔄 Reset...")

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: print("\n🛑 Stop.")