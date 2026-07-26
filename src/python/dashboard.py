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
            # Check if node_modules missing
            node_modules_path = ROOT / "node_modules"
            has_node_modules = node_modules_path.exists() and (node_modules_path / "chalk").exists()
            is_module_not_found = not has_node_modules
            
            # If original index.html exists, inject warning via HTML wrapper? For simplicity, serve warning + link to original
            # We will serve a hybrid page that shows warning and still loads original dashboard below
            if is_module_not_found:
                title = "⚠ MODULE_NOT_FOUND - node_modules thiếu"
                main_msg = f"""
                    <p>Node.js <b>đã cài thành công v22.11.0</b> nhưng <b>node_modules thiếu</b> nên bot không chạy được.</p>
                    <p>Lỗi bạn gặp: <code>MODULE_NOT_FOUND</code> trong <code>main.js</code> - thiếu thư viện <code>chalk, express, mineflayer...</code></p>
                    <p>Server được giữ online bằng Python fallback để bạn fix.</p>
                """
                fix_html = f"""
                    <p><b>Cách 1: Gõ trong Console Pterodactyl (ô Type a command):</b></p>
                    <code>npm install</code>
                    <p>Đợi 1-2 phút cho nó cài xong 200+ packages, sau đó gõ:</p>
                    <code>rs</code> hoặc Restart server

                    <p><b>Cách 2: Đổi Startup Command thành:</b></p>
                    <code>npm install --production --no-fund --no-audit && bash startup.sh</code>

                    <p><b>Cách 3: Xóa node_modules hỏng và cài lại:</b></p>
                    <code>rm -rf node_modules && npm install && python main.py --port {port}</code>

                    <p><b>Cách 4: Dùng bản mới nhất đã fix auto-install:</b></p>
                    <code>https://github.com/Fake2znzj/bunlmao/archive/refs/heads/arena/019f9eb9-bunlmao.zip</code>
                    <p>Bản mới sẽ tự kiểm tra và cài lại nếu thiếu module.</p>
                """
            else:
                title = "⚠ Node.js Không Tìm Thấy - Server Vẫn Online (Fallback Mode)"
                main_msg = f"""
                    <p>Panel <b>nvnmc.top</b> của bạn đang dùng image Python thuần, không có Node.js nên bot Minecraft không chạy được.</p>
                    <p>Server được giữ online bằng Python fallback để bạn có thời gian fix, không bị crash loop.</p>
                """
                fix_html = f"""
                    <p><b>Cách 1: Đổi Startup Command trong Pterodactyl panel:</b></p>
                    <code>curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs && pip install -r requirements.txt --break-system-packages && npm install && python main.py</code>

                    <p><b>Cách 2: Nếu panel cho phép custom Docker image, dùng:</b></p>
                    <code>python:3.11-slim + nodejs (Dockerfile mới đã hỗ trợ)</code>

                    <p><b>Cách 3: Dùng Node.js image thay vì Python:</b></p>
                    <p>Đổi Egg sang Nodejs 22, MAIN_FILE = main.js, Start = node main.js</p>

                    <p><b>Cách 4: Main.py sẽ tự tải Node (đã fix):</b></p>
                    <p>Bản mới đã có tính năng auto-download Node.js binary. Hãy kéo code mới nhất từ GitHub và restart server. Nếu vẫn lỗi, dùng Cách 1.</p>
                """

            warning_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Antares - Fallback</title>
                <style>
                    body{{font-family: system-ui, sans-serif;background:#0f0f10;color:#e2e8f0;margin:0;padding:20px}}
                    .alert{{background:linear-gradient(135deg,#ff4d4d,#a00);color:white;padding:20px;border-radius:12px;margin-bottom:20px;box-shadow:0 4px 20px rgba(255,0,0,0.3)}}
                    .alert-green{{background:linear-gradient(135deg,#22c55e,#16a34a);color:white;padding:16px;border-radius:12px;margin-bottom:20px}}
                    .card{{background:#1e1e20;border:1px solid #333;border-radius:12px;padding:20px;margin-bottom:16px}}
                    code{{background:#2a2a2e;padding:8px 12px;border-radius:6px;display:block;margin:8px 0;white-space:pre-wrap;word-break:break-all;color:#22d3ee;font-family:monospace}}
                    a{{color:#a78bfa;text-decoration:none}} a:hover{{text-decoration:underline}}
                    .btn{{background:#7c3aed;color:white;padding:10px 20px;border-radius:8px;display:inline-block;margin:6px 6px 6px 0;text-decoration:none}}
                    .btn-green{{background:#16a34a}}
                    .tag{{display:inline-block;background:#333;padding:4px 10px;border-radius:20px;font-size:12px;margin-right:6px}}
                </style>
            </head>
            <body>
                <div class="alert-green">
                    <h3>✅ Ngon! Ngrok đã chạy - Server Online { ' - ' + str(port) if port else '' }</h3>
                    <p>Bạn đang vào được web qua ngrok: <b>{ os.getenv('NGROK_URL', 'ngrok-free.dev') }</b> - Server đã Online giữ được!</p>
                </div>

                <div class="alert">
                    <h2>{title}</h2>
                    {main_msg}
                </div>

                <div class="card">
                    <h3>🔧 Cách Fix Nhanh (Chọn 1):</h3>
                    {fix_html}
                </div>

                <div class="card">
                    <h3>📊 Trạng Thái Hiện Tại</h3>
                    <p><span class="tag">Port: {port}</span> <span class="tag">Mode: Python Fallback</span> <span class="tag">Node: {'Có' if (ROOT / 'nodejs' / 'bin' / 'node').exists() or (ROOT / 'node-v22.11.0-linux-x64' / 'bin' / 'node').exists() else 'Thiếu?'}</span> <span class="tag">node_modules: {'✅ Có' if has_node_modules else '❌ Thiếu MODULE_NOT_FOUND'}</span></p>
                    <p>Config bots: {len(config.get('bots', []))} bot(s)</p>
                    <p>Config path: {str(ROOT / 'config.json')}</p>
                    <p><a class="btn" href="/api/bots">Xem API Bots</a> <a class="btn" href="/api/system">System Info</a> <a class="btn btn-green" href="/api/install-deps">🔄 Thử cài lại node_modules (API)</a></p>
                </div>

                <div class="card">
                    <h3>📥 Tải Bản Fix Mới</h3>
                    <p>Code mới nhất đã fix auto-install node_modules khi thiếu:</p>
                    <code>https://github.com/Fake2znzj/bunlmao/archive/refs/heads/arena/019f9eb9-bunlmao.zip</code>
                    <p>Release: <a href="https://github.com/Fake2znzj/bunlmao/releases" target="_blank">Releases</a></p>
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

    @app.route("/api/install-deps", methods=["GET", "POST"])
    def api_install_deps():
        import subprocess
        import shutil
        ROOT = Path(__file__).parent.parent.parent
        node_modules = ROOT / "node_modules"
        # Find npm
        npm_bin = shutil.which("npm") or str(ROOT / "nodejs" / "bin" / "npm") or "npm"
        try:
            # Try install
            result = subprocess.run([npm_bin, "install", "--production", "--no-fund", "--no-audit"], cwd=str(ROOT), timeout=300, capture_output=True, text=True)
            output = result.stdout[-2000:] + "\n" + result.stderr[-2000:]
            success = result.returncode == 0 and (ROOT / "node_modules" / "chalk").exists()
            return jsonify({
                "ok": success,
                "returncode": result.returncode,
                "output": output,
                "message": "Đã cài xong! Hãy restart server để chạy bot (gõ rs hoặc bấm Restart)" if success else "Cài thất bại, xem output"
            })
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/proxies/free-sources")
    def api_free_sources():
        return jsonify({
            "ok": True,
            "sources": [
                {
                    "id": "vn-proxyscrape",
                    "name": "VN Elite - Proxyscrape (SOCKS4/SOCKS5)",
                    "url": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous%2Ctransparent&country=vn",
                    "tag": "vn-proxyscrape",
                    "type": "socks5",
                    "country": "VN"
                },
                {
                    "id": "all-proxyscrape-socks",
                    "name": "All - Proxyscrape SOCKS4/5",
                    "url": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous",
                    "tag": "proxyscrape-socks",
                    "type": "socks5"
                }
            ]
        })

    @app.route("/api/proxies/fetch-vn")
    def api_fetch_vn():
        import requests
        try:
            url = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous%2Ctransparent&country=vn"
            limit = int(request.args.get("limit", 100))
            resp = requests.get(url, timeout=15)
            text = resp.text
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            # Add to config? For fallback we just return list
            # Also try to save to proxies.json? We'll store in config
            proxies = []
            for line in lines[:limit]:
                if ":" in line:
                    host, port = line.split(":", 1)
                    proxies.append({"host": host, "port": int(port), "type": "socks5", "tag": "vn-proxyscrape"})

            # Save to config.json proxies array (append)
            try:
                config_path = ROOT / "config.json"
                if config_path.exists():
                    import json
                    with open(config_path, "r", encoding="utf-8") as cf:
                        cfg = json.load(cf)
                    existing = set((p.get("host"), p.get("port")) for p in cfg.get("proxies", []))
                    added = 0
                    for p in proxies:
                        if (p["host"], p["port"]) not in existing:
                            cfg.setdefault("proxies", []).append(p)
                            added += 1
                    with open(config_path, "w", encoding="utf-8") as cf:
                        json.dump(cfg, cf, indent=2, ensure_ascii=False)
                    return jsonify({"ok": True, "count": added, "totalReceived": len(lines), "proxies": proxies[:10], "message": f"Đã thêm {added} proxy VN vào config.json"})
            except Exception as e:
                return jsonify({"ok": True, "count": len(proxies), "totalReceived": len(lines), "proxies": proxies, "warning": f"Fetch ok nhưng lưu config lỗi: {e}"})

            return jsonify({"ok": True, "count": len(proxies), "totalReceived": len(lines), "proxies": proxies})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.route("/api/status")
    def api_status():
        node_modules = ROOT / "node_modules"
        has_modules = (node_modules / "chalk").exists() and (node_modules / "mineflayer").exists()
        return jsonify({
            "ok": True,
            "nodeMissing": node_missing,
            "mode": "fallback",
            "port": port,
            "hasNodeModules": has_modules,
            "message": "Thiếu node_modules - cần npm install" if not has_modules else "Server đang chạy fallback mode"
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
