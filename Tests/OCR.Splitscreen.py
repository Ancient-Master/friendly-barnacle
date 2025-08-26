import cv2
import numpy as np
import pyautogui
import win32gui
import win32con
import win32api
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
    time.sleep(0.05)

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

# ---------------- Fenster-Handling ----------------
def enum_windows():
    hwnds = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            # Nur exaktes Roblox
            if "Roblox" == title or title.strip() == "Roblox":
                hwnds.append((hwnd, title, class_name))
    win32gui.EnumWindows(callback, None)
    return hwnds

def move_window(hwnd, title, monitor_index, pos="left", is_uwp=False):
    monitors = win32api.EnumDisplayMonitors()
    mon_info = win32api.GetMonitorInfo(monitors[monitor_index][0])
    x1, y1, x2, y2 = mon_info["Monitor"]
    mon_w, mon_h = x2 - x1, y2 - y1
    half_w = mon_w // 2

    if pos == "left":
        target_x, target_y, w, h = x1, y1, half_w, mon_h
    else:
        target_x, target_y, w, h = x1 + half_w, y1, half_w, mon_h

    # Aktuelle Fensterposition prüfen
    cur_x1, cur_y1, cur_x2, cur_y2 = win32gui.GetWindowRect(hwnd)
    cur_w, cur_h = cur_x2 - cur_x1, cur_y2 - cur_y1
    if abs(cur_x1 - target_x) < 10 and abs(cur_y1 - target_y) < 10 and abs(cur_w - w) < 20 and abs(cur_h - h) < 20:
        print(f"⏭️ Fenster '{title}' schon im Split-Screen → skip")
        return

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.2)

        if is_uwp:
            win32gui.SetWindowPos(hwnd, None, x1, y1, mon_w, mon_h,
                                  win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW | win32con.SWP_FRAMECHANGED)
            time.sleep(0.2)
            win32gui.SetWindowPos(hwnd, None, target_x, target_y, w, h,
                                  win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW | win32con.SWP_FRAMECHANGED)
            print(f"✅ UWP '{title}' → {pos} auf Monitor {monitor_index} ({w}x{h})")
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(0.2)
            win32gui.SetWindowPos(hwnd, None, target_x, target_y, w, h,
                                  win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW)
            print(f"✅ Player '{title}' → {pos} auf Monitor {monitor_index} ({w}x{h})")
    except Exception as e:
        print(f"⚠️ Fehler beim Verschieben '{title}': {e}")

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

    # Multi-Scale Matching von 30% bis 200%
    for scale in np.linspace(0.3, 2.0, 35):
        resized = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        rh, rw = resized.shape[:2]

        if rh > img_gray.shape[0] or rw > img_gray.shape[1]:
            continue

        res = cv2.matchTemplate(img_gray, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val > best_val:
            best_val, best_loc, th, tw, best_scale = max_val, max_loc, rh, rw, scale

    print(f"🔍 Best Match: {best_val:.3f} @ scale {best_scale:.2f}")
    if best_val < 0.6:
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
    roblox_windows = enum_windows()
    if len(roblox_windows) < 2:
        print("❌ Weniger als 2 Roblox Fenster gefunden")
        return

    uwp_hwnd, player_hwnd = None, None
    for hwnd, title, class_name in roblox_windows:
        if class_name == "ApplicationFrameWindow":  # UWP
            uwp_hwnd = hwnd
        else:
            player_hwnd = hwnd

    if not uwp_hwnd or not player_hwnd:
        print("❌ Konnte UWP oder Player nicht eindeutig finden")
        return

    move_window(uwp_hwnd, "Roblox UWP", monitor_index=0, pos="left", is_uwp=True)
    move_window(player_hwnd, "Roblox Player", monitor_index=0, pos="right", is_uwp=False)

    time.sleep(2)

    button_center = find_patient(uwp_hwnd)
    if button_center:
        send_input_click(button_center[0], button_center[1])
    else:
        print("❌ Kein Patient Button klickbar")

if __name__ == "__main__":
    main()
