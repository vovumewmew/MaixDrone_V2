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