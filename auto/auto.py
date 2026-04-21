import os
import cv2
import numpy as np
import time
import subprocess
import gc

ADB = r"C:\Users\DAI PHAT\Downloads\platform-tools-latest-windows\platform-tools\adb.exe"

TEMPLATES = ["skip.png", "exit.png", "unit-1.png", "unit-3.png", "unit-4.png"]

def adb(cmd):
    subprocess.run(f'"{ADB}" {cmd}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def tap(x, y):
    adb(f"shell input tap {x} {y}")

def screenshot():
    adb("shell screencap -p /sdcard/screen.png")
    adb("pull /sdcard/screen.png .")
    # Đọc 1 lần, resize nhỏ lại để tiết kiệm RAM, trả về cả 2 phiên bản
    img = cv2.imread("screen.png", 0)  # grayscale cho find()
    if img is None:
        return None
    # Resize xuống 50% để tiết kiệm RAM
    img = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
    return img

def find(screen, template_path, threshold=0.7):
    """Nhận screen từ ngoài, không tự đọc file."""
    if screen is None:
        return None
    template = cv2.imread(template_path, 0)
    if template is None:
        print(f"❌ Thiếu {template_path}")
        return None

    # Resize template cùng tỉ lệ với screen
    template = cv2.resize(template, (0, 0), fx=0.5, fy=0.5)

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    print(f"{template_path} max: {max_val:.4f}")

    t_h, t_w = template.shape
    del result, template
    gc.collect()

    if max_val >= threshold:
        # Nhân 2 lại vì tọa độ tap cần theo ảnh gốc
        center_x = (max_loc[0] + t_w // 2) * 2
        center_y = (max_loc[1] + t_h // 2) * 2
        return (center_x, center_y)
    return None

def setup_templates():
    print("📸 Đang chụp màn hình từ điện thoại...")
    adb("shell screencap -p /sdcard/screen.png")
    adb("pull /sdcard/screen.png .")

    img = cv2.imread("screen.png")
    if img is None:
        print("❌ Không đọc được screen.png.")
        return False

    MAX_H, MAX_W = 850, 480
    orig_h, orig_w = img.shape[:2]
    scale = min(MAX_W / orig_w, MAX_H / orig_h)
    display = cv2.resize(img, (int(orig_w * scale), int(orig_h * scale)))
    del img
    gc.collect()

    print(f"📐 scale={scale:.2f}")
    print("\n✅ Màn hình đã chụp xong!")
    print("=" * 50)
    print("Hướng dẫn: Kéo chuột → ENTER lưu, C chọn lại")
    print("=" * 50)

    for name in TEMPLATES:
        while True:
            print(f"\n👉 Đang crop: {name}")
            img_orig = cv2.imread("screen.png")
            roi = cv2.selectROI(
                f"Chon [{name}] - ENTER luu, C chon lai",
                display, fromCenter=False, showCrosshair=True
            )
            cv2.destroyAllWindows()

            x, y, w, h = roi
            if w == 0 or h == 0:
                print("⚠️  Chưa chọn vùng! Thử lại...")
                del img_orig
                continue

            x0, y0 = int(x / scale), int(y / scale)
            w0, h0 = int(w / scale), int(h / scale)
            crop = img_orig[y0:y0+h0, x0:x0+w0]
            cv2.imwrite(name, crop)
            print(f"✅ Đã lưu {name} ({w0}x{h0} tại {x0},{y0})")
            del img_orig, crop
            gc.collect()
            break

    del display
    gc.collect()
    print("\n🎉 Crop xong!")
    return True

def run_debug():
    print("\n🔍 Debug template...")
    screen = screenshot()
    all_ok = True
    for name in TEMPLATES:
        pos = find(screen, name)
        if pos:
            print(f"  ✅ {name} → {pos}")
        else:
            print(f"  ❌ {name} → không thấy")
            all_ok = False
    del screen
    gc.collect()
    return all_ok

def reset_state():
    return {
        "phase": "pre",
        "unit3_count": 0,
        "wait_start": None,
        "clicked4": False,
        "start_time": time.time(),
    }

def run_bot():
    RETRY_BTN  = (953, 913)
    RETRY_BTNd = (1317, 767)
    UNIT3_BURST = 3
    UNIT3_WAIT  = 45
    START_DELAY = 18

    s = reset_state()
    print("\n🤖 Bot đang chạy... (Ctrl+C để dừng)")

    while True:
        # Chụp và đọc ảnh 1 lần duy nhất
        screen = screenshot()
        if screen is None:
            print("❌ Không chụp được màn hình, thử lại...")
            time.sleep(2)
            continue

        # ===== CHECK DEFEAT / WIN =====
        if find(screen, "defeat.png"):
            print("💀 Defeat!")
            del screen; gc.collect()
            time.sleep(1); tap(*RETRY_BTNd); time.sleep(5)
            s = reset_state(); continue

        if find(screen, "victory.png"):
            print("🎉 Victory!")
            del screen; gc.collect()
            time.sleep(1); tap(*RETRY_BTN); time.sleep(5)
            s = reset_state(); continue

        # ===== CHỜ ĐẦU MÀN =====
        elapsed = time.time() - s["start_time"]
        if elapsed < START_DELAY:
            print(f"  ⏳ Chờ thêm {int(START_DELAY - elapsed)}s...")
            del screen; gc.collect()
            time.sleep(1); continue

        pos3 = find(screen, "unit-3.png", threshold=0.8)
        pos1 = find(screen, "unit-1.png")
        pos4 = find(screen, "unit-4.png")

        # Giải phóng screen ngay sau khi find xong
        del screen
        gc.collect()

        # ── Cập nhật phase ──
        if s["phase"] == "waiting":
            remaining = UNIT3_WAIT - (time.time() - s["wait_start"])
            if remaining <= 0:
                s["phase"] = "free"
                print("  🔓 Hết chờ → spam tự do!")
            else:
                print(f"  ⏳ Chờ thêm {int(remaining)}s...")

        # ===== UNIT 3 =====
        if pos3:
            if s["phase"] == "pre":
                tap(*pos3)
                s["unit3_count"] += 1
                s["phase"] = "burst"
                print(f"  👆 Unit-3 burst {s['unit3_count']}/{UNIT3_BURST}")
            elif s["phase"] == "burst":
                if s["unit3_count"] < UNIT3_BURST:
                    tap(*pos3)
                    s["unit3_count"] += 1
                    print(f"  👆 Unit-3 burst {s['unit3_count']}/{UNIT3_BURST}")
                if s["unit3_count"] >= UNIT3_BURST:
                    s["phase"] = "waiting"
                    s["wait_start"] = time.time()
                    print(f"  ✅ Đủ {UNIT3_BURST} lần → chờ {UNIT3_WAIT}s")
            elif s["phase"] == "free":
                tap(*pos3)

        # ===== UNIT 1 =====
        if pos1:
            if s["phase"] in ("pre", "free"):
                tap(*pos1)
            else:
                print(f"  🛑 Unit-1 dừng (phase={s['phase']})")

        # ===== UNIT 4 =====
        if pos4 and not s["clicked4"]:
            tap(*pos4)
            s["clicked4"] = True
        elif not pos4:
            s["clicked4"] = False

        time.sleep(2)

if __name__ == "__main__":
    print("=" * 50)
    print("       GAME BOT - ZOMBIE AUTO CLICKER")
    print("=" * 50)

    missing = [t for t in TEMPLATES if not os.path.exists(t)]

    if missing:
        print(f"\n⚠️  Thiếu template: {missing}")
        choice = "1"
    else:
        print("\nTemplate đã có sẵn:")
        for t in TEMPLATES:
            print(f"  ✔ {t}")
        print("\n[1] Crop lại template mới")
        print("[2] Chạy debug kiểm tra template hiện tại")
        print("[3] Chạy bot luôn")
        choice = input("\nChọn (1/2/3): ").strip()

    if choice == "1":
        if setup_templates():
            input("\n✅ Crop xong! Nhấn Enter để debug...")
            run_debug()
            input("\nNhấn Enter để bắt đầu bot...")
            run_bot()
    elif choice == "2":
        run_debug()
        input("\nNhấn Enter để bắt đầu bot...")
        run_bot()
    elif choice == "3":
        print("\nBắt đầu sau 5s...")
        time.sleep(5)
        run_bot()
    else:
        print("Lựa chọn không hợp lệ.")