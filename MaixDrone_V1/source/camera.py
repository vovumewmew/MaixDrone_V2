# source/camera.py
from maix import camera, image
import time
import sys

class CameraManager:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.cam = None
        
    def start(self):
        try:
            print("📷 Đang khởi động Camera...")
            # [QUAN TRỌNG] Ép kiểu ảnh về RGB888 để hiển thị đúng màu sắc (Hồng, Xanh...)
            self.cam = camera.Camera(self.width, self.height, image.Format.FMT_RGB888)
            
            # --- [NEW] CẤU HÌNH ISP CHỐNG CHÁY SÁNG (ANTI-WASHOUT) ---
            print("📸 Configuring Camera ISP for high-contrast environment...")
            try:
                # 1. Hạ độ sáng tổng thể (Trị số thường từ -2 đến 2, mặc định 0)
                # Hạ xuống số âm để các mảng trắng của trần nhà/đèn bớt chói lóa
                if hasattr(self.cam, 'set_brightness'):
                    self.cam.set_brightness(-1)

                # 2. Tăng độ tương phản (Trị số thường từ -2 đến 2, mặc định 0)
                # Giúp viền cánh tay tách biệt rõ ràng hơn so với phông nền
                if hasattr(self.cam, 'set_contrast'):
                    self.cam.set_contrast(1)
                # 3. [Nâng cao] Khóa phơi sáng (Nếu API của MaixPy version bạn hỗ trợ)
                # Tắt Auto Exposure và ép phơi sáng ở mức thấp
                # if hasattr(self.cam, 'set_auto_exposure'):
                #     self.cam.set_auto_exposure(False)
                # if hasattr(self.cam, 'set_exposure'):
                #     self.cam.set_exposure(500) # Đơn vị micro-giây, cần chỉnh tay theo môi trường
            except Exception as e:
                print(f"⚠️ Không thể cấu hình ISP: {e}. Vui lòng kiểm tra version MaixPy.")

            # Đọc bỏ 5 frame đầu để camera ổn định ánh sáng
            for _ in range(5):
                self.cam.read()
            print("✅ Camera đã sẵn sàng!")
        except Exception as e:
            print(f"❌ Lỗi Camera: {e}")
            sys.exit()

    def get_frame(self):
        """Trả về đối tượng ảnh gốc"""
        if self.cam:
            img = self.cam.read()
            if img:
                # Ảnh đã là RGB888 do cấu hình lúc init, trả về luôn (không convert lại để tránh lỗi)
                return img
        return None
    
    def close(self):
        # Maix tự quản lý resource, nhưng hàm này để giữ cấu trúc chuẩn
        print("📷 Đã đóng Camera.")