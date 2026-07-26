#!/usr/bin/env python3
"""
⬡ Antares — Mine Bot Manager v2.0 (Python Wrapper)
Entry point Python - wraps Node.js main.js for Pterodactyl Python egg compatibility

Fixed for nvnmc.top panel: auto-download Node.js if missing, fallback to Python dashboard to avoid crash loop.

Usage:
    python main.py              # auto-download node if needed
    python main.py --no-install # skip npm install check
    python main.py --python-only # pure python dashboard
    AUTO_EXE=1 python main.py   # auto mode (no CLI)
"""

import os
import sys
import json
import shutil
import subprocess
import threading
import signal
import time
import platform
import glob
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = ROOT_DIR / "config.json"

AUTO_EXE = os.getenv("AUTO_EXE", "0") == "1"
PORT = int(os.getenv("PORT", "0") or 0) or None

# Try rich, fallback to plain
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rprint
    console = Console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    console = None
    def rprint(*args, **kwargs):
        print(*args, **kwargs)

def print_banner():
    if HAS_RICH:
        banner_text = Text()
        banner_text.append("✦  A N T A R E S  ✦\n", style="bold cyan")
        banner_text.append("Mine Bot Manager  •  v2.0 (Python)\n", style="bold white")
        banner_text.append("Made By Antares", style="dim")
        console.print(Panel(banner_text, border_style="bright_magenta", padding=(1,2), width=48))
        console.print(f"[cyan]⬡ Python Wrapper — Node engine via subprocess[/cyan]")
    else:
        width = 44
        print("")
        print("╔" + "═"*width + "╗")
        print("║" + "✦  A N T A R E S  ✦".center(width) + "║")
        print("║" + "Mine Bot Manager  •  v2.0 (Python)".center(width) + "║")
        print("╠" + "═"*width + "╣")
        print("║" + "Made By Antares".center(width) + "║")
        print("╚" + "═"*width + "╝")
        print("")

def load_config():
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        rprint(f"[yellow]⚠ Không đọc được config.json: {e}[/yellow]" if HAS_RICH else f"Warn: {e}")
    return {}

def safe_path_check(p):
    """Check if path exists and is file, handling PermissionError gracefully"""
    try:
        # Use os.stat with try/except to avoid PermissionError crash on /root/*
        # Also handle broken symlinks
        path_obj = Path(p)
        # First quick lexists-ish via os.path.lexists to avoid stat on forbidden dir?
        # os.path.exists also calls stat, can raise PermissionError in some Python versions
        # So wrap in broad try
        if not os.path.lexists(p):
            return False
        # Now try to check if it's file
        try:
            st = path_obj.stat()
        except (PermissionError, OSError, FileNotFoundError):
            return False
        # Must be file
        if not path_obj.is_file():
            # is_file can also raise PermissionError, double check
            return False
        # Check size > 1KB to filter empty files
        try:
            if st.st_size < 1000:
                # still allow if it's symlink to real node? check later via version
                pass
        except:
            pass
        return True
    except (PermissionError, OSError, ValueError, RuntimeError):
        return False

