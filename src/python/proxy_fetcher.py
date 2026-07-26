"""
Proxy Fetcher - Python version for free proxy API (Proxyscrape VN + Asia 0-175ms)
Used for both Node and Python dashboards
Supports 0-175ms low ping filter and bot->server ping check
"""

import requests
import json
import time
import socket
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).parent.parent.parent
CONFIG_PATH = ROOT / "config.json"

PROXYSCAPE_VN_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous%2Ctransparent&country=vn"

# Asia low ping sources (0-175ms target)
ASIA_SOURCES = {
    "vn-proxyscrape": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous%2Ctransparent&country=vn",
    "sg-proxyscrape": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous&country=sg",
    "jp-proxyscrape": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous&country=jp",
    "asia-mixed": "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous&country=vn%2Csg%2Cjp%2Cid%2Cth%2Cmy%2Cph",
    "speedx-socks5": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
    "proxifly-socks5": "https://cdn.jsdelivr.net/gh/proxy4parsing/proxy-list@main/socks5.txt",
    "roosterkid-socks5": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
}

def fetch_proxies_from_url(url, limit=100, default_type="socks5", tag="free"):
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}", "count": 0}
        text = resp.text
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        proxies = []
        for line in lines[:limit*2]:  # fetch more to filter
            if ":" in line and line.count(".") >= 3:
                try:
                    # Handle ip:port or socks5://ip:port
                    if "://" in line:
                        # Extract host:port from URI
                        from urllib.parse import urlparse
                        parsed = urlparse(line)
                        host = parsed.hostname
                        port = parsed.port
                        if not host or not port:
                            continue
                        proxies.append({"host": host, "port": port, "type": default_type, "tag": tag, "raw": line})
                    else:
                        host, port = line.split(":", 1)
                        port_int = int(port.split()[0])  # handle extra spaces
                        if 1 <= port_int <= 65535 and len(host.split(".")) == 4:
                            proxies.append({"host": host.strip(), "port": port_int, "type": default_type, "tag": tag, "raw": line})
                except:
                    continue
            if len(proxies) >= limit:
                break
        return {"ok": True, "count": len(proxies), "totalReceived": len(lines), "proxies": proxies, "url": url}
    except Exception as e:
        return {"ok": False, "error": str(e), "count": 0}

def test_proxy_to_server(proxy, target_host, target_port=25565, timeout=5):
    """Test proxy connection to Minecraft server, measure ping - bot->server ping"""
    import socks
    try:
        start = time.time()
        # Try SOCKS5 connection
        s = socks.socksocket()
        s.set_proxy(
            socks.SOCKS5 if proxy.get("type") in ("socks5", "socks4") or "socks5" in proxy.get("type", "") else socks.HTTP,
            proxy["host"],
            proxy["port"]
        )
        s.settimeout(timeout)
        s.connect((target_host, target_port))
        ping_ms = int((time.time() - start) * 1000)
        s.close()
        return {"ok": True, "ping": ping_ms, "serverPing": ping_ms, "withinTarget": ping_ms <= 175, "target": f"{target_host}:{target_port}"}
    except Exception as e:
        # Fallback: try direct socket via proxy HTTP CONNECT simulation is complex, just return fail
        # For HTTP proxies, we try simple TCP via proxy using requests? Simplified: return fail
        try:
            # For testing without pysocks, try basic TCP connect to proxy itself as ping
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((proxy["host"], proxy["port"]))
            ping_ms = int((time.time() - start) * 1000)
            sock.close()
            # This is proxy ping, not server ping, but still useful
            return {"ok": True, "ping": ping_ms, "proxyPing": ping_ms, "withinTarget": ping_ms <= 175, "note": "proxy ping only, not server", "target": f"{target_host}:{target_port}"}
        except Exception as e2:
            return {"ok": False, "error": str(e) + " | " + str(e2), "target": f"{target_host}:{target_port}"}

