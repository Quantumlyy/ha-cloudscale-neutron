// Test stand-in for the Scale Monitor broker plus a fake Neutron module.
const http = require('http');
const { WebSocketServer, createWebSocketStream } = require('ws');
const Aedes = require('aedes');
const [port, mid, pin] = [parseInt(process.argv[2]), process.argv[3], process.argv[4]];
const aedes = Aedes();
const state = { gross: 0, tare: 0, status: 'S', polls: 0, mute: false };
aedes.authenticate = (client, username, password, cb) => {
  const ok = username === 'CSL-' + mid && password && password.toString() === pin;
  if (ok) return cb(null, true);
  const err = new Error('bad auth'); err.returnCode = 4; cb(err, false);
};
const pad = (n, d, w) => n.toFixed(d).padStart(w);
const line = () => ['QASI1C', 1, 1, 1, state.status, pad(state.gross, 3, 10), pad(state.gross - state.tare, 3, 10),
  pad(state.tare, 3, 10), pad(state.gross, 5, 10), String(1234567).padStart(10), pad(0.1234, 4, 10), 'kg'].join(',');
const reply = (payload) => aedes.publish({ topic: `$CSL/${mid}/TX/SC`, payload, qos: 0 }, () => {});
aedes.on('publish', (packet, client) => {
  if (!client || packet.topic !== `$CSL/${mid}/RX/SC` || state.mute) return;
  const cmd = packet.payload.toString();
  if (cmd === 'QASI1C') { state.polls++; reply(line()); }
  else if (cmd === 'T') { state.tare = state.gross; reply(`T S ${pad(state.tare, 3, 10)} kg`); }
  else if (cmd === 'Z') { state.gross = 0; reply('Z A'); }
  else if (cmd === 'TAC') { state.tare = 0; reply('TAC A'); }
});
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  if (url.pathname === '/set') {
    for (const [k, v] of url.searchParams) state[k] = (k === 'status') ? v : (k === 'mute' ? v === '1' : parseFloat(v));
  }
  res.end(JSON.stringify(state));
});
const wss = new WebSocketServer({ noServer: true });
server.on('upgrade', (req, socket, head) => {
  if (req.url !== '/sm') { socket.destroy(); return; }
  wss.handleUpgrade(req, socket, head, (ws) => aedes.handle(createWebSocketStream(ws)));
});
server.listen(port, '127.0.0.1', () => console.log('ready'));
