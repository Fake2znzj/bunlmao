#!/bin/bash
# Antares - Pterodactyl Startup Script (nvnmc.top fix)
# Dùng cho panel không có Node.js sẵn
set -e

echo "⬡ Antares Startup - Checking Node.js..."

# Function to check node
check_node() {
  if command -v node >/dev/null 2>&1; then
    echo "✅ Node found: $(node --version) at $(which node)"
    return 0
  fi
  # check local
  if [ -f "./nodejs/bin/node" ]; then
    echo "✅ Local Node found: $(./nodejs/bin/node --version)"
    export PATH="$PWD/nodejs/bin:$PATH"
    return 0
  fi
  if ls node-v*-linux-*/bin/node 1>/dev/null 2>&1; then
    local bin=$(ls node-v*-linux-*/bin/node | head -n 1)
    echo "✅ Local Node found: $($bin --version) at $bin"
    export PATH="$PWD/$(dirname $bin):$PATH"
    export PATH="$PWD/nodejs/bin:$PATH"
    return 0
  fi
  return 1
}

if ! check_node; then
  echo "⚠ Node.js không tìm thấy, thử cài đặt..."
  
  # Try apt-get (Debian/Ubuntu)
  if command -v apt-get >/dev/null 2>&1; then
    echo "📦 Thử apt-get install..."
    apt-get update -qq || true
    # Try nodesource
    if command -v curl >/dev/null 2>&1; then
      echo "📥 Cài NodeSource..."
      curl -fsSL https://deb.nodesource.com/setup_22.x | bash - || true
    fi
    apt-get install -y nodejs || apt-get install -y nodejs npm || true
  fi

  # Check again
  if ! check_node; then
    echo "⚠ apt-get thất bại, thử tải binary trực tiếp..."
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then
      NODE_ARCH="x64"
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
      NODE_ARCH="arm64"
    else
      NODE_ARCH="x64"
    fi
    VERSION="v22.11.0"
    URL="https://nodejs.org/dist/$VERSION/node-$VERSION-linux-$NODE_ARCH.tar.xz"
    echo "📥 Tải $URL ..."
    if command -v curl >/dev/null 2>&1; then
      curl -fsSL -o node.tar.xz "$URL" || echo "curl failed"
    elif command -v wget >/dev/null 2>&1; then
      wget -q -O node.tar.xz "$URL" || echo "wget failed"
    else
      echo "❌ Không có curl/wget để tải Node"
    fi

    if [ -f "node.tar.xz" ]; then
      echo "📦 Giải nén..."
      tar -xf node.tar.xz || echo "tar failed"
      # Setup
      EXTRACTED="node-$VERSION-linux-$NODE_ARCH"
      if [ -d "$EXTRACTED" ]; then
        mkdir -p nodejs/bin
        cp "$EXTRACTED/bin/node" nodejs/bin/node
        cp "$EXTRACTED/bin/npm" nodejs/bin/npm || true
        cp "$EXTRACTED/bin/npx" nodejs/bin/npx || true
        chmod +x nodejs/bin/*
        export PATH="$PWD/nodejs/bin:$PATH"
        echo "✅ Node installed locally: $(nodejs/bin/node --version)"
        rm -rf node.tar.xz || true
      fi
    fi
  fi
fi

check_node || echo "⚠ Vẫn không có Node, main.py sẽ chạy fallback dashboard để không crash"

echo "📦 Checking Python deps..."
pip install -r requirements.txt --break-system-packages -q || pip3 install -r requirements.txt --break-system-packages -q || pip install -r requirements.txt -q || true

echo "📦 Checking Node deps..."
if command -v npm >/dev/null 2>&1 || [ -f "./nodejs/bin/npm" ]; then
  if [ -f "./nodejs/bin/npm" ]; then
    export PATH="$PWD/nodejs/bin:$PATH"
  fi
  if [ ! -d "node_modules" ]; then
    npm install --production --no-fund --no-audit || ./nodejs/bin/npm install --production --no-fund --no-audit || true
  fi
else
  echo "⚠ npm không có, bỏ qua"
fi

echo "🚀 Starting Antares..."
# Port priority: cli arg > PORT > SERVER_PORT > 26270 > 3000
# SERVER_PORT is Pterodactyl allocation (e.g. 26270) - use it if PORT not set
if [ -z "$PORT" ] && [ -n "$SERVER_PORT" ]; then
  # If Pterodactyl gives us a port, respect it, but user wants 26270 default
  # Only override if user didn't explicitly want 26270? We keep SERVER_PORT if it exists
  export PORT=$SERVER_PORT
  echo "ℹ️ Using Pterodactyl SERVER_PORT as PORT: $PORT"
fi
export PORT=${PORT:-26270}
export SERVER_PORT=${SERVER_PORT:-$PORT}
echo "📡 Dashboard will run on port: $PORT (config webPort will be updated)"
echo "   If you want different port: PORT=3000 bash startup.sh or python main.py --port 26270"

# Ngrok support: set NGROK_AUTHTOKEN env to enable public URL
# Example: NGROK_AUTHTOKEN=2abc... NGROK_ENABLED=1 bash startup.sh
# Or: NGROK_AUTHTOKEN=xxx python main.py --ngrok --port $PORT
if [ -n "$NGROK_AUTHTOKEN" ] || [ "$NGROK_ENABLED" = "1" ] || [ "$USE_NGROK" = "1" ]; then
  echo "🌐 Ngrok enabled! Token: ${NGROK_AUTHTOKEN:0:10}... Region: ${NGROK_REGION:-ap}"
  echo "   Dashboard will be exposed via public URL (bypass firewall)"
  NGROK_ARGS="--ngrok --ngrok-region ${NGROK_REGION:-ap}"
  if [ -n "$NGROK_AUTHTOKEN" ]; then
    NGROK_ARGS="$NGROK_ARGS --ngrok-token $NGROK_AUTHTOKEN"
  fi
else
  NGROK_ARGS=""
  echo "   Tip: Set NGROK_AUTHTOKEN to get public URL: NGROK_AUTHTOKEN=xxx NGROK_ENABLED=1 bash startup.sh"
  echo "   Get free token: https://dashboard.ngrok.com/get-started/your-authtoken"
fi

# Try python3 first, then python
if command -v python3 >/dev/null 2>&1; then
  python3 main.py --port $PORT $NGROK_ARGS
else
  python main.py --port $PORT $NGROK_ARGS
fi
