# ⬡ Antares — Mine Bot Manager v2.0

A premium Minecraft bot management dashboard with CLI support. Proxy auto-detection, multi-bot orchestration, live web UI.

## Features

- **Multi-Bot Manager** — Run dozens of bots simultaneously with staggered startup and concurrent connection limits
- **Proxy Auto-Detect** — HTTP / HTTPS / SOCKS4 / SOCKS5 with automatic type detection, health tracking, and geo enrichment
- **Live Web Dashboard** — Real-time status, logs, inventory, commands, and system metrics
- **CLI Interface** — Full command-line control alongside the web UI
- **Auto Menu** — Automatic server menu navigation and GUI handling
- **AFK Modes** — Jump and walk AFK with anti-stuck detection
- **Shard Tracking** — Auto-read shard counts from scoreboard and inventory windows
- **Per-Bot Logs** — Isolated log streams for each bot, never mixed
- **Responsive Design** — Mobile-first Glassmorphism UI with gradient background

## Quick Start

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

### Manual
```bash
npm install
node main.js
```

Open **http://localhost:3000** in your browser.

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

- **Node.js** >= 18
- **npm** >= 9

## Project Structure

```
antares/
├── main.js                  Entry point
├── config.json              Bot & server configuration
├── package.json             Dependencies
├── setup.sh / setup.bat     Install scripts
├── run.sh / run.bat         Launch scripts
└── src/
    ├── core/                Core engine
    │   ├── BotSession.js    Bot lifecycle & events
    │   ├── ProxyManager.js  Proxy management & detection
    │   ├── CommandRegistry.js
    │   ├── WindowRouter.js  Minecraft GUI handling
    │   ├── PacketMonitor.js Packet rate tracking
    │   ├── constants.js     Timing & config constants
    │   └── utils.js         Utility functions
    ├── services/
    │   └── BotManager.js    Bot orchestration
    └── web/
        ├── WebDashboard.js  Express + Socket.io server
        └── public/          Frontend assets
```

## Deploy to Render

### 1. Blueprint (Auto Deploy)

Push this repo to GitHub, then in Render dashboard:

**New → Blueprint** → select your repo → Render reads `render.yaml` automatically.

### 2. Docker

**New → Web Service** → Docker → point to `Dockerfile`.

### 3. Manual

**New → Web Service** → Node:
- **Build Command:** `npm install`
- **Start Command:** `node main.js`

Render injects `PORT` env var automatically. The app prioritizes `process.env.PORT`.

> Free tier spins down after inactivity. Use Starter plan for 24/7 uptime.

## License

MIT
