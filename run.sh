#!/bin/bash
# Antares - Run with Python wrapper
set -e
echo "⬡ Starting Antares (Python wrapper)..."
if [ -f requirements.txt ]; then
  echo "📦 Checking Python deps..."
  pip install -r requirements.txt -q || pip3 install -r requirements.txt -q || true
fi
if [ ! -d "node_modules" ]; then
  echo "📦 Installing Node deps..."
  npm install --production --no-fund --no-audit
fi
python3 main.py || python main.py
