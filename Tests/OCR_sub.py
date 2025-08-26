import cv2
import numpy as np
import pyautogui
import win32gui
import os
import time
import ctypes
import keyboard

# ---------------- Einstellungen ----------------
DESIRED_SUBTEAM = "Historic"
# mögliche Werte: "Patient", "Psychotic", "Psychosomatic", "Brute", "Historic"

SUBTEAM_TEMPLATES = {
    "Patient": "patient_template.png",
    "Psychotic": "sub_psychotic.png",
    "Psychosomatic": "sub_psychosomatic.png",
    "Brute": "sub_brute.png",
    "Historic": "sub_historic.png"
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
    return np.array(img), (x1, y1), (w, h)

# ---------------- Template Matching mit Skalierung ----------------
def match_template_scaled(img_gray, template, win_h, ref_h=2160):
    """Skaliert Template auf Fensterhöhe und macht Matching."""
    scale = win_h / ref_h
    template_scaled = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    th, tw = template_scaled.shape[:2]

    if th > img_gray.shape[0] or tw > img_gray.shape[1]:
        return None, 0, None, None

    res = cv2.matchTemplate(img_gray, template_scaled, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    return max_loc, max_val, th, tw

# ---------------- Template Finder ----------------
def find_template(hwnd, template_filename, label="Template"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, template_filename)

    img, offset, (win_w, win_h) = screenshot_hwnd(hwnd)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
    if template is None:
        print(f"❌ Template konnte nicht geladen werden: {template_path}")
        return None

    if len(template.shape) == 3 and template.shape[2] == 4:
        template = cv2.cvtColor(template, cv2.COLOR_BGRA2GRAY)
    elif len(template.shape) == 3:
        template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    max_loc, max_val, th, tw = match_template_scaled(img_gray, template, win_h)
    print(f"🔍 {label} Match Score: {max_val:.3f}")
    if not max_loc or max_val < 0.6:
        print(f"❌ {label} nicht gefunden")
        return None

    # Klickposition = untere Mitte
    cx = offset[0] + (max_loc[0] + tw // 2)
    cy = offset[1] + (max_loc[1] + int(th * 0.85))
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

    # Schritt 1: Patient wählen
    patient_btn = find_template(hwnd, "patient_template.png", label="Patient")
    if patient_btn:
        send_input_click(*patient_btn)
        time.sleep(0.7)  # Warte bis Subteam-Auswahl erscheint

        # Schritt 2: Gewünschtes Subteam
                # Schritt 2: Gewünschtes Subteam wiederholt suchen
        if DESIRED_SUBTEAM in SUBTEAM_TEMPLATES:
            template_file = SUBTEAM_TEMPLATES[DESIRED_SUBTEAM]

            while True:
                subteam_btn = find_template(hwnd, template_file, label=f"Subteam {DESIRED_SUBTEAM}")
                if subteam_btn:
                    send_input_click(*subteam_btn)
                    print(f"✅ Subteam {DESIRED_SUBTEAM} gewählt!")
                    break
                else:
                    print(f"⚠️ Subteam {DESIRED_SUBTEAM} nicht erkannt → drücke 'E' und versuche erneut")
                    keyboard.send("e")
                    time.sleep(0.25)
        else:
            print(f"❌ Ungültiges Subteam in DESIRED_SUBTEAM: {DESIRED_SUBTEAM}")


    else:
        print("❌ Kein Hauptteam 'Patient' klickbar")

if __name__ == "__main__":
    main()
