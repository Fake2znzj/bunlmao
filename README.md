# ⬡ Antares — Mine Bot Manager v2.0 (Python + Node)

A premium Minecraft bot management dashboard with CLI support. Proxy auto-detection, multi-bot orchestration, live web UI.
Now with **Python wrapper** for Pterodactyl Python egg compatibility.

## Features

- **Multi-Bot Manager** — Run dozens of bots simultaneously with staggered startup and concurrent connection limits
- **Proxy Auto-Detect** — HTTP / HTTPS / SOCKS4 / SOCKS5 with automatic type detection, health tracking, and geo enrichment
- **Live Web Dashboard** — Real-time status, logs, inventory, commands, and system metrics
- **CLI Interface** — Full command-line control alongside the web UI
- **Python Wrapper** — Entry point chính là `main.py`, tự động spawn Node engine (tương thích Pterodactyl Python egg)
- **Auto Menu** — Automatic server menu navigation and GUI handling
- **AFK Modes** — Jump and walk AFK with anti-stuck detection
- **Shard Tracking** — Auto-read shard counts from scoreboard and inventory windows
- **Per-Bot Logs** — Isolated log streams for each bot, never mixed
- **Responsive Design** — Mobile-first Glassmorphism UI with gradient background

## Quick Start

### Python (Recommended — Pterodactyl Python Egg)

```bash
pip install -r requirements.txt
npm install
python main.py
```

### Node (Legacy)

```bash
npm install
node main.js
# or
npm run start:node
```

### Windows
```bat
setup.bat
run.bat
```

### Linux / macOS
```bash
chmod +x setup.sh run.sh
./setup.sh
./run.sh
```

Open **http://localhost:3000** in your browser.

### Pterodactyl — Python Egg (Mới)

1. Tạo server với **Python 3.11** egg
2. Set `MAIN_FILE` = `main.py`
3. Startup command:
   ```bash
   python main.py
   ```
   Hoặc nếu image có cả Node + Python:
   ```bash
   pip install -r requirements.txt && npm install && python main.py
   ```
4. **Dockerfile** mới đã hỗ trợ cả Python + Node 22, chỉ cần push lên GitHub và dùng Docker image.

### Pterodactyl — Node.js 22 (Cũ, vẫn hỗ trợ)

- Use a **Node.js 22** server image
- Set `MAIN_FILE` to `main.js`
- Startup:
  ```bash
  /usr/local/bin/node /home/container/main.js
  ```

## Architecture — Python Wrapper

```
main.py (Python)
  ├─ Checks Node.js >=22
  ├─ npm install if needed
  ├─ Spawns: node main.js (BotManager + WebDashboard)
  ├─ Forwards stdin (CLI commands) -> Node
  └─ Handles SIGTERM/SIGINT + auto-restart

src/python/
  ├─ dashboard.py — Experimental pure-Python Flask fallback
```

Khi chạy `python main.py`:
- Banner đẹp bằng `rich`
- Kiểm tra Node, tự cài deps
- Launch `node main.js` trên cùng PORT
- CLI `help`, `list`, `start <id>`, `stop <id>` sẽ được forward vào Node process

Nếu muốn chạy **pure Python dashboard** không cần Node (experimental):
```bash
python main.py --python-only
```

## Configuration

Edit `config.json`:

```json
{
  "host": "server.com",
  "port": 25565,
  "version": "1.21.1",
  "ownerUsername": "YourName",
  "botPassword": "yourPassword",
  "bots": [
    {
      "id": "bot1",
      "host": "server.com",
      "port": 25565,
      "version": "1.21.1",
      "username": "BotName1",
      "botPassword": "password1",
      "useProxy": false
    }
  ],
  "proxies": [],
  "proxyAssignments": {}
}
```

| Field | Description |
|-------|-------------|
| `host` | Default Minecraft server IP |
| `port` | Default server port (25565) |
| `version` | Minecraft version string |
| `ownerUsername` | Your username for `/tpa` commands |
| `botPassword` | Password for `/dk` and `/dn` register/login |
| `bots[]` | Array of bot configurations |
| `proxies[]` | Proxy entries (managed via UI or CLI) |
| `settings.webPort` | Web dashboard port (default 3000) |

## Proxy Formats

```
http://user:pass@host:port
socks5://user:pass@host:port
host:port:user:pass          (auto-detect)
host:port                    (no auth)
```

## CLI Commands

```
help                    Show commands
list                    List all bots
start <id>              Start a bot
stop <id>               Stop a bot
cmd <id> <command>      Send command to bot
proxy list              List proxies
proxy add <string>      Add a proxy
sys                     System metrics
exit                    Shutdown
```

## Requirements

- **Python** >= 3.11 (for wrapper)
- **Node.js** >= 22 (engine)
- **npm** >= 9
- Python deps: `rich`, `requests`, `python-dotenv`, `psutil`

Install all:
```bash
pip install -r requirements.txt
npm install
```

## Project Structure

```
antares/
├── main.py                  Entry point (Python wrapper) ⭐ NEW
├── main.js                  Entry point (Node engine, called by main.py)
├── requirements.txt         Python dependencies ⭐ NEW
├── config.json              Bot & server configuration
├── package.json             Dependencies (Node + Python scripts)
├── Dockerfile               Python 3.11 + Node 22 multi-runtime ⭐ UPDATED
├── render.yaml              Python env for Render ⭐ UPDATED
└── src/
    ├── python/              Python modules ⭐ NEW
    │   ├── dashboard.py     Flask fallback dashboard
    │   └── __init__.py
    ├── core/                Core engine (Node)
    │   ├── BotSession.js
    │   ├── ProxyManager.js
    │   └── ...
    ├── services/
    │   └── BotManager.js
    └── web/
        ├── WebDashboard.js
        └── public/
```

## Deploy to Render

### Python + Node (Current)

Render `render.yaml` now uses `env: python`:
- **Build:** `pip install -r requirements.txt && npm install`
- **Start:** `python main.py`

### Blueprint (Auto Deploy)

Push to GitHub → Render → **New → Blueprint** → selects repo.

### Docker

**New → Web Service** → Docker → `Dockerfile` (python:3.11-slim + Node 22)

## License

MIT
