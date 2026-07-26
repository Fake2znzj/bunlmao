"""
Proxy Fetcher - Python version for free proxy API (Proxyscrape VN)
Used for both Node and Python dashboards
"""

import requests
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = ROOT / "config.json"

PROXYSCAPE_VN_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous%2Ctransparent&country=vn"

def fetch_proxies_from_url(url, limit=100, default_type="socks5", tag="free"):
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}", "count": 0}
        text = resp.text
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        proxies = []
        for line in lines[:limit]:
            if ":" in line and line.count(".") >= 3:
                try:
                    host, port = line.split(":", 1)
                    port_int = int(port)
                    if 1 <= port_int <= 65535:
                        proxies.append({
                            "host": host.strip(),
                            "port": port_int,
                            "type": default_type,
                            "tag": tag
                        })
                except:
                    continue
        return {"ok": True, "count": len(proxies), "totalReceived": len(lines), "proxies": proxies}
    except Exception as e:
        return {"ok": False, "error": str(e), "count": 0}

def add_proxies_to_config(proxies, config_path=None):
    config_path = Path(config_path) if config_path else CONFIG_PATH
    try:
        if not config_path.exists():
            return {"ok": False, "error": "config.json not found"}

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        existing = set((p.get("host"), p.get("port")) for p in cfg.get("proxies", []))
        added = 0
        for p in proxies:
            if (p["host"], p["port"]) not in existing:
                cfg.setdefault("proxies", []).append(p)
                added += 1
                existing.add((p["host"], p["port"]))

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

        return {"ok": True, "added": added, "total": len(cfg.get("proxies", []))}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def fetch_vn_proxies(limit=100, save=True):
    """Fetch VN proxies from proxyscrape and optionally save to config.json"""
    result = fetch_proxies_from_url(PROXYSCAPE_VN_URL, limit=limit, default_type="socks5", tag="vn-proxyscrape")
    if result["ok"] and save:
        save_res = add_proxies_to_config(result["proxies"])
        result["saveResult"] = save_res
    return result

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch free VN proxies")
    parser.add_argument("--limit", type=int, default=100, help="Max proxies to fetch")
    parser.add_argument("--no-save", action="store_true", help="Don't save to config.json")
    parser.add_argument("--url", type=str, default=PROXYSCAPE_VN_URL, help="Custom proxy API URL")
    args = parser.parse_args()

    print(f"Fetching proxies from {args.url}...")
    res = fetch_proxies_from_url(args.url, limit=args.limit, tag="vn-proxyscrape")
    print(f"Received: {res.get('totalReceived')} | Parsed: {res.get('count')}")
    if res["ok"]:
        print(f"Sample: {res['proxies'][:5]}")
        if not args.no_save:
            save_res = add_proxies_to_config(res["proxies"])
            print(f"Save result: {save_res}")
    else:
        print(f"Error: {res.get('error')}")