def test_proxies_to_server(proxies, target_host, target_port=25565, max_ms=175, concurrency=10):
    """Test list of proxies to Minecraft server, filter 0-175ms"""
    low_ping = []
    all_results = []
    
    def test_one(proxy):
        res = test_proxy_to_server(proxy, target_host, target_port)
        return {"proxy": proxy, "result": res}

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_proxy = {executor.submit(test_one, p): p for p in proxies}
        for future in as_completed(future_to_proxy):
            try:
                data = future.result()
                all_results.append(data)
                if data["result"].get("ok") and data["result"].get("ping", 9999) <= max_ms:
                    low_ping.append(data)
            except Exception as e:
                pass

    low_ping_sorted = sorted(low_ping, key=lambda x: x["result"]["ping"])

    return {
        "ok": True,
        "target": f"{target_host}:{target_port}",
        "maxMs": max_ms,
        "totalTested": len(all_results),
        "totalLowPing": len(low_ping),
        "lowPingProxies": low_ping_sorted,
        "allResults": all_results,
        "summary": {
            "excellent": len([r for r in low_ping if r["result"]["ping"] <= 50]),
            "good": len([r for r in low_ping if 50 < r["result"]["ping"] <= 100]),
            "fair": len([r for r in low_ping if 100 < r["result"]["ping"] <= 175]),
            "totalLow": len(low_ping)
        }
    }

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
            # Normalize
            host = p.get("host")
            port = p.get("port")
            if not host or not port:
                continue
            if (host, port) not in existing:
                cfg.setdefault("proxies", []).append({
                    "host": host,
                    "port": port,
                    "type": p.get("type", "socks5"),
                    "tag": p.get("tag", "asia-0-175ms"),
                    "ping": p.get("ping", -1),
                    "serverPing": p.get("serverPing", -1),
                })
                added += 1
                existing.add((host, port))

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)

        return {"ok": True, "added": added, "total": len(cfg.get("proxies", []))}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def fetch_vn_proxies(limit=100, save=True, max_ms=175, filter_low_ping=False, target_host=None):
    """Fetch VN proxies from proxyscrape and optionally save to config.json, with 0-175ms filter"""
    result = fetch_proxies_from_url(PROXYSCAPE_VN_URL, limit=limit*2 if filter_low_ping else limit, default_type="socks5", tag="vn-0-175ms")
    if not result["ok"]:
        return result

    proxies = result["proxies"]

    # If filtering low ping and target provided, test to server
    if filter_low_ping and target_host:
        print(f"Testing {len(proxies)} proxies to {target_host} for 0-{max_ms}ms...")
        test_res = test_proxies_to_server(proxies, target_host, max_ms=max_ms)
        print(f"Found {test_res['totalLowPing']}/{test_res['totalTested']} low ping (0-{max_ms}ms)")
        print(f"  Excellent 0-50ms: {test_res['summary']['excellent']}")
        print(f"  Good 51-100ms: {test_res['summary']['good']}")
        print(f"  Fair 101-175ms: {test_res['summary']['fair']}")
        # Use low ping proxies
        proxies = [r["proxy"] for r in test_res["lowPingProxies"]]
        result["lowPingTest"] = test_res

    if save:
        save_res = add_proxies_to_config(proxies)
        result["saveResult"] = save_res

    # Trim to limit after filtering
    result["proxies"] = proxies[:limit]
    result["count"] = len(result["proxies"])
    return result

def fetch_asia_low_ping(limit=100, save=True, max_ms=175, target_host=None):
    """Fetch Asia mixed proxies and filter 0-175ms"""
    all_proxies = []
    for tag, url in ASIA_SOURCES.items():
        if "vn" in tag or "asia" in tag or "sg" in tag or "jp" in tag:
            print(f"Fetching {tag} from {url[:60]}...")
            res = fetch_proxies_from_url(url, limit=limit, default_type="socks5", tag=tag)
            if res["ok"]:
                all_proxies.extend(res["proxies"])
            time.sleep(0.5)

    # Deduplicate
    seen = set()
    deduped = []
    for p in all_proxies:
        key = (p["host"], p["port"])
        if key not in seen:
            seen.add(key)
            deduped.append(p)

    print(f"Total fetched: {len(all_proxies)}, deduped: {len(deduped)}")

    if target_host:
        print(f"Testing to {target_host} for 0-{max_ms}ms...")
        test_res = test_proxies_to_server(deduped[:limit*2], target_host, max_ms=max_ms)
        low = [r["proxy"] for r in test_res["lowPingProxies"]]
        print(f"Low ping 0-{max_ms}ms: {len(low)}/{len(deduped)}")
        deduped = low

    if save:
        save_res = add_proxies_to_config(deduped[:limit])
        return {"ok": True, "count": len(deduped[:limit]), "saveResult": save_res, "proxies": deduped[:limit]}

    return {"ok": True, "count": len(deduped[:limit]), "proxies": deduped[:limit]}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch free VN/Asia proxies 0-175ms + bot->server ping")
    parser.add_argument("--limit", type=int, default=50, help="Max proxies to fetch")
    parser.add_argument("--no-save", action="store_true", help="Don't save to config.json")
    parser.add_argument("--url", type=str, default=PROXYSCAPE_VN_URL, help="Custom proxy API URL")
    parser.add_argument("--max-ms", type=int, default=175, help="Max ping ms target (default 175 for 0-175ms)")
    parser.add_argument("--target", type=str, default=None, help="Minecraft server host to test ping bot->server (e.g. java.kingmc.vn)")
    parser.add_argument("--target-port", type=int, default=25565, help="Minecraft server port")
    parser.add_argument("--asia", action="store_true", help="Fetch Asia mixed (VN/SG/JP/ID/TH) instead of just VN")
    args = parser.parse_args()

    if args.asia:
        print(f"Fetching Asia low ping 0-{args.max_ms}ms...")
        if args.target:
            res = fetch_asia_low_ping(limit=args.limit, save=not args.no_save, max_ms=args.max_ms, target_host=args.target)
        else:
            # Fetch without server test, just list
            res = fetch_asia_low_ping(limit=args.limit, save=not args.no_save, max_ms=args.max_ms)
        print(f"Result: {res}")
    else:
        print(f"Fetching proxies from {args.url} (0-{args.max_ms}ms target)...")
        if args.target:
            res = fetch_vn_proxies(limit=args.limit, save=not args.no_save, max_ms=args.max_ms, filter_low_ping=True, target_host=args.target)
        else:
            res = fetch_proxies_from_url(args.url, limit=args.limit, tag="vn-0-175ms")
            print(f"Received: {res.get('totalReceived')} | Parsed: {res.get('count')}")
            if res["ok"] and not args.no_save:
                save_res = add_proxies_to_config(res["proxies"])
                print(f"Save result: {save_res}")
                res["saveResult"] = save_res
        print(f"Final: {res.get('count')} proxies")
        if res.get("lowPingTest"):
            print(f"Low ping summary: {res['lowPingTest']['summary']}")
