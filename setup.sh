#!/bin/bash
# Antares - Setup Python + Node
set -e
echo "⬡ Antares Setup"
echo ""
echo "Checking Python..."
python3 --version || python --version

echo "Checking Node..."
node --version || echo "Node not found, please install Node.js >=22"

echo ""
echo "Installing Python deps..."
pip3 install -r requirements.txt || pip install -r requirements.txt

echo ""
echo "Installing Node deps..."
npm install

echo ""
echo "✅ Setup complete!"
echo "Run: python main.py  OR  ./run.sh"
