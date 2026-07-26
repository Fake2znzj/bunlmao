FROM python:3.11-slim

# Install Node.js 22 + build deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Ho_Chi_Minh
ENV NODE_ENV=production
ENV PORT=3000
ENV NODE_OPTIONS="--max-old-space-size=512"
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy dep files first for caching
COPY package.json package-lock.json* requirements.txt* ./

# Install Python + Node deps
RUN pip install --no-cache-dir --upgrade pip && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi && \
    npm install --production --no-fund --no-audit && npm cache clean --force

# Copy rest
COPY . .

# Make main.py executable
RUN chmod +x main.py

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('127.0.0.1', int('${PORT}'))); s.close()" || wget -q -O- http://localhost:${PORT}/ || exit 1

# Default: run Python wrapper (which spawns Node). Compatible with Pterodactyl Python egg.
CMD ["python", "main.py"]
