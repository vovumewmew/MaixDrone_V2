import re
import time

import config
from maix import app, camera, display

from source.ai import AIEngine
from source.tracker import ObjectTracker
from source.tinker_client import TinkerClient
from source.ui import HUD

class CPUMeter:
    def __init__(self):
        self.prev_total = None
        self.prev_idle = None

    def read_percent(self):
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                parts = f.readline().split()
            vals = [int(x) for x in parts[1:8]]
            idle = vals[3] + vals[4]
            total = sum(vals)
        except Exception:
            return 0.0

        if self.prev_total is None:
            self.prev_total = total
            self.prev_idle = idle
            return 0.0

        d_total = total - self.prev_total
        d_idle = idle - self.prev_idle
        self.prev_total = total
        self.prev_idle = idle

        if d_total <= 0:
            return 0.0
        return max(0.0, min(100.0, (1.0 - d_idle / d_total) * 100.0))


def read_ram():
    try:
        mem = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                mem[key.strip()] = int(value.strip().split()[0])
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", 0)
        used = max(0, total - available)
        pct = (used * 100.0 / total) if total > 0 else 0.0
        return used / 1024.0, total / 1024.0, pct
    except Exception:
        return 0.0, 0.0, 0.0


class NPUMeter:
    CANDIDATE_PATHS = [
        "/sys/kernel/debug/cvi-npu/load",
        "/sys/class/devfreq/cvi-npu/load",
        "/proc/npu_usage",
        "/proc/cvitek/npu",
    ]

    def __init__(self):
        self.ema_util = 0.0

    def _read_direct_npu_util(self):
        for path in self.CANDIDATE_PATHS:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    txt = f.read()
                match = re.search(r"([0-9]+(?:\.[0-9]+)?)", txt)
                if not match:
                    continue
                value = float(match.group(1))
                if value <= 1.0:
                    value *= 100.0
                return max(0.0, min(100.0, value))
            except Exception:
                continue
        return None

    def update(self, frame_ms, infer_ms):
        direct = self._read_direct_npu_util()
        if direct is not None:
            util = direct
        else:
            util = (infer_ms * 100.0 / frame_ms) if frame_ms > 0 else 0.0
            util = max(0.0, min(100.0, util))

        self.ema_util = self.ema_util * 0.8 + util * 0.2
        return self.ema_util


def main():
    disp = display.Display()
    cam = camera.Camera(config.CAM_WIDTH, config.CAM_HEIGHT)
    try:
        cam.set_brightness(-1)
        cam.set_contrast(1)
    except Exception:
        pass

    # [FIX] AIEngine của Du_An_Maix_V2 không nhận iou_threshold trong init (nó tự động adaptive)
    engine = AIEngine(config.MODEL_PATH, conf_threshold=config.CONF_THRESHOLD)
    tracker = ObjectTracker()
    ui = HUD(config.CAM_WIDTH, config.CAM_HEIGHT)
    iot_client = TinkerClient(host=config.TINKER_IP, port=config.TINKER_PORT)

    # [FIX] Phải gọi load() để nạp model vào NPU.
    if not engine.load():
        print("❌ Không thể nạp model AI. Thoát chương trình.")
        return

    cpu_meter = CPUMeter()
    npu_meter = NPUMeter()

    fps_show = getattr(config, "FPS_LIMIT", 30)
    t_last = time.time()
    t_last_stats = 0.0

    print("🚀 Bắt đầu luồng xử lý chính...", flush=True)

    while not app.need_exit():
        t_frame_start = time.time()
        img = cam.read()
        if img is None:
            continue

        current_time = time.time()

        t_inf0 = time.time()
        # [FIX] engine.process trả về tuple (img, results) trong Du_An_Maix_V2
        _, raw_objs = engine.process(img)
        infer_ms = (time.time() - t_inf0) * 1000.0

        # [FIX] ObjectTracker của V2 nhận trực tiếp list dict từ AI, tự xử lý smoothing/gesture
        processed_people = tracker.update(raw_objs)

        # [FIX] Vẽ giao diện bằng HUD (đã bao gồm vẽ xương, box, và thông báo action)
        ui.draw_ai_result(img, processed_people)

        # [FIX] Gửi cảnh báo qua IoT (TinkerClient của V2 dùng send_pose)
        if getattr(config, "ENABLE_TINKER", False):
            iot_client.send_pose(processed_people)

        dt = current_time - t_last
        if dt > 0:
            fps_show = (fps_show * 0.9) + ((1.0 / dt) * 0.1)
        t_last = current_time
        ui.draw_fps(img, fps_show)

        frame_ms = (time.time() - t_frame_start) * 1000.0
        # [OPTIMIZE] NPU cần update liên tục mỗi frame để bộ lọc làm mượt (EMA) hoạt động đúng
        npu_pct = npu_meter.update(frame_ms, infer_ms)

        if (current_time - t_last_stats) >= 1.5:
            # [OPTIMIZE] Chỉ đọc CPU/RAM mỗi 1.5s. 
            # Giúp tính được mức trung bình trong 1.5s qua -> Số liệu ổn định, chính xác hơn.
            cpu_pct = cpu_meter.read_percent()
            ram_used, ram_total, ram_pct = read_ram()
            
            if not getattr(config, "ENABLE_TINKER", False):
                print(
                    f"CPU {cpu_pct:5.1f}% | "
                    f"RAM {ram_used:5.1f}/{ram_total:5.1f} MB ({ram_pct:4.1f}%) | "
                    f"NPU {npu_pct:5.1f}% | "
                    f"INF {infer_ms:5.1f} ms | "
                    f"FPS {fps_show:4.1f} | "
                    f"POSE {len(processed_people)}",
                    flush=True,
                )
            t_last_stats = current_time

        disp.show(img)


if __name__ == "__main__":
    main()
