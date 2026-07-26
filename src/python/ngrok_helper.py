"""
Ngrok helper for Antares - Expose dashboard via public URL
Bypass Pterodactyl firewall / Cloudflare blocking

Usage:
  NGROK_AUTHTOKEN=your_token python main.py --ngrok
  or set env in Pterodactyl: NGROK_AUTHTOKEN, NGROK_ENABLED=1

Get free token: https://dashboard.ngrok.com/get-started/your-authtoken
"""

import os
import sys
import time
import threading
from pathlib import Path

def start_ngrok_tunnel(port, authtoken=None, region="ap", use_pyngrok=True):
    """
    Start ngrok tunnel for given port
    Returns public URL or None
    """
    # Try pyngrok first (Python package)
    if use_pyngrok:
        try:
            from pyngrok import ngrok, conf
            # Set authtoken if provided
            if authtoken:
                try:
                    ngrok.set_auth_token(authtoken)
                    print(f"[Ngrok] Auth token set")
                except Exception as e:
                    print(f"[Ngrok] Auth token error: {e}")

            # Optional: set region to ap (Asia Pacific) for lower latency from VN
            # pyngrok config
            try:
                # Kill any existing tunnels
                ngrok.kill()
            except:
                pass

            print(f"[Ngrok] Starting tunnel for port {port} (region={region})...")

            # Build options
            options = {}
            if region:
                options["region"] = region  # ap, us, eu, au, sa, jp, in

            # Start HTTP tunnel
            public_url = ngrok.connect(port, "http", options=options)
            # pyngrok returns NgrokTunnel object or string
            if hasattr(public_url, 'public_url'):
                url_str = public_url.public_url
            else:
                url_str = str(public_url)

            print(f"\n{'='*60}")
            print(f"🌐 Ngrok Public URL: {url_str}")
            print(f"   Local: http://localhost:{port} -> Public: {url_str}")
            print(f"   Dùng URL này để truy cập dashboard từ bất cứ đâu, bypass firewall nvnmc.top")
            print(f"{'='*60}\n")

            # Keep thread to monitor
            def monitor():
                try:
                    while True:
                        time.sleep(60)
                        # Print stats occasionally
                        # tunnels = ngrok.get_tunnels()
                except:
                    pass

            t = threading.Thread(target=monitor, daemon=True)
            t.start()

            return url_str

        except ImportError as e:
            print(f"[Ngrok] pyngrok not installed: {e}, trying binary...")
        except Exception as e:
            print(f"[Ngrok] pyngrok failed: {e}")
            import traceback
            traceback.print_exc()

    # Fallback: try binary ngrok if exists
    try:
        import shutil
        import subprocess
        ngrok_bin = shutil.which("ngrok") or "./ngrok" or str(Path.home() / "ngrok")
        if not Path(ngrok_bin).exists() if isinstance(ngrok_bin, str) and "/" in ngrok_bin else False:
            ngrok_bin = shutil.which("ngrok")

        if ngrok_bin:
            print(f"[Ngrok] Found binary: {ngrok_bin}")
            # Set authtoken via binary
            if authtoken:
                try:
                    subprocess.run([ngrok_bin, "config", "add-authtoken", authtoken], timeout=10)
                except Exception as e:
                    print(f"[Ngrok] Binary authtoken set failed: {e}")

            # Start tunnel in background
            print(f"[Ngrok] Starting binary tunnel: {ngrok_bin} http {port} --region={region}")
            proc = subprocess.Popen([ngrok_bin, "http", str(port), f"--region={region}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # Give it time to start and fetch URL from API
            time.sleep(3)
            # Try to get public URL from ngrok API
            try:
                import requests
                resp = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
                data = resp.json()
                if data.get("tunnels"):
                    public_url = data["tunnels"][0].get("public_url")
                    print(f"\n{'='*60}")
                    print(f"🌐 Ngrok Public URL (binary): {public_url}")
                    print(f"{'='*60}\n")
                    return public_url
            except Exception as e:
                print(f"[Ngrok] Failed to get URL from API: {e}, but tunnel may still be running on port 4040")
                print(f"Check http://127.0.0.1:4040 for ngrok dashboard")
                return f"http://127.0.0.1:4040"

    except Exception as e:
        print(f"[Ngrok] Binary method failed: {e}")

    return None

def download_ngrok_binary():
    """Download ngrok binary if not exists (for Pterodactyl containers)"""
    import platform
    import shutil
    import subprocess
    import urllib.request
    from pathlib import Path

    ROOT = Path(__file__).parent.parent.parent
    ngrok_path = ROOT / "ngrok"

    if ngrok_path.exists():
        print(f"[Ngrok] Binary already exists: {ngrok_path}")
        return str(ngrok_path)

    if shutil.which("ngrok"):
        return shutil.which("ngrok")

    try:
        machine = platform.machine().lower()
        system = platform.system().lower()

        # Determine download URL
        # ngrok v3 download URLs - use v3 stable
        # https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
        if system != "linux":
            print(f"[Ngrok] Auto-download only for Linux, current: {system}")
            return None

        if machine in ("x86_64", "amd64", "x64"):
            arch = "amd64"
        elif machine in ("aarch64", "arm64"):
            arch = "arm64"
        else:
            arch = "amd64"

        # ngrok official download via bin.equinox.io
        url = f"https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-{arch}.tgz"
        print(f"[Ngrok] Downloading ngrok binary from {url}...")

        tgz_path = ROOT / "ngrok.tgz"

        # Try curl/wget first
        downloaded = False
        if shutil.which("curl"):
            try:
                subprocess.run(["curl", "-fsSL", "-o", str(tgz_path), url], timeout=60)
                if tgz_path.exists() and tgz_path.stat().st_size > 100000:
                    downloaded = True
            except:
                pass

        if not downloaded and shutil.which("wget"):
            try:
                subprocess.run(["wget", "-q", "-O", str(tgz_path), url], timeout=60)
                if tgz_path.exists():
                    downloaded = True
            except:
                pass

        if not downloaded:
            try:
                urllib.request.urlretrieve(url, str(tgz_path))
                downloaded = True
            except Exception as e:
                print(f"[Ngrok] Download failed: {e}")
                return None

        # Extract
        print(f"[Ngrok] Extracting {tgz_path}...")
        try:
            import tarfile
            with tarfile.open(str(tgz_path), "r:gz") as tar:
                tar.extractall(path=str(ROOT))
        except Exception:
            # try system tar
            try:
                subprocess.run(["tar", "-xzf", str(tgz_path), "-C", str(ROOT)], timeout=30)
            except Exception as e:
                print(f"[Ngrok] Extract failed: {e}")
                return None

        # Make executable
        try:
            import os
            os.chmod(str(ngrok_path), 0o755)
        except:
            pass

        # Cleanup
        try:
            tgz_path.unlink()
        except:
            pass

        if ngrok_path.exists():
            print(f"[Ngrok] ✅ Downloaded ngrok binary: {ngrok_path}")
            return str(ngrok_path)

    except Exception as e:
        print(f"[Ngrok] download failed: {e}")
        import traceback
        traceback.print_exc()

    return None
