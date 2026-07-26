"""
Pure Python dashboard - fallback when Node fails (keeps server online)
Used for Pterodactyl panels that use python image without Node.js
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

def run_dashboard(port=3000, config=None, node_missing=False):
    config = config or {}
    public_dir = ROOT / "src/web/public"

    # Try Flask, fallback to minimal HTTP
    try:
        from flask import Flask, send_from_directory, jsonify, Response
    except ImportError:
        print("Flask not installed, installing...")
        try:
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "flask", "--break-system-packages", "-q"], timeout=60)
            from flask import Flask, send_from_directory, jsonify, Response
        except Exception as e:
            print(f"Flask install failed: {e}, using minimal HTTP server")
            return run_minimal_http(port, config, node_missing)

    app = Flask(__name__, static_folder=str(public_dir))

    @app.route("/")
    def index():
        # If node missing, serve a custom warning page, but still try to serve original if exists
        if node_missing:
            # If original index.html exists, inject warning via HTML wrapper? For simplicity, serve warning + link to original
            # We will serve a hybrid page that shows warning and still loads original dashboard below
            warning_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Antares - Node.js Missing</title>
                <style>
                    body{{font-family: system-ui, sans-serif;background:#0f0f10;color:#e2e8f0;margin:0;padding:20px}}
                    .alert{{background:linear-gradient(135deg,#ff4d4d,#a00);color:white;padding:20px;border-radius:12px;margin-bottom:20px;box-shadow:0 4px 20px rgba(255,0,0,0.3)}}
                    .card{{background:#1e1e20;border:1px solid #333;border-radius:12px;padding:20px;margin-bottom:16px}}
                    code{{background:#2a2a2e;padding:4px 8px;border-radius:6px;display:block;margin:8px 0;white-space:pre-wrap;word-break:break-all;color:#22d3ee}}
                    a{{color:#a78bfa;text-decoration:none}} a:hover{{text-decoration:underline}}
                    .btn{{background:#7c3aed;color:white;padding:10px 20px;border-radius:8px;display:inline-block;margin-top:10px}}
                </style>
            </head>
            <body>
                <div class="alert">
                    <h2>⚠ Node.js Không Tìm Thấy - Server Vẫn Online (Fallback Mode)</h2>
                    <p>Panel <b>nvnmc.top</b> của bạn đang dùng image Python thuần, không có Node.js nên bot Minecraft không chạy được.</p>
                    <p>Server được giữ online bằng Python fallback để bạn có thời gian fix, không bị crash loop.</p>
                </div>

                <div class="card">
                    <h3>🔧 Cách Fix Nhanh (Chọn 1):</h3>
                    <p><b>Cách 1: Đổi Startup Command trong Pterodactyl panel:</b></p>
                    <code>curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs && pip install -r requirements.txt --break-system-packages && npm install && python main.py</code>

                    <p><b>Cách 2: Nếu panel cho phép custom Docker image, dùng:</b></p>
                    <code>python:3.11-slim + nodejs (Dockerfile mới đã hỗ trợ)</code>

                    <p><b>Cách 3: Dùng Node.js image thay vì Python:</b></p>
                    <p>Đổi Egg sang Nodejs 22, MAIN_FILE = main.js, Start = node main.js</p>

                    <p><b>Cách 4: Main.py sẽ tự tải Node (đã fix):</b></p>
                    <p>Bản mới đã có tính năng auto-download Node.js binary. Hãy kéo code mới nhất từ GitHub và restart server. Nếu vẫn lỗi, dùng Cách 1.</p>
                </div>

                <div class="card">
                    <h3>📊 Trạng Thái Hiện Tại</h3>
                    <p>Port: {port}</p>
                    <p>Mode: Python Fallback (giữ online)</p>
                    <p>Config bots: {len(config.get('bots', []))} bot(s)</p>
                    <p>Config path: {str(ROOT / 'config.json')}</p>
                    <p><a class="btn" href="/api/bots">Xem API Bots</a> <a class="btn" href="/api/system">System Info</a></p>
                </div>

                <div class="card">
                    <h3>📥 Tải Bản Fix Mới</h3>
                    <p>Code mới nhất đã fix auto-download Node:</p>
                    <code>https://github.com/Fake2znzj/bunlmao/archive/refs/heads/arena/019f9eb9-bunlmao.zip</code>
                    <p>Release: <a href="https://github.com/Fake2znzj/bunlmao/releases/tag/v2.0-python-wrapper" target="_blank">v2.0-python-wrapper</a></p>
                </div>

                <div class="card" style="opacity:0.7">
                    <h4>Original Dashboard (có thể không hoạt động đủ vì thiếu Node)</h4>
                    <p><a href="/static-index">Mở dashboard gốc (src/web/public/index.html)</a></p>
                </div>
            </body>
            </html>
            """
            return Response(warning_html, mimetype='text/html')
        try:
            if (public_dir / "index.html").exists():
                return send_from_directory(str(public_dir), "index.html")
            else:
                return "Antares Dashboard - index.html not found", 404
        except Exception as e:
            return f"Error serving index: {e}", 500

    @app.route("/static-index")
    def static_index():
        try:
            return send_from_directory(str(public_dir), "index.html")
        except Exception as e:
            return f"Error: {e}", 500

    @app.route("/api/bots")
    def api_bots():
        bots = config.get("bots", [])
        summaries = []
        for b in bots:
            summaries.append({
                "id": b.get("id"),
                "state": "OFFLINE - Node missing" if node_missing else "OFFLINE",
                "host": b.get("host"),
                "port": b.get("port"),
                "username": b.get("username"),
                "ping": -1,
                "nodeMissing": node_missing,
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
                "pythonVersion": f"{sys.version}",
                "mode": "python-fallback" if node_missing else "python-wrapper",
                "nodeMissing": node_missing,
                "fix": "Install Node.js >=22 or use auto-download version"
            })
        except:
            return jsonify({
                "mode": "python-fallback" if node_missing else "python-wrapper",
                "nodeMissing": node_missing,
                "note": "install psutil for metrics",
                "fix": "curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs"
            })

    @app.route("/api/status")
    def api_status():
        return jsonify({
            "ok": True,
            "nodeMissing": node_missing,
            "mode": "fallback",
            "port": port,
            "message": "Server đang chạy fallback mode, cần cài Node.js để chạy bot"
        })

    @app.route("/<path:path>")
    def static_files(path):
        try:
            return send_from_directory(str(public_dir), path)
        except Exception:
            return f"File {path} not found", 404

    print(f"[Python Dashboard] Starting on 0.0.0.0:{port} (node_missing={node_missing})")
    print(f"[Python Dashboard] Static dir: {public_dir}")
    # Disable reloader, enable threaded
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True, use_reloader=False)

def run_minimal_http(port, config, node_missing):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json as js

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = f"""
            <html><head><title>Antares - Fallback</title></head>
            <body style="font-family:sans-serif;background:#111;color:#eee;text-align:center;padding:50px">
            <h1>Antares - Fallback Mode</h1>
            <p>Node.js missing: {node_missing}</p>
            <p>Port: {port}</p>
            <p>Bots: {len(config.get('bots', []))}</p>
            <hr>
            <p>Fix: curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs && python main.py</p>
            </body></html>
            """
            self.wfile.write(html.encode('utf-8'))
            if self.path == "/api/bots":
                self.wfile.write(js.dumps(config.get("bots", [])).encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[Minimal HTTP] Running on 0.0.0.0:{port} - keeping online")
    server.serve_forever()
