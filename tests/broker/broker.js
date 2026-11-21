// Test stand-in for the Scale Monitor broker plus a fake Neutron module.
//
//   node broker.js PORT MODULE_ID PIN [CERT_FILE KEY_FILE]
//
// MQTT over WebSocket is served on /sm. With a certificate it is served over
// TLS. The same port answers plain HTTP(S) requests that steer the fake module:
//
//   /set?gross=1.5&status=D&mute=1   change the module's state
//   /inject?payload=...              publish a raw line on the reply topic
//
// The WebSocket path /silent accepts the connection and then says nothing, and
// the password "busy" is refused with "server unavailable".
const fs = require('fs');
const http = require('http');
const https = require('https');
const { WebSocketServer, createWebSocketStream } = require('ws');
const Aedes = require('aedes');

const [port, mid, pin, certFile, keyFile] = [parseInt(process.argv[2]), ...process.argv.slice(3)];
const aedes = Aedes();
const state = { gross: 0, tare: 0, status: 'S', polls: 0, mute: false, commands: [] };
// Made-up scale settings: 30 kg capacity, 0.005 kg division.
const SETTINGS = 'RSD;SCI=1;SAM=0;1D1=0.005;1D2=;1D3=;1M1=30;1M2=;1M3=;1U=kg;1WR=1;1FT=100';

aedes.authenticate = (client, username, password, cb) => {
  const given = password ? password.toString() : '';
  if (username === 'CSL-' + mid && given === pin) return cb(null, true);
  const err = new Error('refused');
  err.returnCode = given === 'busy' ? 3 : 4; // 3 = server unavailable, 4 = bad credentials
  cb(err, false);
};

const pad = (n, d, w) => n.toFixed(d).padStart(w);
const line = () => ['QASI1C', 1, 1, 1, state.status, pad(state.gross, 3, 10), pad(state.gross - state.tare, 3, 10),
  pad(state.tare, 3, 10), pad(state.gross, 5, 10), String(1234567).padStart(10), pad(0.1234, 4, 10), 'kg'].join(',');
const reply = (payload) => aedes.publish({ topic: `$CSL/${mid}/TX/SC`, payload, qos: 0 }, () => {});

aedes.on('publish', (packet, client) => {
  if (!client || packet.topic !== `$CSL/${mid}/RX/SC` || state.mute) return;
  const cmd = packet.payload.toString();
  if (!state.commands.includes(cmd)) state.commands.push(cmd);
  if (cmd === 'QASI1C') { state.polls++; reply(line()); }
  else if (cmd === 'RSD') { reply(SETTINGS); }
  else if (cmd === 'T') { state.tare = state.gross; reply(`T S ${pad(state.tare, 3, 10)} kg`); }
  else if (cmd === 'Z') { state.gross = 0; reply('Z A'); }
  else if (cmd === 'TAC') { state.tare = 0; reply('TAC A'); }
});

const handler = (req, res) => {
  const url = new URL(req.url, 'http://x');
  if (url.pathname === '/set') {
    for (const [k, v] of url.searchParams) state[k] = (k === 'status') ? v : (k === 'mute' ? v === '1' : parseFloat(v));
  } else if (url.pathname === '/inject') {
    reply(url.searchParams.get('payload'));
  }
  res.end(JSON.stringify(state));
};
const server = certFile
  ? https.createServer({ cert: fs.readFileSync(certFile), key: fs.readFileSync(keyFile) }, handler)
  : http.createServer(handler);

const wss = new WebSocketServer({ noServer: true });
server.on('upgrade', (req, socket, head) => {
  if (req.url === '/sm') {
    wss.handleUpgrade(req, socket, head, (ws) => aedes.handle(createWebSocketStream(ws)));
  } else if (req.url === '/silent') {
    wss.handleUpgrade(req, socket, head, () => {});
  } else {
    socket.destroy();
  }
});
server.listen(port, '127.0.0.1', () => console.log('ready'));
