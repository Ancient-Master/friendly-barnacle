from flask import Flask, render_template, request, jsonify, Response
from ui.config_manager import load_config, save_config
import json, time, threading, sys
import mss
import cv2
import numpy as np
import os

app = Flask(__name__, template_folder="templates")

status_data = {
    "contracts_completed": 0,
    "uptime": "0m 0s",
    "contracts_per_min": 0.0,
    "script_running": True,
    "paused": False
}

TEAM_OPTIONS = ["Patient", "Psychotic", "Psychosomatic", "Brute", "Historic"]

# --- Fake Bot zum Testen
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
    monitor = sct.monitors[monitor_index] if monitor_index != 0 else sct.monitors[0]

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
    return render_template("dashboard.html", config=load_config(), status=status_data, teams=TEAM_OPTIONS)

@app.route("/update_config", methods=["POST"])
def update_config():
    try:
        new_config = request.json
        if not isinstance(new_config, dict):
            return jsonify({"success": False, "error": "Ungültige Daten"}), 400

        # Validate team
        if "team" in new_config and new_config["team"] not in TEAM_OPTIONS:
            return jsonify({"success": False, "error": "Ungültiges Team"}), 400

        # Validate monitors
        if "monitors" in new_config:
            monitors_raw = new_config["monitors"]
            if isinstance(monitors_raw, str):
                monitors_list = [x.strip() for x in monitors_raw.split(",") if x.strip() != ""]
                if not monitors_list:
                    new_config["monitors"] = []
                elif monitors_list == ["0"]:
                    new_config["monitors"] = [0]
                else:
                    new_config["monitors"] = [int(x) for x in monitors_list if x.isdigit()]
            elif isinstance(monitors_raw, list):
                new_config["monitors"] = [int(x) for x in monitors_raw if isinstance(x, int) or str(x).isdigit()]
            else:
                new_config["monitors"] = []

        save_config(new_config)
        return jsonify({"success": True, "message": "Config gespeichert", "config": new_config})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/pause_toggle", methods=["POST"])
def pause_toggle():
    try:
        status_data["paused"] = not status_data["paused"]
        return jsonify({"success": True, "paused": status_data["paused"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/stop_script", methods=["POST"])
def stop_script():
    try:
        status_data["script_running"] = False
        print("⛔ Stop gedrückt – Prozess wird sofort beendet.")
        os._exit(0)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# --- SSE Event Stream
@app.route("/status_stream")
def status_stream():
    def generate():
        while True:
            time.sleep(1)
            yield f"data: {json.dumps(status_data)}\n\n"
    return Response(generate(), mimetype="text/event-stream")
