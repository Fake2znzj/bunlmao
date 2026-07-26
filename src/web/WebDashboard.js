'use strict';
const fs = require('fs');
const path = require('path');
class WebDashboard {
  constructor(botManager, options = {}) {
    this.manager = botManager;
    this.expressApp = options.expressApp;
    this.io = options.io;
    this.expressServer = options.expressServer;
    this.port = process.env.PORT || options.port || 3000;
    this.autoExe = options.autoExe || false;
    this._prevStatusSnap = '';
    this._statusInterval = null;
    this._metricsInterval = null;
  }
  start() {
    if (!this.expressApp || !this.io) {
      console.log('[Dashboard] express/socket.io không khả dụng');
      return;
    }
    this._prevStatusSnap = '';
    const publicDir = path.join(__dirname, 'public');
    try {
      fs.mkdirSync(path.join(publicDir, 'assets'), { recursive: true });
    } catch { }
    this.expressApp.use(require('express').static(publicDir, {
      maxAge: 0,
      setHeaders: (res) => {
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Cache-Control', 'no-cache');
      },
    }));
    this.expressApp.get('/', (req, res) => {
      res.setHeader('Cache-Control', 'no-cache');
      res.sendFile(path.join(publicDir, 'index.html'));
    });
    this.expressApp.use(require('express').json());
    this.expressApp.use('/api', (req, res, next) => {
      res.setHeader('Access-Control-Allow-Origin', '*');
      res.setHeader('Access-Control-Allow-Methods', 'GET,POST,PATCH,DELETE,OPTIONS');
      res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
      if (req.method === 'OPTIONS') return res.sendStatus(200);
      next();
    });
    const _rateMap = new Map();
    const _rateLimit = (key, maxPerSec = 5) => {
      const now = Date.now();
      const bucket = _rateMap.get(key) || [];
      const recent = bucket.filter(t => now - t < 1000);
      recent.push(now);
      _rateMap.set(key, recent);
      return recent.length <= maxPerSec;
    };
    this._rateCleanup = setInterval(() => {
      const cutoff = Date.now() - 5000;
      for (const [key, bucket] of _rateMap) {
        const filtered = bucket.filter(t => t > cutoff);
        if (filtered.length) _rateMap.set(key, filtered);
        else _rateMap.delete(key);
      }
    }, 30000);
    if (this._rateCleanup.unref) this._rateCleanup.unref();
    this.expressApp.get('/api/bots', (req, res) => {
      res.json(this.manager.bots.map(b => b.getSummary()));
    });
    this.expressApp.post('/api/bots/all/cmd', (req, res) => {
      const { cmd } = req.body || {};
      if (!cmd) return res.status(400).json({ error: 'cmd required' });
      for (const b of this.manager.bots) b.cmd(String(cmd));
      res.json({ ok: true, count: this.manager.bots.length });
    });
    this.expressApp.post('/api/bots/all/start', (req, res) => {
      this.manager.startAll();
      res.json({ ok: true, count: this.manager.bots.length });
    });
    this.expressApp.post('/api/bots/all/stop', (req, res) => {
      this.manager.stopAll();
      res.json({ ok: true, count: this.manager.bots.length });
    });
    this.expressApp.get('/api/bots/:id', (req, res) => {
      const b = this.manager.findBot(req.params.id);
      if (!b) return res.status(404).json({ error: 'Not found' });
      res.json({
        ...b.getSummary(),
        logs: b.getLogs(),
        inventory: b.state.inventory,
        customCmds: b.cmdRegistry.getCustomCmds(),
      });
    });
    this.expressApp.post('/api/bots/:id/cmd', (req, res) => {
      const b = this.manager.findBot(req.params.id);
      if (!b) return res.status(404).json({ error: 'Not found' });
      const { cmd } = req.body || {};
      if (!cmd) return res.status(400).json({ error: 'cmd required' });
      b.cmd(String(cmd));
      res.json({ ok: true });
    });
    this.expressApp.post('/api/bots/:id/reconnect', (req, res) => {
      const b = this.manager.findBot(req.params.id);
      if (!b) return res.status(404).json({ error: 'Not found' });
      b.forceReconnect();
      res.json({ ok: true });
    });
    this.expressApp.post('/api/bots/:id/start', (req, res) => {
      const b = this.manager.findBot(req.params.id);
      if (!b) return res.status(404).json({ error: 'Not found' });
      if (b.isConnected || b.isReconnecting) {
        return res.status(409).json({ error: 'Bot đang chạy' });
      }
      b._disabled = false;
      b.state.reconnects = 0;
      b.start();
      if (this.io) this.io.emit('botState', { id: b.cfg.id, state: b.state.connState });
      res.json({ ok: true });
    });
    this.expressApp.post('/api/bots/:id/stop', (req, res) => {
      const b = this.manager.findBot(req.params.id);
      if (!b) return res.status(404).json({ error: 'Not found' });
      b.shutdown();
      if (this.io) this.io.emit('botState', { id: b.cfg.id, state: b.state.connState });
      res.json({ ok: true });
    });
    this.expressApp.delete('/api/bots/:id', (req, res) => {
      const bot = this.manager.removeBot(req.params.id);
      if (!bot) return res.status(404).json({ error: 'Not found' });
      if (this.io) this.io.emit('botRemoved', { id: req.params.id });
      res.json({ ok: true });
    });
    this.expressApp.patch('/api/bots/:id', (req, res) => {
      const b = this.manager.findBot(req.params.id);
      if (!b) return res.status(404).json({ error: 'Not found' });
      const allowed = ['autoMenu', 'menuCommand', 'respawn', 'ownerUsername', 'botPassword', 'useProxy', 'sendClientSettings', 'skipValidation', 'viewDistance', 'host', 'port', 'version', 'username'];
      const needsRestart = ['host', 'port', 'version', 'username'];
      let willNeedRestart = false;
      for (const k of allowed) {
        if (req.body[k] !== undefined) {
          b.cfg[k] = req.body[k];
          if (needsRestart.includes(k) && (b.isConnected || b.isReconnecting)) {
            willNeedRestart = true;
          }
        }
      }
      this._syncBotToConfig(b);
      res.json({
        ok: true,
        needsRestart: willNeedRestart,
        warning: willNeedRestart ? 'Thay đổi host/port/version/username cần restart bot để có hiệu lực' : undefined,
        cfg: { autoMenu: b.cfg.autoMenu, menuCommand: b.cfg.menuCommand, respawn: b.cfg.respawn, ownerUsername: b.cfg.ownerUsername, useProxy: b.cfg.useProxy, host: b.cfg.host, port: b.cfg.port, username: b.cfg.username, version: b.cfg.version }
      });
    });
    this.expressApp.post('/api/bots', (req, res) => {
      const { id, host, port, username, password, version, proxyIdx, proxyId } = req.body || {};
      if (!id || !host || !port || !username) {
        return res.status(400).json({ error: 'id, host, port, username required' });
      }
      if (this.manager.findBot(id)) {
        return res.status(409).json({ error: 'ID already exists' });
      }
      const b = this.manager.createBot({ id, host, port, username, password, version, proxyIdx, proxyId });
      if (this.io) this.io.emit('botAdded', b.getSummary());
      res.json({ ok: true, id: b.cfg.id });
    });
    this.expressApp.get('/api/proxies', (req, res) => {
      res.json(this.manager.proxyManager.getSummaries());
    });

    this.expressApp.post('/api/proxies', (req, res) => {
      const { proxy, tag } = req.body || {};
      if (!proxy) return res.status(400).json({ error: 'proxy required' });
      const r = this.manager.proxyManager.add(proxy, tag);
      res.json(r);
    });
    this.expressApp.post('/api/proxies/auto-add', async (req, res) => {
      const { proxy, tag } = req.body || {};
      if (!proxy) return res.status(400).json({ error: 'proxy required' });
      const r = await this.manager.proxyManager.autoAdd(proxy, tag);
      res.json(r);
    });
    this.expressApp.post('/api/proxies/detect', async (req, res) => {
      const { proxy, host, port } = req.body || {};
      let result;
      if (proxy) {
        result = await this.manager.proxyManager.detectType(proxy);
      } else if (host && port) {
        result = await this.manager.proxyManager.detectType(host, port);
      } else {
        return res.status(400).json({ error: 'proxy or host+port required' });
      }
      res.json(result);
    });
    this.expressApp.post('/api/proxies/test/:idx', async (req, res) => {
      const idx = parseInt(req.params.idx, 10);
      const result = await this.manager.proxyManager.test(idx);
      res.json(result);
    });
    this.expressApp.post('/api/proxies/enrich/:idx', async (req, res) => {
      const idx = parseInt(req.params.idx, 10);
      const result = await this.manager.proxyManager.enrichGeo(idx);
      res.json(result);
    });
    this.expressApp.post('/api/proxies/upgrade/:idx', async (req, res) => {
      const idx = parseInt(req.params.idx, 10);
      const result = await this.manager.proxyManager.upgrade(idx);
      res.json(result);
    });
    this.expressApp.post('/api/proxies/upgrade-all', async (req, res) => {
      const results = await this.manager.proxyManager.upgradeAll();
      res.json({ ok: true, results });
    });
    this.expressApp.delete('/api/proxies/:idx', (req, res) => {
      const idx = parseInt(req.params.idx, 10);
      const p = this.manager.proxyManager.remove(idx);
      if (!p) return res.status(404).json({ error: 'Invalid index' });
      res.json({ ok: true, removed: { host: p.host, port: p.port } });
    });

    // ===== FREE PROXY FETCHER (Asia Low Ping 150-200ms) =====
    this.expressApp.get('/api/proxies/free-sources', (req, res) => {
      res.json({
        ok: true,
        asiaLowPing: true,
        description: "Free proxy sources optimized for Asia VN/SG/JP - ping 150-200ms target",
        sources: [
          {
            id: 'vn-proxyscrape',
            name: '🇻🇳 VN Elite - Proxyscrape SOCKS4/5 (0-175ms (VN elite, ultra low) for VN)',
            url: 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous%2Ctransparent&country=vn',
            tag: 'vn-proxyscrape',
            type: 'socks5',
            country: 'VN',
            pingTarget: '0-175ms (VN elite, ultra low)',
            recommended: true
          },
          {
            id: 'vn-sg-proxyscrape',
            name: '🇻🇳🇸🇬 VN+SG Mixed - Proxyscrape (0-175ms (VN+SG, recommended))',
            url: 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous&country=vn%2Csg',
            tag: 'vn-sg-mixed',
            type: 'socks5',
            country: 'VN,SG',
            pingTarget: '0-175ms (VN+SG, recommended)',
            recommended: true
          },
          {
            id: 'sg-proxyscrape',
            name: '🇸🇬 Singapore - Proxyscrape SOCKS (40-150ms, fastest Asia hub)',
            url: 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous&country=sg',
            tag: 'sg-proxyscrape',
            type: 'socks5',
            country: 'SG',
            pingTarget: '0-175ms - Singapore fastest Asia hub, excellent for VN',
            recommended: true
          },
          {
            id: 'jp-proxyscrape',
            name: '🇯🇵 Japan - Proxyscrape SOCKS (0-175ms (JP, low latency))',
            url: 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous&country=jp',
            tag: 'jp-proxyscrape',
            type: 'socks5',
            country: 'JP',
            pingTarget: '0-175ms (JP, low latency)'
          },
          {
            id: 'asia-mixed-proxyscrape',
            name: '🌏 Asia Mixed VN/SG/JP/ID/TH/MY - Proxyscrape (0-175ms (Asia mixed, filtered))',
            url: 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous&country=vn%2Csg%2Cjp%2Cid%2Cth%2Cmy%2Cph%2Ckh%2Ctw%2Ckr',
            tag: 'asia-mixed',
            type: 'socks5',
            country: 'VN,SG,JP,ID,TH,MY,PH,KH,TW,KR',
            pingTarget: '0-175ms (Asia mixed, filtered)',
            recommended: true
          },
          {
            id: 'asia-socks5-raw',
            name: '🌏 Asia SOCKS5 - TheSpeedX (ID, SG, JP, VN)',
            url: 'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt',
            tag: 'asia-speedx-socks5',
            type: 'socks5',
            country: 'Mixed Asia',
            pingTarget: '0-175ms (filtered)',
            filterAsia: true
          },
          {
            id: 'proxifly-sg-jp',
            name: '🇸🇬🇯🇵 SG/JP Filtered - Proxifly SOCKS5 (Asia filtered)',
            url: 'https://cdn.jsdelivr.net/gh/proxy4parsing/proxy-list@main/socks5.txt',
            tag: 'proxifly-socks5-asia',
            type: 'socks5',
            country: 'Mixed, filter SG/JP/VN',
            pingTarget: '0-175ms (filtered)',
            filterAsia: true
          },
          {
            id: 'roosterkid-socks5',
            name: '🌏 RoosterKid SOCKS5 - OpenProxyList (large, contains Asia)',
            url: 'https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt',
            tag: 'roosterkid-socks5',
            type: 'socks5',
            country: 'Global, contains Asia',
            pingTarget: '0-175ms target (will filter)'
          },
          {
            id: 'databay-sg',
            name: '🇸🇬 Databay Singapore TXT (fastest Asia, 1.3s median, elite 40%)',
            url: 'https://databay.com/api/v1/proxy-list?country=SG&format=txt&limit=100',
            tag: 'databay-sg',
            type: 'socks5',
            country: 'SG',
            pingTarget: '40-150ms - fastest Asia list',
            apiFormat: 'databay'
          },
          {
            id: 'all-proxyscrape-socks',
            name: '🌍 Global - Proxyscrape SOCKS4/5 (fallback, higher ping 0-175ms target (will filter high ping))',
            url: 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous',
            tag: 'proxyscrape-socks',
            type: 'socks5',
            pingTarget: '0-175ms target (will filter high ping)'
          }
        ]
      });
    });

    this.expressApp.post('/api/proxies/fetch/free', async (req, res) => {
    this.expressApp.post('/api/proxies/fetch/free', async (req, res) => {
      const { url, tag, limit, type, autoTest } = req.body || {};
      if (!url) return res.status(400).json({ ok: false, error: 'url required - API endpoint for proxy list' });
      try {
        const result = await this.manager.proxyManager.fetchFreeProxiesFromUrl(url, {
          tag: tag || 'free',
          limit: Math.min(parseInt(limit, 10) || 100, 500),
          defaultType: type || 'socks5',
          autoTest: autoTest === true,
        });
        res.json(result);
      } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
      }
    });

    this.expressApp.get('/api/proxies/fetch-vn', async (req, res) => {
      const limit = Math.min(parseInt(req.query.limit, 10) || 100, 500);
      const autoTest = req.query.autoTest !== 'false';
      try {
        const result = await this.manager.proxyManager.fetchProxyscrapeVN({ limit, autoTest });
        res.json(result);
      } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
      }
    });

    this.expressApp.post('/api/proxies/fetch-vn', async (req, res) => {
      const { limit, autoTest, url } = req.body || {};
      try {
        const result = await this.manager.proxyManager.fetchProxyscrapeVN({
          limit: Math.min(parseInt(limit, 10) || 100, 500),
          autoTest: autoTest !== false,
          url,
        });
        res.json(result);
      } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
      }
    });


