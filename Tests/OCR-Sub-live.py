import cv2
import numpy as np
import win32gui
import os
import time
import ctypes
import keyboard
import mss  # schneller als pyautogui!

# ---------------- Einstellungen ----------------
DESIRED_SUBTEAM = "Brute"  # Welches Subteam soll gewählt werden?
THRESHOLD = 0.5            # Mindestscore für Klick

SUBTEAM_TEMPLATES = {
    "Patient": "Subteam_templates/patient_template.png",
    "Psychotic": "Subteam_templates/sub_psychotic.png",
    "Psychosomatic": "Subteam_templates/sub_psychosomatic.png",
    "Brute": "Subteam_templates/sub_brute.png",
    "Historic": "Subteam_templates/sub_historic.png"
}

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
    ctypes.windll.user32.SendInput(1, ctypes.byref(INPUT(0, mi)), ctypes.sizeof(INPUT))

    time.sleep(0.01)

    # Klick runter
    mi = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE, 0, None)
    ctypes.windll.user32.SendInput(1, ctypes.byref(INPUT(0, mi)), ctypes.sizeof(INPUT))
    time.sleep(0.02)

    # Klick hoch
    mi = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE, 0, None)
    ctypes.windll.user32.SendInput(1, ctypes.byref(INPUT(0, mi)), ctypes.sizeof(INPUT))

    print(f"🖱️ Klick bei ({x},{y})")

# ---------------- Screenshot mit mss ----------------
def screenshot_hwnd(hwnd):
    x1, y1, x2, y2 = win32gui.GetWindowRect(hwnd)
    w, h = x2 - x1, y2 - y1
    with mss.mss() as sct:
        monitor = {"left": x1, "top": y1, "width": w, "height": h}
        img = np.array(sct.grab(monitor))
    return img, (x1, y1), (w, h)

# ---------------- Template Matching ----------------
def match_template_scaled(img_gray, template, win_h, ref_h=2160):
    scale = win_h / ref_h
    template_scaled = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    th, tw = template_scaled.shape[:2]

    if th > img_gray.shape[0] or tw > img_gray.shape[1]:
        return None, 0, None, None

    res = cv2.matchTemplate(img_gray, template_scaled, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    return max_loc, max_val, th, tw

# ---------------- Templates einmal laden ----------------
def load_templates(win_h):
    templates = {}
    for label, path in SUBTEAM_TEMPLATES.items():
        abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        t = cv2.imread(abs_path, cv2.IMREAD_UNCHANGED)
        if t is None:
            print(f"⚠️ Template fehlt: {abs_path}")
            continue
        if len(t.shape) == 3:
            t = cv2.cvtColor(t, cv2.COLOR_BGRA2GRAY) if t.shape[2] == 4 else cv2.cvtColor(t, cv2.COLOR_BGR2GRAY)
        # gleich skalieren!
        scale = win_h / 2160
        t = cv2.resize(t, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        templates[label] = t
    return templates

# ---------------- Main ----------------
def main():
    hwnds = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd).strip() == "Roblox":
            hwnds.append(hwnd)
    win32gui.EnumWindows(callback, None)

    if not hwnds:
        print("❌ Kein Roblox gefunden")
        return

    hwnd = max(hwnds, key=lambda h: (win32gui.GetWindowRect(h)[2] - win32gui.GetWindowRect(h)[0]) *
                                    (win32gui.GetWindowRect(h)[3] - win32gui.GetWindowRect(h)[1]))
    print("✅ Roblox Fenster gefunden")

    # einmal Screenshot, um Höhe zu bestimmen
    img, offset, (win_w, win_h) = screenshot_hwnd(hwnd)
    templates = load_templates(win_h)

    # ---------------- Klick auf Patient ----------------
    if "Patient" in templates:
        loc, val, th, tw = match_template_scaled(cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR), cv2.COLOR_BGR2GRAY),
                                                 templates["Patient"], win_h)
        if loc and val >= THRESHOLD:
            cx = offset[0] + loc[0] + tw // 2
            cy = offset[1] + loc[1] + int(th * 0.85)
            send_input_click(cx, cy)
            time.sleep(1)
        else:
            print("❌ Patient nicht gefunden!")
            return

    # ---------------- Schleife für Subteam ----------------
    last_print = 0
    while True:
        img, offset, (win_w, win_h) = screenshot_hwnd(hwnd)
        img_gray = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR), cv2.COLOR_BGR2GRAY)

        scores = {}

        for label, template in templates.items():
            loc, val, th, tw = match_template_scaled(img_gray, template, win_h)
            scores[label] = val

            if label == DESIRED_SUBTEAM and loc and val >= THRESHOLD:
                cx = offset[0] + loc[0] + tw // 2
                cy = offset[1] + loc[1] + int(th * 0.85)
                send_input_click(cx, cy)
                print(f"✅ Subteam {label} gewählt!")
                return  # Ende

        # nur 1x pro Sekunde Scores ausgeben
        if time.time() - last_print >= 1.0:
            print("\n--- Scores ---")
            for label, score in scores.items():
                print(f"{label:12}: {score:.3f}")
            last_print = time.time()

        # Wenn Subteam nicht erkannt → „E“ drücken
        print(f"⚠️ {DESIRED_SUBTEAM} nicht erkannt → drücke 'E'")
        keyboard.send("e")
        time.sleep(0.3)  # kürzer warten für mehr Speed

if __name__ == "__main__":
    main()
