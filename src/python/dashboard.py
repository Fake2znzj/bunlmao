"""
Experimental pure Python dashboard - fallback when Node fails
Uses Flask to serve frontend and provides basic API
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

def run_dashboard(port=3000, config=None):
    try:
        from flask import Flask, send_from_directory, jsonify
    except ImportError:
        print("Flask not installed. Install via: pip install flask")
        print("Falling back: Please run 'python main.py' without --python-only")
        return

    config = config or {}
    public_dir = ROOT / "src/web/public"

    app = Flask(__name__, static_folder=str(public_dir))

    @app.route("/")
    def index():
        return send_from_directory(str(public_dir), "index.html")

    @app.route("/api/bots")
    def api_bots():
        bots = config.get("bots", [])
        # Enrich minimal summary
        summaries = []
        for b in bots:
            summaries.append({
                "id": b.get("id"),
                "state": "OFFLINE",
                "host": b.get("host"),
                "port": b.get("port"),
                "username": b.get("username"),
                "ping": -1,
            })
        return jsonify(summaries)

    @app.route("/api/system")
    def api_system():
        try:
            import psutil
            mem = psutil.virtual_memory()
            return jsonify({
                "memPercent": mem.percent,
                "totalMem": mem.total,
                "platform": os.name,
                "pythonVersion": f"{os.sys.version}",
                "mode": "python-wrapper-experimental"
            })
        except:
            return jsonify({"mode": "python-wrapper", "note": "install psutil for metrics"})

    @app.route("/<path:path>")
    def static_files(path):
        return send_from_directory(str(public_dir), path)

    print(f"[Python Dashboard] Starting on http://0.0.0.0:{port}")
    print(f"[Python Dashboard] Static dir: {public_dir}")
    app.run(host="0.0.0.0", port=port, debug=False)
