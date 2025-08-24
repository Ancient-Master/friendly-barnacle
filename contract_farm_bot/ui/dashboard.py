from flask import Flask, render_template, request, jsonify, Response
from ui.config_manager import load_config, save_config
import json, time, threading, sys
import mss
import cv2
import numpy as np
import sys
import os


app = Flask(__name__, template_folder="templates")

status_data = {
    "contracts_completed": 0,
    "uptime": "0m 0s",
    "contracts_per_min": 0.0,
    "script_running": True,
    "paused": False
}

# --- Fake Bot zum Testen (Demo!)
def fake_bot():
    seconds = 0
    while True:
        time.sleep(1)
        if status_data["script_running"] and not status_data["paused"]:
            seconds += 1
            status_data["uptime"] = f"{seconds//60}m {seconds%60}s"
            status_data["contracts_completed"] += 1
            status_data["contracts_per_min"] = status_data["contracts_completed"] / (seconds/60+0.001)

threading.Thread(target=fake_bot, daemon=True).start()

# --- MJPEG Stream Generator für einen Monitor
def generate_frames(monitor_index=1):
    sct = mss.mss()
    monitor = sct.monitors[monitor_index]
    while True:
        screenshot = np.array(sct.grab(monitor))
        frame = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.05)  # ~20 FPS

@app.route('/video_feed/<int:monitor_id>')
def video_feed(monitor_id):
    return Response(generate_frames(monitor_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/monitors")
def get_monitors():
    config = load_config()
    return jsonify({"monitors": config.get("monitors", [1])})

# --- Dashboard + Config
@app.route("/")
def index():
    return render_template("dashboard.html", config=load_config(), status=status_data)

@app.route("/update_config", methods=["POST"])
def update_config():
    new_config = request.json

    # Monitore als Liste verarbeiten
    if "monitors" in new_config:
        if isinstance(new_config["monitors"], list):
            new_config["monitors"] = [int(x) for x in new_config["monitors"] if isinstance(x, int) or str(x).isdigit()]
        else:
            new_config["monitors"] = [1]

    save_config(new_config)
    return jsonify({"message": "Config gespeichert", "config": new_config})

@app.route("/pause_toggle", methods=["POST"])
def pause_toggle():
    status_data["paused"] = not status_data["paused"]
    return jsonify({"paused": status_data["paused"]})

@app.route("/stop_script", methods=["POST"])
def stop_script():
    status_data["script_running"] = False
    print("⛔ Stop gedrückt – Prozess wird sofort beendet.")
    os._exit(0)   # Hartes Beenden, kein Zurück

def shutdown_server():
    func = request.environ.get("werkzeug.server.shutdown")
    if func is None:
        print("⚠️ Konnte Server nicht sauber herunterfahren, erzwinge exit.")
        sys.exit(0)
    func()
    sys.exit(0)

# --- SSE Event Stream
@app.route("/status_stream")
def status_stream():
    def generate():
        while True:
            time.sleep(1)
            yield f"data: {json.dumps(status_data)}\n\n"
    return Response(generate(), mimetype="text/event-stream")
