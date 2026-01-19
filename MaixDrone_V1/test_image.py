import os
import time
from maix import image
import config
from source.ai import AIEngine
from source.ui import HUD

def test_static_images(input_dir, output_dir):
    # 1. Khởi tạo thư mục output
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    print(f"📂 Input: {input_dir}")
    print(f"💾 Output: {output_dir}")

    # 2. Load AI Engine
    # Lưu ý: Config phải trỏ đúng model path
    ai_engine = AIEngine(config.MODEL_PATH, config.CONF_THRESHOLD)
    if not ai_engine.load():
        print("❌ Failed to load model.")
        return

    # 3. Load HUD để vẽ
    hud = HUD(config.CAM_WIDTH, config.CAM_HEIGHT)

    # 4. Lấy danh sách file ảnh
    if not os.path.exists(input_dir):
        print(f"❌ Input directory not found: {input_dir}")
        return
        
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.jfif'))]
    
    if not files:
        print("⚠️ No images found!")
        return

    print(f"🚀 Found {len(files)} images. Processing...")

    for fname in files:
        fpath = os.path.join(input_dir, fname)
        
        try:
            # Đọc ảnh
            img = image.load(fpath)
            print(f"   ℹ️ Size: {img.width()}x{img.height()}")
            
            # Chạy AI (Logic mapping mới nhất trong source/ai.py sẽ được dùng)
            _, results = ai_engine.process(img)
            
            # Chuyển đổi định dạng để HUD vẽ được
            display_objects = []
            for i, res in enumerate(results):
                box = [res['x'], res['y'], res['w'], res['h']]

                display_objects.append({
                    'id': i + 1,
                    'box': box,
                    'score': res['score'],
                })
            
            # Vẽ kết quả
            hud.draw_ai_result(img, display_objects)
            
            # Lưu ảnh
            # [OPTIONAL] Ép đuôi file về .jpg để chuẩn hóa đầu ra
            fname_no_ext = os.path.splitext(fname)[0]
            out_path = os.path.join(output_dir, f"out_{fname_no_ext}.jpg")
            img.save(out_path)
            print(f"✅ Processed: {fname} -> {len(results)} pose(s)")
            
        except Exception as e:
            print(f"❌ Error processing {fname}: {e}")

if __name__ == "__main__":
    # Đường dẫn mặc định
    INPUT_DIR = "/root/MaixDrone_V1/test_pose"
    OUTPUT_DIR = "/root/MaixDrone_V1/output_images"
    
    test_static_images(INPUT_DIR, OUTPUT_DIR)