    this.expressApp.post('/api/proxies/fetch-multiple', async (req, res) => {
      const { sources, limit, autoTest } = req.body || {};
      const defaultSources = (sources && sources.length) ? sources : [
        { url: 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous%2Ctransparent&country=vn', tag: 'vn-proxyscrape', type: 'socks5', limit: 50 },
        { url: 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite', tag: 'proxyscrape-mixed', type: 'socks5', limit: 50 },
      ];
      try {
        const results = await this.manager.proxyManager.fetchMultipleSources(defaultSources, { limit, autoTest });
        const totalAdded = results.reduce((sum, r) => sum + (r.result.count || 0), 0);
        res.json({ ok: true, totalAdded, results });
      } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
      }
    });

    // ===== BOT TO SERVER PING CHECK (0-175ms) =====
    this.expressApp.post('/api/proxies/test-to-server/:idx', async (req, res) => {
      const idx = parseInt(req.params.idx, 10);
      const { host, port } = req.body || {};
      const targetHost = host || req.query.host;
      const targetPort = parseInt(port || req.query.port || 25565, 10);
      if (!targetHost) return res.status(400).json({ ok: false, error: 'host required - Minecraft server IP' });
      try {
        const result = await this.manager.proxyManager.testToMinecraftServer(idx, targetHost, targetPort);
        res.json(result);
      } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
      }
    });