def find_node_bin():
    """Find node binary in many possible locations - permission safe"""
    candidates = []
    # which
    try:
        w = shutil.which("node")
        if w:
            candidates.append(w)
    except:
        pass
    try:
        w = shutil.which("nodejs")
        if w:
            candidates.append(w)
    except:
        pass

    # common paths - ONLY user-writable or safe paths, SKIP /root entirely
    common = [
        "/usr/local/bin/node",
        "/usr/bin/node",
        "/bin/node",
        "/home/container/nodejs/bin/node",
        "/home/container/.local/nodejs/bin/node",
        "/home/container/.local/bin/node",
        "/opt/nodejs/bin/node",
        str(ROOT_DIR / "nodejs" / "bin" / "node"),
        str(ROOT_DIR / "node-v22.11.0-linux-x64" / "bin" / "node"),
        str(ROOT_DIR / "node-v22.11.0-linux-arm64" / "bin" / "node"),
        str(ROOT_DIR / "local_node" / "bin" / "node"),
        str(ROOT_DIR / ".local" / "bin" / "node"),
        str(ROOT_DIR / "node-v22.9.0-linux-x64" / "bin" / "node"),
        str(ROOT_DIR / "node-v20.18.0-linux-x64" / "bin" / "node"),
    ]
    candidates.extend(common)

    # glob for any node-v*-linux-*/bin/node - only inside ROOT_DIR and /home/container
    for pattern in [
        str(ROOT_DIR / "node-v*-linux-*" / "bin" / "node"),
        str(ROOT_DIR / "node-*" / "bin" / "node"),
        str(ROOT_DIR / "nodejs" / "bin" / "node"),
        "/home/container/node-v*/bin/node",
        "/home/container/nodejs/bin/node",
    ]:
        try:
            for match in glob.glob(pattern):
                candidates.append(match)
        except (PermissionError, OSError):
            pass

    # dedup preserve order
    seen = set()
    uniq = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)

    for c in uniq:
        # safe check first
        if not safe_path_check(c):
            continue
        p = Path(c)
        try:
            os.chmod(c, 0o755)
        except (PermissionError, OSError):
            pass
        # quick check version
        try:
            res = subprocess.run([c, "--version"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip().startswith("v"):
                return c
        except (PermissionError, OSError, FileNotFoundError, subprocess.SubprocessError):
            # try size check as fallback
            try:
                if p.stat().st_size > 1000000:
                    return c
            except (PermissionError, OSError):
                continue
    return None

def download_node_binary():
    """Download Node.js 22.x binary tar.xz and extract to ./nodejs"""
    try:
        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64", "x64", "x86-64"):
            node_arch = "x64"
        elif machine in ("aarch64", "arm64", "armv8"):
            node_arch = "arm64"
        else:
            node_arch = "x64"
            rprint(f"[yellow]⚠ Arch {machine} không nhận diện, dùng x64[/yellow]")

        version = "v22.11.0"  # LTS
        # fallback versions if first fails
        versions_to_try = ["v22.11.0", "v22.9.0", "v20.18.0"]
        base_url = "https://nodejs.org/dist"

        tar_path = None
        extracted_bin = None

        for ver in versions_to_try:
            url = f"{base_url}/{ver}/node-{ver}-linux-{node_arch}.tar.xz"
            rprint(f"[cyan]📥 Đang thử tải Node.js {ver} ({node_arch}): {url}[/cyan]")
            tar_name = f"node-{ver}-linux-{node_arch}.tar.xz"
            tar_path = ROOT_DIR / tar_name

            downloaded = False
            # Try curl
            if shutil.which("curl"):
                try:
                    rprint("[dim]  Dùng curl...[/dim]" if HAS_RICH else "  curl...")
                    proc = subprocess.run(["curl", "-fsSL", "-o", str(tar_path), url], timeout=180)
                    if proc.returncode == 0 and tar_path.exists() and tar_path.stat().st_size > 1000000:
                        downloaded = True
                except Exception as e:
                    rprint(f"[yellow]curl thất bại: {e}[/yellow]")

            # Try wget
            if not downloaded and shutil.which("wget"):
                try:
                    rprint("[dim]  Dùng wget...[/dim]" if HAS_RICH else "  wget...")
                    proc = subprocess.run(["wget", "-q", "-O", str(tar_path), url], timeout=180)
                    if proc.returncode == 0 and tar_path.exists() and tar_path.stat().st_size > 1000000:
                        downloaded = True
                except Exception as e:
                    rprint(f"[yellow]wget thất bại: {e}[/yellow]")

            # Python urllib fallback
            if not downloaded:
                try:
                    import urllib.request
                    rprint("[dim]  Dùng Python urllib...[/dim]" if HAS_RICH else "  urllib...")
                    # with progress-ish
                    urllib.request.urlretrieve(url, str(tar_path))
                    if tar_path.exists():
                        downloaded = True
                except Exception as e:
                    rprint(f"[yellow]urllib thất bại: {e}[/yellow]")

            if not downloaded:
                rprint(f"[red]✗ Không tải được {ver}, thử version khác...[/red]")
                try:
                    if tar_path.exists():
                        tar_path.unlink()
                except:
                    pass
                continue

            # Extract
            rprint(f"[cyan]📦 Giải nén {tar_path.name}...[/cyan]")
            extract_ok = False
            # Method 1: python tarfile
            try:
                import tarfile
                with tarfile.open(str(tar_path), "r:xz") as tar:
                    tar.extractall(path=str(ROOT_DIR))
                extract_ok = True
            except Exception as e:
                rprint(f"[yellow]Python tarfile thất bại: {e}, thử tar command...[/yellow]")
                try:
                    proc = subprocess.run(["tar", "-xf", str(tar_path), "-C", str(ROOT_DIR)], timeout=120)
                    if proc.returncode == 0:
                        extract_ok = True
                except Exception as e2:
                    rprint(f"[red]tar command thất bại: {e2}[/red]")

            if not extract_ok:
                continue

            # Find extracted node bin
            extracted_dir = ROOT_DIR / f"node-{ver}-linux-{node_arch}"
            node_bin = extracted_dir / "bin" / "node"
            if node_bin.exists():
                extracted_bin = node_bin
                version = ver  # keep successful version
                break
            else:
                rprint(f"[red]Không tìm thấy {node_bin} sau giải nén[/red]")

        if not extracted_bin or not extracted_bin.exists():
            rprint("[red]✗ Thất bại download Node.js sau nhiều lần thử[/red]")
            return None

        # Setup nodejs dir symlink/copy
        try:
            nodejs_dir = ROOT_DIR / "nodejs"
            bin_dir = nodejs_dir / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            # copy binaries
            for bname in ["node", "npm", "npx"]:
                src = extracted_bin.parent / bname
                dst = bin_dir / bname
                if src.exists():
                    try:
                        shutil.copy2(str(src), str(dst))
                        os.chmod(str(dst), 0o755)
                    except Exception as e:
                        rprint(f"[yellow]Copy {bname} lỗi: {e}[/yellow]")
            # also create local_node for compatibility
            rprint(f"[green]✅ Đã cài Node.js {version} tại {extracted_bin}[/green]")
            rprint(f"[green]   -> {bin_dir / 'node'}[/green]")
        except Exception as e:
            rprint(f"[yellow]Setup nodejs dir lỗi: {e}[/yellow]")

        # cleanup tar
        try:
            if tar_path and tar_path.exists():
                tar_path.unlink()
        except:
            pass

        return str(extracted_bin)

    except Exception as e:
        rprint(f"[red]download_node_binary lỗi: {e}[/red]")
        import traceback
        traceback.print_exc()
        return None

def get_node_version():
    node_bin = find_node_bin()
    if not node_bin:
        # Try auto download
        rprint("[yellow]⚠ Không tìm thấy Node.js, thử tự động cài đặt...[/yellow]")
        node_bin = download_node_binary()
        if not node_bin:
            # Try again find after download
            node_bin = find_node_bin()

    if not node_bin:
        return None, None
    try:
        result = subprocess.run([node_bin, "--version"], capture_output=True, text=True, timeout=5)
        ver = result.stdout.strip()
        return node_bin, ver
    except Exception:
        return node_bin, "unknown"

def check_node_version(version_str):
    if not version_str or version_str == "unknown":
        return True  # allow unknown to try
    try:
        v = version_str.lstrip('v').split('.')[0]
        return int(v) >= 18  # allow >=18, ideally >=22 but be lenient for auto-downloaded
    except:
        return False

def ensure_node_modules(no_install=False):
    node_modules = ROOT_DIR / "node_modules"
    if node_modules.exists() and (node_modules / "mineflayer").exists():
        return True
    if no_install:
        return False
    rprint("[cyan]📦 node_modules thiếu — đang chạy npm install...[/cyan]")
    node_bin = find_node_bin()
    # Find npm
    npm_bin = None
    if node_bin:
        # npm usually sibling to node
        possible_npm = Path(node_bin).parent / "npm"
        if possible_npm.exists():
            npm_bin = str(possible_npm)
    if not npm_bin:
        npm_bin = shutil.which("npm")
    if not npm_bin:
        npm_bin = "/usr/local/bin/npm"
        if not Path(npm_bin).exists():
            npm_bin = str(ROOT_DIR / "nodejs" / "bin" / "npm")
    if not Path(npm_bin).exists() if npm_bin else True:
        npm_bin = "npm"  # fallback to PATH

    try:
        # Use node to run npm if needed: node /path/to/npm-cli.js install
        if "npm" in npm_bin and Path(npm_bin).exists():
            cmd = [npm_bin, "install", "--production", "--no-fund", "--no-audit"]
        else:
            # try npx or node
            if node_bin:
                cmd = [node_bin, str(Path(npm_bin).parent / "npm-cli.js" if Path(npm_bin).exists() else npm_bin), "install", "--production", "--no-fund", "--no-audit"]
                # simpler: use npm bin as string
                cmd = [npm_bin, "install", "--production", "--no-fund", "--no-audit"]
            else:
                cmd = [npm_bin, "install", "--production", "--no-fund", "--no-audit"]

        rprint(f"[dim]Chạy: {' '.join(cmd)}[/dim]" if HAS_RICH else f"Running: {' '.join(cmd)}")
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            timeout=300
        )
        return proc.returncode == 0
    except Exception as e:
        rprint(f"[red]✗ npm install failed: {e}[/red]")
        # Try alternative: node npm install
        try:
            if node_bin:
                # find npm-cli.js
                npm_cli_candidates = [
                    Path(node_bin).parent.parent / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js",
                    ROOT_DIR / "nodejs" / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js",
                    Path(f"node-v22.11.0-linux-x64/lib/node_modules/npm/bin/npm-cli.js"),
                ]
                for cli in npm_cli_candidates:
                    if cli.exists():
                        proc = subprocess.run([node_bin, str(cli), "install", "--production", "--no-fund", "--no-audit"], cwd=str(ROOT_DIR), timeout=300)
                        return proc.returncode == 0
        except Exception as e2:
            rprint(f"[red]npm fallback failed: {e2}[/red]")
        return False

def get_port_from_config(cfg):
    if PORT:
        return PORT
    if cfg.get("settings", {}).get("webPort"):
        return cfg["settings"]["webPort"]
    return 3000

class NodeProcessManager:
    def __init__(self, node_bin, port):
        self.node_bin = node_bin
        self.port = port
        self.proc = None
        self._shutdown = False
        self._restart_count = 0

    def start(self):
        env = os.environ.copy()
        env["PORT"] = str(self.port)
        if "NODE_OPTIONS" not in env:
            env["NODE_OPTIONS"] = "--max-old-space-size=512"

        cmd = [self.node_bin, "main.js"]
        rprint(f"[green]⬡ Đang khởi động Node engine: {' '.join(cmd)} trên port {self.port}[/green]" if HAS_RICH else f"Starting Node: {' '.join(cmd)} port {self.port}")

        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdin=subprocess.PIPE,
                stdout=None,
                stderr=None,
                env=env,
                bufsize=0,
            )
            return True
        except Exception as e:
            rprint(f"[red]✗ Không thể start node: {e}[/red]")
            return False

    def forward_stdin(self):
        if AUTO_EXE:
            return
        if not sys.stdin.readable():
            return
        try:
            while True:
                if self.proc is None or self.proc.poll() is not None:
                    break
                line = sys.stdin.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                if self.proc.stdin and not self.proc.stdin.closed:
                    try:
                        self.proc.stdin.write(line.encode())
                        self.proc.stdin.flush()
                    except BrokenPipeError:
                        break
        except Exception:
            pass

    def wait(self):
        if not self.proc:
            return -1
        try:
            return self.proc.wait()
        except KeyboardInterrupt:
            return self.proc.poll() or 0

    def shutdown(self):
        self._shutdown = True
        if self.proc and self.proc.poll() is None:
            rprint("[cyan]  Shutting down Node process...[/cyan]")
            try:
                if sys.platform != "win32":
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                else:
                    self.proc.terminate()
            except Exception:
                pass

