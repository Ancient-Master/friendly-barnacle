import win32gui
import win32ui
import win32con
import ctypes
import numpy as np
import cv2

# ---------------- Roblox window capture ----------------
def find_roblox_window():
    hwnds = []
    def callback(h, _):
        if win32gui.IsWindowVisible(h) and "Roblox" in win32gui.GetWindowText(h):
            hwnds.append(h)
    win32gui.EnumWindows(callback, None)
    return hwnds

def capture_window(hwnd):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top

    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)

    PW_RENDERFULLCONTENT = 0x00000002
    result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)

    if result != 1:
        saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)

    bmpinfo = saveBitMap.GetInfo()
    bmpstr = saveBitMap.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype=np.uint8)
    img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)

    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

# ---------------- Load templates ----------------
template_paths = [
    r"\target.png",
    r"\user.png",
    r"\user1.png",
]

templates = []
for path in template_paths:
    temp = cv2.imread(path)
    if temp is None:
        raise FileNotFoundError(f"Template not found: {path}")
    templates.append({
        "image": temp,
        "gray": cv2.cvtColor(temp, cv2.COLOR_BGR2GRAY),
        "rects": []  # store detected rectangles
    })

# ---------------- Main live tracking ----------------
hwnds = find_roblox_window()
if not hwnds:
    print("❌ No Roblox window found")
    exit()

hwnd = hwnds[0]
print("✅ Capturing Roblox window")

threshold = 0.8
thickness = 3  # rectangle thickness

while True:
    img = capture_window(hwnd)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # ---------------- Track all templates ----------------
    for i, t in enumerate(templates):
        res = cv2.matchTemplate(gray, t["gray"], cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= threshold)
        t["rects"] = [(int(x), int(y)) for x, y in zip(*loc[::-1])]  # update rects every frame

        # Draw rectangles only if matches found
        if t["rects"]:
            h, w = t["image"].shape[:2]
            color = (0, 255, 0) if i == 0 else (0, 0, 255)
            for pt in t["rects"]:
                cv2.rectangle(img, pt, (pt[0]+w, pt[1]+h), color, thickness)

    cv2.imshow("Roblox Live Tracking", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
