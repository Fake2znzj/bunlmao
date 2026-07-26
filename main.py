#!/usr/bin/env python3
"""
⬡ Antares — Mine Bot Manager v2.0 (Python Wrapper)
Entry point Python - wraps Node.js main.js for Pterodactyl Python egg compatibility

Chức năng:
- Hiển thị banner đẹp bằng rich
- Kiểm tra Node.js >=22
- Tự động npm install nếu thiếu node_modules
- Spawn node main.js với forwarding stdin/stdout
- Xử lý tín hiệu SIGINT/SIGTERM, auto-restart
- Hỗ trợ Pterodactyl panel pipe mode (stdin not tty)

Usage:
    python main.py              # normal
    python main.py --no-install # skip npm install check
    python main.py --python-only # (future) pure python dashboard
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
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = ROOT_DIR / "config.json"
PACKAGE_JSON = ROOT_DIR / "package.json"

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

def get_node_version():
    node_bin = shutil.which("node")
    if not node_bin:
        # Try common Pterodactyl paths
        for p in ["/usr/local/bin/node", "/usr/bin/node", "/home/container/nodejs/bin/node"]:
            if Path(p).exists():
                node_bin = p
                break
    if not node_bin:
        return None, None
    try:
        result = subprocess.run([node_bin, "--version"], capture_output=True, text=True, timeout=5)
        ver = result.stdout.strip()  # v22.x.x
        return node_bin, ver
    except Exception:
        return None, None

def check_node_version(version_str):
    if not version_str:
        return False
    try:
        # v22.1.0 -> 22
        v = version_str.lstrip('v').split('.')[0]
        return int(v) >= 22
    except:
        return False

def ensure_node_modules(no_install=False):
    node_modules = ROOT_DIR / "node_modules"
    if node_modules.exists() and (node_modules / "mineflayer").exists():
        return True
    if no_install:
        return False
    rprint("[cyan]📦 node_modules thiếu — đang chạy npm install...[/cyan]")
    npm_bin = shutil.which("npm") or "/usr/local/bin/npm"
    try:
        # Use --production --no-fund --no-audit to be lightweight
        proc = subprocess.run(
            [npm_bin, "install", "--production", "--no-fund", "--no-audit"],
            cwd=str(ROOT_DIR),
            timeout=300
        )
        return proc.returncode == 0
    except Exception as e:
        rprint(f"[red]✗ npm install failed: {e}[/red]")
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
        # Ensure NODE_OPTIONS
        if "NODE_OPTIONS" not in env:
            env["NODE_OPTIONS"] = "--max-old-space-size=512"

        cmd = [self.node_bin, "main.js"]
        rprint(f"[green]⬡ Đang khởi động Node engine: {' '.join(cmd)} trên port {self.port}[/green]" if HAS_RICH else f"Starting Node: {' '.join(cmd)} port {self.port}")

        # We want Node's stdout/stderr to go directly to console (inherit)
        # but stdin as PIPE so we can forward user input
        try:
            self.proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdin=subprocess.PIPE,
                stdout=None,  # inherit
                stderr=None,
                env=env,
                bufsize=0,
            )
            return True
        except Exception as e:
            rprint(f"[red]✗ Không thể start node: {e}[/red]")
            return False

    def forward_stdin(self):
        """Forward Python stdin to Node stdin (for CLI commands like 'list', 'help')"""
        if AUTO_EXE:
            return
        # Check stdin available
        if not sys.stdin.readable():
            return
        try:
            while True:
                if self.proc is None or self.proc.poll() is not None:
                    break
                line = sys.stdin.readline()
                if not line:
                    # EOF
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
                # On Windows there's no SIGTERM same way
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

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Antares Python Wrapper")
    parser.add_argument("--no-install", action="store_true", help="Skip npm install check")
    parser.add_argument("--python-only", action="store_true", help="Run pure Python dashboard (experimental)")
    args = parser.parse_args()

    print_banner()

    cfg = load_config()
    port = get_port_from_config(cfg)

    # Python-only mode placeholder (future full Python rewrite)
    if args.python_only:
        rprint("[yellow]⚠ python-only mode is experimental - launching Flask fallback dashboard[/yellow]")
        try:
            # Try to load flask app if exists
            from src.python.dashboard import run_dashboard
            run_dashboard(port=port, config=cfg)
            return
        except ImportError as e:
            rprint(f"[red]python-only dashboard chưa sẵn sàng: {e} — fallback sang Node wrapper[/red]")

    # Check Node
    node_bin, node_ver = get_node_version()
    if not node_bin:
        rprint("[red]✗ Không tìm thấy Node.js! Vui lòng cài Node.js >=22[/red]")
        rprint("[dim]  Pterodactyl: chọn image nodejs 22 hoặc python có nodejs[/dim]" if HAS_RICH else "  Pterodactyl: use Nodejs 22 image or python with nodejs")
        rprint("  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs")
        sys.exit(1)

    rprint(f"[dim]  Node: {node_bin} {node_ver}[/dim]" if HAS_RICH else f"  Node: {node_bin} {node_ver}")

    if not check_node_version(node_ver):
        rprint(f"[yellow]⚠ Node version {node_ver} có thể quá cũ, yêu cầu >=v22. Vẫn thử chạy...[/yellow]")

    if not ensure_node_modules(no_install=args.no_install):
        rprint("[red]✗ node_modules vẫn thiếu - hãy chạy npm install thủ công[/red]")
        if not args.no_install:
            sys.exit(1)

    manager = NodeProcessManager(node_bin, port)

    # Signal handling
    def handle_signal(signum, frame):
        rprint(f"\n[cyan]Nhận tín hiệu {signum}, đang tắt...[/cyan]")
        manager.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if not manager.start():
        sys.exit(1)

    # Start stdin forwarding thread if not AUTO_EXE
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

    # Wait loop with auto-restart (max 5 restarts)
    while not manager._shutdown:
        ret = manager.wait()
        if manager._shutdown:
            break
        # Process died
        manager._restart_count += 1
        if manager._restart_count > 5:
            rprint(f"[red]✗ Node process chết quá nhiều lần ({manager._restart_count}), dừng lại[/red]")
            break
        rprint(f"[yellow]⚠ Node process thoát với mã {ret}, restart lại sau 3s (lần {manager._restart_count})...[/yellow]")
        time.sleep(3)
        if not manager.start():
            break

    rprint("[cyan]Python wrapper đã dừng.[/cyan]")

if __name__ == "__main__":
    main()
