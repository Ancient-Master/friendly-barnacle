import cv2
import numpy as np
import pyautogui
import win32gui
import os
import time
import ctypes

# ---------------- SendInput Setup ----------------
PUL = ctypes.POINTER(ctypes.c_ulong)

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("mi", MOUSEINPUT)]

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

def send_input_click(x, y):
    """Simuliert echten Klick via SendInput (UWP-kompatibel)."""
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)

    abs_x = int(x * 65535 / screen_w)
    abs_y = int(y * 65535 / screen_h)

    # Maus bewegen
    mi = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None)
    input_event = INPUT(0, mi)
    ctypes.windll.user32.SendInput(1, ctypes.byref(input_event), ctypes.sizeof(input_event))
    time.sleep(0.02)

    # Klick runter
    mi = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE, 0, None)
    input_event = INPUT(0, mi)
    ctypes.windll.user32.SendInput(1, ctypes.byref(input_event), ctypes.sizeof(input_event))
    time.sleep(0.05)

    # Klick hoch
    mi = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE, 0, None)
    input_event = INPUT(0, mi)
    ctypes.windll.user32.SendInput(1, ctypes.byref(input_event), ctypes.sizeof(input_event))

    print(f"🖱️ SendInput-Klick bei ({x},{y})")

# ---------------- Screenshot vom Roblox Fenster ----------------
def screenshot_hwnd(hwnd):
    rect = win32gui.GetWindowRect(hwnd)
    x1, y1, x2, y2 = rect
    w, h = x2 - x1, y2 - y1
    img = pyautogui.screenshot(region=(x1, y1, w, h))
    return np.array(img), (x1, y1)

# ---------------- Patient finden ----------------
def find_patient(hwnd, template_filename="patient_template.png"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, template_filename)

    img, offset = screenshot_hwnd(hwnd)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
    if template is None:
        print(f"❌ Template konnte nicht geladen werden: {template_path}")
        return None

    if len(template.shape) == 3 and template.shape[2] == 4:
        template = cv2.cvtColor(template, cv2.COLOR_BGRA2GRAY)
    elif len(template.shape) == 3:
        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    best_val, best_loc, th, tw, best_scale = 0, None, 0, 0, 1.0

    def search_with_scales(scales):
        nonlocal best_val, best_loc, th, tw, best_scale
        for scale in scales:
            resized = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            rh, rw = resized.shape[:2]

            if rh > img_gray.shape[0] or rw > img_gray.shape[1]:
                continue

            res = cv2.matchTemplate(img_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            if max_val > best_val:
                best_val, best_loc, th, tw, best_scale = max_val, max_loc, rh, rw, scale

    # 🟢 Schnelle Suche
    search_with_scales(np.linspace(0.5, 1.5, 5))

    # 🔴 Fallback: große Range nur wenn nötig
    if best_val < 0.6:
        print("⚠️ Schnelle Suche fehlgeschlagen → Fallback-Vollsuche...")
        search_with_scales(np.linspace(0.3, 2.0, 25))

    print(f"🔍 Best Match: {best_val:.3f} @ scale {best_scale:.2f}")
    if best_val < 0.4:
        print("❌ Patient nicht gefunden")
        return None

    top_left = best_loc
    bottom_right = (top_left[0] + tw, top_left[1] + th)

    # Debug speichern
    cropped = img[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]]
    cv2.imwrite(os.path.join(script_dir, "debug_patient_box.png"), cropped)

    # Klickposition = untere Mitte
    cx = offset[0] + (top_left[0] + tw // 2)
    cy = offset[1] + (top_left[1] + int(th * 0.85))
    return (cx, cy)

# ---------------- Main ----------------
def main():
    hwnds = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            if win32gui.GetWindowText(hwnd).strip() == "Roblox":
                hwnds.append(hwnd)
    win32gui.EnumWindows(callback, None)

    if not hwnds:
        print("❌ Kein Roblox UWP gefunden")
        return

    hwnd = hwnds[0]
    print("✅ Roblox UWP gefunden")

    button_center = find_patient(hwnd)
    if button_center:
        send_input_click(button_center[0], button_center[1])
    else:
        print("❌ Kein Patient Button klickbar")

if __name__ == "__main__":
    main()