    this.expressApp.post('/api/proxies/test-all-to-server', async (req, res) => {
      const { host, port, maxMs, onlyLowPing, concurrency, onlyLive } = req.body || {};
      const targetHost = host || req.query.host;
      const targetPort = parseInt(port || req.query.port || 25565, 10);
      if (!targetHost) return res.status(400).json({ ok: false, error: 'host required - Minecraft server IP' });
      try {
        const result = await this.manager.proxyManager.testAllToMinecraftServer(targetHost, targetPort, {
          maxMs: parseInt(maxMs, 10) || 175,
          filterLowPing: onlyLowPing !== false,
          concurrency: parseInt(concurrency, 10) || 5,
          onlyLive: onlyLive === true
        });
        res.json(result);
      } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
      }
    });

    this.expressApp.get('/api/proxies/low-ping', (req, res) => {
      const maxMs = parseInt(req.query.maxMs, 10) || 175;
      const lowPing = this.manager.proxyManager.getLowPingProxies(maxMs);
      res.json({
        ok: true,
        maxMs,
        count: lowPing.length,
        proxies: lowPing.map(p => ({
          id: p.id,
          host: p.host,
          port: p.port,
          type: p.type,
          ping: p.ping,
          serverPing: p.serverPing,
          quality: p.quality,
          tag: p.tag,
          status: p.status
        })).sort((a,b) => a.ping - b.ping)
      });
    });

    this.expressApp.post('/api/proxies/fetch-lowping-asia', async (req, res) => {
      const { url, limit, maxMs, targetHost, targetPort, tag } = req.body || {};
      const apiUrl = url || 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=ipport&format=text&protocol=socks4%2Csocks5&anonymity=elite%2Canonymous%2Ctransparent&country=vn%2Csg%2Cjp%2Cid%2Cth%2Cmy';
      try {
        const result = await this.manager.proxyManager.fetchAndTestLowPingAsia(apiUrl, {
          tag: tag || 'asia-0-175ms',
          limit: Math.min(parseInt(limit, 10) || 50, 200),
          maxMs: parseInt(maxMs, 10) || 175,
          targetHost: targetHost || null,
          targetPort: parseInt(targetPort, 10) || 25565,
          type: 'socks5',
          autoFilter: true
        });
        res.json(result);
      } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
      }
    });

    // Bot ping to server (from BotSession mineflayer ping)
    this.expressApp.get('/api/bots/:id/ping', (req, res) => {
      const b = this.manager.findBot(req.params.id);
      if (!b) return res.status(404).json({ error: 'Bot not found' });
      const summary = b.getSummary();
      res.json({
        ok: true,
        botId: b.cfg.id,
        ping: summary.ping, // mineflayer ping to server
        server: `${summary.host}:${summary.port}`,
        state: summary.state,
        proxy: summary.proxy,
        quality: summary.ping >=0 ? (summary.ping <=50 ? 'excellent' : summary.ping <=100 ? 'good' : summary.ping <=175 ? 'fair - within 0-175ms target' : 'high') : 'unknown',
        withinTarget: summary.ping >=0 && summary.ping <=175
      });
    });

    this.expressApp.get('/api/bots/ping/all', (req, res) => {
      const bots = this.manager.bots.map(b => {
        const s = b.getSummary();
        return {
          id: s.id,
          host: s.host,
          port: s.port,
          ping: s.ping,
          state: s.state,
          proxy: s.proxy,
          withinTarget: s.ping >=0 && s.ping <=175,
          quality: s.ping >=0 ? (s.ping <=50 ? 'excellent' : s.ping <=100 ? 'good' : s.ping <=175 ? 'fair' : 'high') : 'unknown'
        };
      });
      const lowPing = bots.filter(b => b.withinTarget);
      res.json({
        ok: true,
        maxMs: 175,
        total: bots.length,
        lowPingCount: lowPing.length,
        lowPingBots: lowPing.sort((a,b) => a.ping - b.ping),
        allBots: bots.sort((a,b) => (a.ping>=0?a.ping:9999) - (b.ping>=0?b.ping:9999))
      });
    });


        this.expressApp.post('/api/bots/:id/assign-proxy', (req, res) => {
      const b = this.manager.findBot(req.params.id);
      if (!b) return res.status(404).json({ error: 'Not found' });
      const { proxyIdx, proxyId } = req.body || {};
      if ((proxyIdx === undefined || proxyIdx === null) && (proxyId === undefined || proxyId === null)) {
        this.manager.proxyManager.unassignBot(b.cfg.id);
        b.proxy = null;
        this._syncBotToConfig(b);
        return res.json({ ok: true });
      }
      const target = proxyId !== undefined ? proxyId : parseInt(proxyIdx, 10);
      if (!this.manager.proxyManager.assignBot(b.cfg.id, target)) {
        return res.status(400).json({ error: 'Invalid proxy' });
      }
      b.proxy = this.manager.proxyManager.getAssignment(b.cfg.id);
      this._syncBotToConfig(b);
      res.json({ ok: true });
    });
    this.expressApp.get('/api/system', (req, res) => {
      res.json(this.manager.getSystemMetrics());
    });
    this.expressApp.get('/api/capacity', (req, res) => {
      try {
        res.json(this.manager.getBotCapacity());
      } catch (e) {
        res.status(500).json({ ok: false, error: e.message });
      }
    });
    this.expressApp.get('/api/server-env', (req, res) => {
      res.json(this.manager.env);
    });
    this.io.on('connection', sock => {
      const clientIp = sock.handshake?.address || sock.conn?.remoteAddress || 'unknown';
      sock.emit('init', {
        bots: this.manager.bots.map(b => b.getSummary()),
        serverEnv: this.manager.env,
        proxies: this.manager.proxyManager.getSummaries(),
        summary: this.manager.getSummary ? this.manager.getSummary() : null,
        capacity: this.manager.getBotCapacity ? this.manager.getBotCapacity() : null,
      });
      sock.on('subscribe', id => {
        try {
          if (!id || typeof id !== 'string') return;
          sock.join(`bot:${id}`);
          const b = this.manager.findBot(id);
          if (b) {
            sock.emit('logs', { id, logs: b.getLogs() });
            sock.emit('inventory', { id, items: b.state.inventory });
            sock.emit('customCmds', { id, cmds: b.cmdRegistry.getCustomCmds() });
          }
        } catch (e) {
        }
      });
      sock.on('unsubscribe', id => sock.leave(`bot:${id}`));
      sock.on('cmd', ({ id, cmd }) => {
        if (!id || cmd === undefined) return;
        if (!_rateLimit('cmd:' + id, 10)) {
          sock.emit('error', { code: 'RATE_LIMIT', message: 'Quá nhiều lệnh — vui lòng chậm lại' });
          return;
        }
        if (id === '*') {
          for (const bot of this.manager.bots) bot.cmd(String(cmd));
        } else {
          const b = this.manager.findBot(id);
          if (b) b.cmd(String(cmd));
        }
      });
      sock.on('reconnect_bot', ({ id }) => {
        if (!id) return;
        const b = this.manager.findBot(id);
        if (b) b.forceReconnect();
      });
      sock.on('startBot', ({ id }, cb) => {
        if (!id) { if (cb) cb({ ok: false, code: 'INVALID_ID', message: 'Thiếu ID bot' }); return; }
        if (!_rateLimit('startStop:' + id, 2)) {
          if (cb) cb({ ok: false, code: 'RATE_LIMIT', message: 'Vui lòng chậm lại' }); return;
        }
        const b = this.manager.findBot(id);
        if (!b) { if (cb) cb({ ok: false, code: 'NOT_FOUND', message: 'Bot không tồn tại' }); return; }
        if (b.isConnected || b.isReconnecting) {
          if (cb) cb({ ok: false, code: 'ALREADY_RUNNING', message: 'Bot đang chạy rồi' });
          return;
        }
        b._disabled = false;
        b.state.reconnects = 0;
        b.start();
        this.io.emit('botState', { id, state: b.state.connState });
        if (cb) cb({ ok: true });
      });
      sock.on('stopBot', ({ id }, cb) => {
        if (!id) { if (cb) cb({ ok: false, code: 'INVALID_ID', message: 'Thiếu ID bot' }); return; }
        if (!_rateLimit('startStop:' + id, 2)) {
          if (cb) cb({ ok: false, code: 'RATE_LIMIT', message: 'Vui lòng chậm lại' }); return;
        }
        const b = this.manager.findBot(id);
        if (!b) { if (cb) cb({ ok: false, code: 'NOT_FOUND', message: 'Bot không tồn tại' }); return; }
        b.shutdown();
        this.io.emit('botState', { id, state: b.state.connState });
        if (cb) cb({ ok: true });
      });
      sock.on('addBot', (data, cb) => {
        const { id, host, port, username, password, version, proxyIdx, proxyId } = data || {};
        if (!id || !host || !port || !username) {
          if (cb) cb({ ok: false, code: 'MISSING_FIELDS', message: 'Thiếu thông tin (id, host, port, username)' });
          return;
        }
        if (this.manager.findBot(id)) {
          if (cb) cb({ ok: false, code: 'DUPLICATE', message: 'ID đã tồn tại' });
          return;
        }
        const b = this.manager.createBot({ id, host, port, username, password, version, proxyIdx, proxyId });
        this.io.emit('botAdded', b.getSummary());
        if (cb) cb({ ok: true });
      });
      sock.on('editBot', (data, cb) => {
        const { id, host, port, username, password, version, useProxy, autoMenu, menuCommand, ownerUsername, proxyId, sendClientSettings, skipValidation, viewDistance } = data || {};
        const b = this.manager.findBot(id);
        if (!b) { if (cb) cb({ ok: false, code: 'NOT_FOUND', message: 'Bot không tồn tại' }); return; }
        const allowed = { host, port, username, version, useProxy, autoMenu, menuCommand, ownerUsername, sendClientSettings, skipValidation, viewDistance };
        for (const [k, v] of Object.entries(allowed)) {
          if (v !== undefined && v !== null && v !== '') b.cfg[k] = v;
        }
        if (password !== undefined && password !== null && password !== '') {
          b.cfg.botPassword = password;
          b.cfg.registered = false;
        }
        if (proxyId !== undefined && proxyId !== null) {
          if (proxyId && proxyId !== '') {
            const assigned = this.manager.proxyManager.assignBot(b.cfg.id, proxyId);
            if (!assigned) {
              if (cb) cb({ ok: false, code: 'PROXY_NOT_FOUND', message: 'Proxy không tồn tại hoặc đã bị xóa' });
              return;
            }
            b.proxy = this.manager.proxyManager.getAssignment(b.cfg.id);
            b.cfg.useProxy = true;
          } else {
            this.manager.proxyManager.unassignBot(b.cfg.id);
            b.proxy = null;
            b.cfg.useProxy = false;
          }
        }
        this._syncBotToConfig(b);
        this.io.emit('botUpdated', b.getSummary());
        if (cb) cb({ ok: true });
      });
      sock.on('removeBot', ({ id }, cb) => {
        const bot = this.manager.removeBot(id);
        if (!bot) { if (cb) cb({ ok: false, code: 'NOT_FOUND', message: 'Bot không tồn tại' }); return; }
        this.io.emit('botRemoved', { id });
        if (cb) cb({ ok: true });
      });
      sock.on('addCustomCmd', ({ id, name, cmd }, cb) => {
        const b = this.manager.findBot(id);
        if (!b) { if (cb) cb({ ok: false, code: 'NOT_FOUND', message: 'Bot không tồn tại' }); return; }
        b.cmdRegistry.addCustom(name, cmd);
        this.io.emit('customCmds', { id, cmds: b.cmdRegistry.getCustomCmds() });
        if (cb) cb({ ok: true });
      });
      sock.on('delCustomCmd', ({ id, name }, cb) => {
        const b = this.manager.findBot(id);
        if (!b) { if (cb) cb({ ok: false, code: 'NOT_FOUND', message: 'Bot không tồn tại' }); return; }
        b.cmdRegistry.deleteCustom(name);
        this.io.emit('customCmds', { id, cmds: b.cmdRegistry.getCustomCmds() });
        if (cb) cb({ ok: true });
      });
      sock.on('getSystemMetrics', (cb) => {
        if (cb) cb(this.manager.getSystemMetrics());
      });
      sock.on('startAll', (data, cb) => {
        this.manager.startAll(typeof data?.filterFn === 'function' ? data.filterFn : null);
        if (cb) cb({ ok: true });
      });
      sock.on('stopAll', (data, cb) => {
        this.manager.stopAll(typeof data?.filterFn === 'function' ? data.filterFn : null);
        if (cb) cb({ ok: true });
      });
      sock.on('restartAll', (data, cb) => {
        this.manager.restartAll(typeof data?.filterFn === 'function' ? data.filterFn : null);
        if (cb) cb({ ok: true });
      });
      sock.on('disconnect', reason => {
        const reasonMap = {
          'transport close': 'transport_close',
          'ping timeout': 'ping_timeout',
          'transport error': 'transport_error',
          'server namespace disconnect': 'server_ns_disconnect',
          'client namespace disconnect': 'client_ns_disconnect',
        };
        const code = reasonMap[reason] || reason;
        if (!process.env.SILENT_SOCKET) {
          console.log(`[Socket] Client disconnected (${clientIp}): ${code}`);
        }
      });
    });
    const statusInterval = this.manager.profile?.statusInterval || 1500;
    const metricsInterval = this.manager.profile?.metricsInterval || 3000;
    this._statusInterval = setInterval(() => {
      if (!this.io || this.io.engine.clientsCount === 0) return;
      const summaries = this.manager.bots.map(b => b.getSummary());
      const hashParts = summaries.map(s =>
        `${s.id}|${s.state}|${s.ping}|${s.ppsIn}|${s.ppsOut}|${s.health}|${s.food}|${s.shard}|${s.reconnects}|${s.afk || ''}|${s.position?.x?.toFixed(1) || ''}`
      ).join(';');
      if (hashParts === this._prevStatusSnap) return;
      this._prevStatusSnap = hashParts;
      if (summaries.length > 50) {
        setImmediate(() => {
          this.io.emit('statusUpdate', { bots: summaries });
        });
      } else {
        this.io.emit('statusUpdate', { bots: summaries });
      }
    }, statusInterval);
    this._metricsInterval = setInterval(() => {
      if (!this.io || this.io.engine.clientsCount === 0) return;
      this.io.emit('systemMetrics', this.manager.getSystemMetrics());
    }, metricsInterval);
    if (this._statusInterval.unref) this._statusInterval.unref();
    if (this._metricsInterval.unref) this._metricsInterval.unref();
    // Bind to 0.0.0.0 explicitly for Pterodactyl Docker networking
    // Pterodactyl maps container port to host port, must listen on 0.0.0.0 not 127.0.0.1
    const bindHost = process.env.BIND_HOST || process.env.HOST || '0.0.0.0';
    this.expressServer.listen(this.port, bindHost, () => {
      const localUrl = `http://localhost:${this.port}`;
      const bindUrl = `http://${bindHost}:${this.port}`;
      // Try to detect external Pterodactyl allocation
      const serverIp = process.env.SERVER_IP || process.env.P_SERVER_IP || '';
      const serverPort = process.env.SERVER_PORT || process.env.P_SERVER_PORT || this.port;
      const externalIp = process.env.EXTERNAL_IP || serverIp || 'play1.nvnmc.top';
      
      if (this.autoExe) {
        console.log(`\x1b[36m╔══════════════════════════════════════╗\x1b[0m`);
        console.log(`\x1b[36m║  ⬡   Bot Manager — Antares       ║\x1b[0m`);
        console.log(`\x1b[36m╠══════════════════════════════════════╣\x1b[0m`);
        console.log(`\x1b[36m║  Web Dashboard:                      ║\x1b[0m`);
        console.log(`\x1b[36m║  \x1b[33m${localUrl.padEnd(36)}\x1b[36m║\x1b[0m`);
        console.log(`\x1b[36m║  \x1b[33m${bindUrl.padEnd(36)}\x1b[36m║\x1b[0m`);
        if (externalIp && serverPort) {
          const extUrl = `http://${externalIp}:${serverPort}`;
          console.log(`\x1b[36m║  \x1b[32m${extUrl.padEnd(36)}\x1b[36m║\x1b[0m`);
        }
        console.log(`\x1b[36m╚══════════════════════════════════════╝\x1b[0m`);
        console.log(`\x1b[33m[INFO] Nếu ERR_CONNECTION_TIMED_OUT khi vào ${externalIp}:${serverPort}:\x1b[0m`);
        console.log(`\x1b[33m  - Kiểm tra Cloudflare: port 26009 không được Cloudflare proxy cho phép (chỉ 80,443,2053,2083,2087,2096,8443...)\x1b[0m`);
        console.log(`\x1b[33m  - Thử http:// không phải https://\x1b[0m`);
        console.log(`\x1b[33m  - Hỏi admin nvnmc.top tắt Cloudflare proxy (đám mây xám) cho play1.nvnmc.top\x1b[0m`);
        console.log(`\x1b[33m  - Hoặc dùng IP trực tiếp thay vì domain, hoặc đổi port sang 2053/2083 được Cloudflare cho phép\x1b[0m`);
      } else {
        console.log(`\x1b[36m[Dashboard] Web UI: ${localUrl} (bind ${bindUrl})\x1b[0m`);
        if (externalIp) {
          console.log(`\x1b[36m[Dashboard] External: http://${externalIp}:${serverPort}\x1b[0m`);
        }
      }
    });
    this.expressServer.on('error', (err) => {
      console.error(`\x1b[31m[Dashboard] Failed to bind ${bindHost}:${this.port} - ${err.message}\x1b[0m`);
      if (err.code === 'EADDRINUSE') {
        console.error(`\x1b[33mPort ${this.port} đang bị chiếm! Thử đổi PORT env hoặc --port khác\x1b[0m`);
      }
      if (err.code === 'EACCES') {
        console.error(`\x1b[33mKhông có quyền bind port ${this.port} (cần >1024 hoặc chạy root)\x1b[0m`);
      }
    });
  }
  shutdown() {
    if (this._statusInterval) clearInterval(this._statusInterval);
    if (this._metricsInterval) clearInterval(this._metricsInterval);
    if (this._rateCleanup) clearInterval(this._rateCleanup);
  }
  _syncBotToConfig(bot) {
    if (!this.manager._config?.bots) return;
    const cfgBot = this.manager._config.bots.find(c => c.id.toLowerCase() === bot.cfg.id.toLowerCase());
    if (cfgBot) {
      for (const k of Object.keys(bot.cfg)) {
        if (bot.cfg[k] !== undefined) cfgBot[k] = bot.cfg[k];
      }
    }
    this.manager.persistence.markDirty();
    this.manager.persistence.saveSync();
  }
}
module.exports = WebDashboard;