def run_python_fallback_dashboard(port, cfg, reason="Node.js không khả dụng"):
    """Fallback dashboard to keep server online instead of crash loop"""
    rprint(f"[yellow]⚠ {reason} — Chuyển sang Python-only dashboard để giữ server online[/yellow]")
    rprint(f"[cyan] Dashboard tạm sẽ chạy tại http://0.0.0.0:{port} (không có bot, chỉ giữ server không crash)[/cyan]")
    rprint("[dim] Để fix, thêm vào Startup Command của Pterodactyl:[/dim]" if HAS_RICH else "Fix:")
    rprint("  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs && python main.py")
    rprint("Hoặc upload bản có sẵn Node hoặc đổi sang Docker image python:3.11 + node:22")

    try:
        from src.python.dashboard import run_dashboard
        run_dashboard(port=port, config=cfg, node_missing=True)
    except ImportError as e:
        rprint(f"[red]Flask không có: {e}, thử cài...[/red]")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "flask", "--break-system-packages", "-q"], timeout=60)
            from src.python.dashboard import run_dashboard
            run_dashboard(port=port, config=cfg, node_missing=True)
            return
        except Exception as e2:
            rprint(f"[red]Fallback dashboard import lỗi: {e2}[/red]")

        # Ultimate fallback: simple HTTP server that stays alive
        rprint("[yellow]Chạy HTTP server tối thiểu để giữ online...[/yellow]")
        try:
            from http.server import HTTPServer, BaseHTTPRequestHandler
            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    html = f"""
                    <html><head><title>Antares - Node Missing</title></head>
                    <body style="font-family:sans-serif;background:#111;color:#eee;text-align:center;padding:50px">
                    <h1>⚠ Antares - Node.js Missing</h1>
                    <p>{reason}</p>
                    <p>Port: {port}</p>
                    <p>Vui lòng cài Node.js >=22:</p>
                    <code>curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs</code>
                    <p>Hoặc đổi Startup Command thành:</p>
                    <code>curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs && npm install && python main.py</code>
                    <p>Server vẫn online để bạn fix.</p>
                    </body></html>
                    """
                    self.wfile.write(html.encode())
                def log_message(self, *args):
                    pass

            server = HTTPServer(("0.0.0.0", port), Handler)
            rprint(f"[green]Minimal HTTP server running on 0.0.0.0:{port} - giữ online vô hạn[/green]")
            server.serve_forever()
        except Exception as e:
            rprint(f"[red]Minimal server lỗi: {e}[/red]")
            # Final: sleep loop to keep alive
            rprint("[yellow]Sleep loop giữ server online...[/yellow]")
            while True:
                time.sleep(60)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Antares Python Wrapper")
    parser.add_argument("--no-install", action="store_true", help="Skip npm install check")
    parser.add_argument("--python-only", action="store_true", help="Run pure Python dashboard (experimental)")
    parser.add_argument("--no-node-download", action="store_true", help="Don't auto-download Node.js if missing")
    args = parser.parse_args()

    print_banner()

    cfg = load_config()
    port = get_port_from_config(cfg)

    if args.python_only:
        rprint("[yellow]⚠ python-only mode - launching Flask dashboard[/yellow]")
        try:
            from src.python.dashboard import run_dashboard
            run_dashboard(port=port, config=cfg)
            return
        except Exception as e:
            rprint(f"[red]python-only dashboard lỗi: {e} — fallback[/red]")

    # Check Node
    node_bin, node_ver = get_node_version()

    if not node_bin:
        if args.no_node_download:
            rprint("[red]✗ Không tìm thấy Node.js và --no-node-download được bật[/red]")
            run_python_fallback_dashboard(port, cfg, reason="Không tìm thấy Node.js")
            return
        # get_node_version already tried download, but if still None, fallback
        rprint("[red]✗ Không tìm thấy Node.js sau khi thử tự động tải![/red]")
        rprint("[dim]Thử cách thủ công:[/dim]" if HAS_RICH else "Manual fix:")
        rprint("  1. Đổi image Pterodactyl sang nodejs 22")
        rprint("  2. Hoặc thêm vào Startup: curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs && python main.py")
        run_python_fallback_dashboard(port, cfg, reason="Không tìm thấy Node.js sau auto-download")
        return

    rprint(f"[dim]  Node: {node_bin} {node_ver}[/dim]" if HAS_RICH else f"  Node: {node_bin} {node_ver}")

    if not check_node_version(node_ver):
        rprint(f"[yellow]⚠ Node version {node_ver} hơi cũ, yêu cầu >=22. Vẫn thử chạy...[/yellow]")

    if not ensure_node_modules(no_install=args.no_install):
        rprint("[yellow]⚠ node_modules vẫn thiếu - thử tiếp tục, có thể crash nhưng sẽ fallback[/yellow]")
        # don't exit, try to run anyway, fallback will handle

    manager = NodeProcessManager(node_bin, port)

    def handle_signal(signum, frame):
        rprint(f"\n[cyan]Nhận tín hiệu {signum}, đang tắt...[/cyan]")
        manager.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if not manager.start():
        rprint("[red]Không start được Node, fallback Python dashboard[/red]")
        run_python_fallback_dashboard(port, cfg, reason="Không start được Node process")
        return

    stdin_thread = None
    if not AUTO_EXE and sys.stdin and sys.stdin.readable():
        stdin_thread = threading.Thread(target=manager.forward_stdin, daemon=True)
        stdin_thread.start()
        if HAS_RICH:
            console.print(f"[dim]Dashboard: http://localhost:{port} | Gõ 'help' để xem lệnh | AUTO_EXE={AUTO_EXE}[/dim]")
        else:
            print(f"Dashboard: http://localhost:{port}")
    else:
        if HAS_RICH:
            console.print(f"[dim]Dashboard: http://localhost:{port} | AUTO_EXE mode — CLI tắt, dùng web UI[/dim]")
        else:
            print(f"Dashboard running on port {port} (AUTO_EXE mode)")

    while not manager._shutdown:
        ret = manager.wait()
        if manager._shutdown:
            break
        manager._restart_count += 1
        if manager._restart_count > 5:
            rprint(f"[red]✗ Node process chết quá nhiều lần ({manager._restart_count}), chuyển sang fallback dashboard[/red]")
            run_python_fallback_dashboard(port, cfg, reason=f"Node crash {manager._restart_count} lần")
            break
        rprint(f"[yellow]⚠ Node process thoát mã {ret}, restart sau 3s (lần {manager._restart_count})...[/yellow]")
        time.sleep(3)
        if not manager.start():
            rprint("[red]Restart thất bại, fallback[/red]")
            run_python_fallback_dashboard(port, cfg, reason="Node restart thất bại")
            break

    rprint("[cyan]Python wrapper đã dừng.[/cyan]")

if __name__ == "__main__":
    main()
