'use strict';
// Minimal websocket backend for /api/ws/system on 127.0.0.1:19081.
//
// On real UniFi OS the system websocket is served by unifi-core, but under
// FreeBSD that handler is not available, so the port's nginx config proxies
// /api/ws/system to this stub. Without a backend nginx returns 502 and the
// uhd-setup wizard spins forever waiting for the system socket to connect.
//
// The setup UI flips its system connectionState to "connected" the moment the
// socket opens, so accepting the upgrade and keeping it alive is enough to let
// the wizard render; system data itself is read over REST (/api/system).

const http = require('http');
const wsmod = require('/usr/share/unifi-core/app/node_modules/ws');
const WebSocketServer = wsmod.WebSocketServer || wsmod.Server;

const HOST = '127.0.0.1';
const PORT = 19081;

const server = http.createServer((req, res) => {
  // Anything that is not an Upgrade gets a clear non-200 instead of hanging.
  res.writeHead(426, { 'Content-Type': 'text/plain' });
  res.end('Upgrade Required\n');
});

const wss = new WebSocketServer({ server });

wss.on('connection', (ws) => {
  // Drain client frames (subscribe/open messages) so the socket stays healthy.
  ws.on('message', () => {});

  // Keep the connection alive through nginx's proxy_read_timeout.
  const keepalive = setInterval(() => {
    if (ws.readyState === ws.OPEN) {
      try { ws.ping(); } catch (_) { /* ignore */ }
    }
  }, 30000);

  const stop = () => clearInterval(keepalive);
  ws.on('close', stop);
  ws.on('error', stop);
});

wss.on('error', (err) => {
  console.error('[system-ws-stub] server error:', err && err.message);
});

server.listen(PORT, HOST, () => {
  console.log(`[system-ws-stub] listening on ${HOST}:${PORT}`);
});
