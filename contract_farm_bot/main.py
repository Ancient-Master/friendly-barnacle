from ui.dashboard import app

if __name__ == "__main__":
    print("🌐 Dashboard läuft auf http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
