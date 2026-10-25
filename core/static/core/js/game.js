/* Reboot Town — Jelly Village & Drink Village mini games (/game/).
   Anyone can play. Signed-in customers send each run to the server, which checks the
   score and pays points (max 300 P per run, 1,000 P per UTC day). */
'use strict';
(() => {
const dataEl = document.getElementById('game-data');
const stage = document.getElementById('game-stage');
const cv = document.getElementById('game-canvas');
if (!dataEl || !stage || !cv) return;
const DATA = JSON.parse(dataEl.textContent);
const C = cv.getContext('2d');
const W = 480, H = 270;
const $ = id => document.getElementById(id);
const PIX = '"Silkscreen", "Courier New", monospace';
const DISP = '"Barlow Condensed", "Arial Narrow", sans-serif';
const INK = '#14160f', NEON = '#b1ff3b', LAV = '#c8b5ff', CREAM = '#f5f4e9', PINK = '#ff87bd';
const REBU = '#89e325', REBU_D = '#5fa312', REBU_L = '#c5f495';
// Product colors measured from the real packshots: [Original, Balance]
const FLAVOR = {
  lime:   { name: 'LIME',   shape: 'boot',  jelly: ['#9cc10b', '#c5d077'], drink: ['#7cae58', '#bfe0a6'] },
  lemon:  { name: 'LEMON',  shape: 'lasso', jelly: ['#f8be14', '#f4d579'], drink: ['#d4cd4d', '#ece69a'] },
  cherry: { name: 'CHERRY', shape: 'hat',   jelly: ['#f9316e', '#e99ea7'], drink: ['#b7494b', '#e09a9b'] },
};
const FLAVORS = ['lime', 'lemon', 'cherry'];
const SHAPE_OF = { boot: 'lime', lasso: 'lemon', hat: 'cherry' };

let t = 0; // global clock (s)
const rnd = (a, b) => a + Math.random() * (b - a);
const pick = arr => arr[Math.floor(Math.random() * arr.length)];
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, k) => a + (b - a) * k;
const smooth = k => { k = clamp(k, 0, 1); return k * k * (3 - 2 * k); };

/* ---------- pixel helpers ---------- */
function R(x, y, w, h, c) { C.fillStyle = c; C.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)); }
function O(x, y, w, h, c) { R(x - 1, y - 1, w + 2, h + 2, INK); R(x, y, w, h, c); }
function shape(rects, c) { for (const r of rects) R(r[0] - 1, r[1] - 1, r[2] + 2, r[3] + 2, INK); for (const r of rects) R(r[0], r[1], r[2], r[3], c); }
function circ(cx, cy, r, c) { for (let dy = -r; dy <= r; dy++) { const w = Math.round(Math.sqrt(r * r - dy * dy)); R(cx - w, cy + dy, w * 2, 1, c); } }
function ocirc(cx, cy, r, c) { circ(cx, cy, r + 1, INK); circ(cx, cy, r, c); }
function glow(x, y, r, c, a) {
  const g = C.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, c); g.addColorStop(1, 'rgba(0,0,0,0)');
  C.globalAlpha = a; C.fillStyle = g; C.fillRect(x - r, y - r, r * 2, r * 2); C.globalAlpha = 1;
}
function hex(h) { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; }
function mix(a, b, k) { const p = hex(a), q = hex(b); return '#' + p.map((v, i) => Math.round(v + (q[i] - v) * clamp(k, 0, 1)).toString(16).padStart(2, '0')).join(''); }
function txt(s, x, y, op = {}) {
  const { size = 8, color = CREAM, align = 'center', font = PIX, stroke = null, sw = 3, weight = '' } = op;
  C.font = `${weight} ${size}px ${font}`.trim(); C.textAlign = align; C.textBaseline = 'middle';
  if (stroke) { C.lineJoin = 'round'; C.lineWidth = sw; C.strokeStyle = stroke; C.strokeText(s, Math.round(x), Math.round(y)); }
  C.fillStyle = color; C.fillText(s, Math.round(x), Math.round(y));
}
function textW(s, size = 8, font = PIX) { C.font = `${size}px ${font}`; return C.measureText(s).width; }
function panel(x, y, w, h, fill = CREAM) { R(x + 3, y + 4, w, h, 'rgba(0,0,0,.35)'); O(x, y, w, h, fill); }

/* ---------- product sprites ---------- */
// Rebu: lime jelly body, black cowboy hat with a green star, small green horns, white cowboy boots.
function drawRebu(x, y, op = {}) {
  const { s = 1, flip = false, walk = false, ph = 0, tilt = 0, happy = false, noBoots = false } = op;
  C.save(); C.translate(Math.round(x), Math.round(y)); if (tilt) C.rotate(tilt); C.scale(flip ? -s : s, s);
  const step = walk ? Math.floor((t + ph) * 8) % 2 : 0;
  const bob = walk ? -step : Math.round(Math.sin((t + ph) * 3) * 0.6);
  R(-7, -1, 14, 2, 'rgba(0,0,0,.28)');
  if (!noBoots) { // boots
    shape([[-6, -5 - step, 4, 4], [-7, -2 - step, 5, 2]], CREAM);
    shape([[2, -5 + step - (walk ? 1 : 0), 4, 4], [2, -2 + step - (walk ? 1 : 0), 5, 2]], CREAM);
    R(-6, -4 - step, 4, 1, '#c9c5b2'); R(2, -4 + step - (walk ? 1 : 0), 4, 1, '#c9c5b2');
  }
  C.translate(0, bob);
  shape([[-5, -19, 10, 2], [-7, -17, 14, 10], [-6, -7, 12, 2]], REBU); // body
  R(-6, -9, 12, 2, REBU_D); R(-5, -17, 2, 4, REBU_L); R(-3, -18, 2, 1, REBU_L);
  shape([[-10, -13 + (walk ? step : 0), 3, 3]], REBU); shape([[7, -13 + (walk ? 1 - step : 0), 3, 3]], REBU); // arms
  R(-4, -14, 2, 3, INK); R(2, -14, 2, 3, INK); R(-4, -14, 1, 1, '#fff'); R(2, -14, 1, 1, '#fff'); // eyes
  if (happy) { R(-2, -10, 4, 1, INK); R(-3, -11, 1, 1, INK); R(2, -11, 1, 1, INK); } else R(-1, -10, 2, 1, INK);
  R(-6, -11, 2, 1, PINK); R(4, -11, 2, 1, PINK);
  shape([[-8, -21, 2, 3]], REBU_D); shape([[6, -21, 2, 3]], REBU_D); // horns
  shape([[-10, -21, 20, 2], [-5, -27, 10, 6]], '#1a1a1a'); // hat
  R(-1, -27, 2, 1, '#333'); R(-5, -23, 10, 1, '#2a2a2a');
  R(-1, -26, 2, 3, NEON); R(-2, -25, 4, 1, NEON);
  C.restore();
}

// Jelly pieces: lime = boot, lemon = lasso, cherry = hat. line 0 = Original (deep), 1 = Balance (light).
function drawJelly(x, y, flavor, line = 0, s = 1, face = false) {
  const c = FLAVOR[flavor].jelly[line], hi = mix(c, '#ffffff', .45);
  C.save(); C.translate(Math.round(x), Math.round(y)); C.scale(s, s);
  if (flavor === 'lime') { // cowboy boot
    shape([[-3, -6, 5, 8], [-3, 1, 9, 3], [-4, 3, 3, 2]], c); R(-2, -5, 1, 4, hi); R(-3, -6, 5, 1, mix(c, INK, .25)); R(4, 2, 1, 1, hi);
  } else if (flavor === 'cherry') { // cowboy hat
    shape([[-6, 1, 12, 2], [-3, -4, 6, 5]], c); R(-3, -1, 6, 1, mix(c, INK, .3)); R(-2, -3, 1, 2, hi); R(-5, 1, 3, 1, hi);
  } else { // lasso ring + tail
    C.lineWidth = 4; C.strokeStyle = INK; C.beginPath(); C.arc(0, -1, 4.5, 0, Math.PI * 2); C.stroke();
    C.beginPath(); C.moveTo(3, 3); C.lineTo(6, 6); C.stroke();
    C.lineWidth = 2; C.strokeStyle = c; C.beginPath(); C.arc(0, -1, 4.5, 0, Math.PI * 2); C.stroke();
    C.beginPath(); C.moveTo(3, 3); C.lineTo(6, 6); C.stroke(); R(-3, -5, 2, 1, hi);
  }
  if (face) { R(-2, -1, 1, 1, INK); R(1, -1, 1, 1, INK); }
  C.restore();
}

// 100 ml Reboot bottle. line 0 = Original, 1 = Balance (Zero Sugar).
function drawBottle(x, y, flavor, line = 0, s = 1, face = false) {
  const liquid = FLAVOR[flavor].drink[line];
  C.save(); C.translate(Math.round(x), Math.round(y)); C.scale(s, s);
  shape([[-2, -17, 4, 2]], '#0f2a12');               // cap
  shape([[-2, -15, 4, 3], [-4, -12, 8, 12]], '#dff3ea'); // glass
  R(-3, -9, 6, 8, liquid); R(-3, -6, 6, 3, '#151515'); R(-2, -5, 3, 1, NEON); // liquid + label
  R(-3, -11, 1, 8, 'rgba(255,255,255,.7)');
  if (line === 1) R(1, -5, 1, 1, CREAM);
  if (face) { R(-2, -8, 1, 1, INK); R(1, -8, 1, 1, INK); }
  C.restore();
}

// Jelly line package (black pouch, all three shapes inside).
function drawPackage(x, y, line = 0, s = 1) {
  C.save(); C.translate(Math.round(x), Math.round(y)); C.scale(s, s);
  shape([[-7, -20, 14, 20]], '#171717'); R(-7, -20, 14, 2, '#2c2c2c'); R(-6, -15, 12, 2, line ? '#c5d077' : NEON);
  R(-5, -10, 3, 3, FLAVOR.lime.jelly[line]); R(-1, -10, 3, 3, FLAVOR.lemon.jelly[line]); R(3, -10, 3, 3, FLAVOR.cherry.jelly[line]);
  R(-6, -4, 12, 1, '#333');
  C.restore();
}

// Mixed Box: three bottles, lemon / lime / cherry.
function drawBox3(x, y, s = 1, gold = false) {
  C.save(); C.translate(Math.round(x), Math.round(y)); C.scale(s, s);
  shape([[-11, -12, 22, 12]], gold ? '#ffd84a' : CREAM); R(-11, -12, 22, 3, '#151515'); R(-9, -11, 6, 1, NEON);
  ['lemon', 'lime', 'cherry'].forEach((f, i) => { R(-8 + i * 6, -7, 4, 6, FLAVOR[f].drink[0]); R(-7 + i * 6, -8, 2, 1, '#0f2a12'); });
  if (gold) { R(-12, -14, 2, 2, '#fff8c4'); R(10, -3, 2, 2, '#fff8c4'); }
  C.restore();
}

function drawTumbleweed(x, y, r = 7) {
  ocirc(x, y, r, '#a8834f'); C.strokeStyle = '#6e5130'; C.lineWidth = 1;
  for (let i = 0; i < 4; i++) { const a = t * 6 + i * 1.6; C.beginPath(); C.arc(x, y, r - 2 - i % 2 * 2, a, a + 2.4); C.stroke(); }
}

/* ================= REBOOT TOWN ================= */
const WORLD = 960, GROUND = 184, Y_MIN = 200, Y_MAX = 252;
const BUILDINGS = [
  { id: 'lasso-leap',     x: 112, village: 'jelly', label: 'LASSO LEAP',     box: [80, 150, 92, 184] },
  { id: 'jelly-drop',     x: 240, village: 'jelly', label: 'JELLY DROP',     box: [184, 296, 96, 184] },
  { id: 'store-jelly',    x: 382, village: 'jelly', label: 'JELLY STORE',    box: [344, 420, 92, 184], store: 'Jelly' },
  { id: 'bottle-pop',     x: 580, village: 'drink', label: 'BOTTLE POP',     box: [552, 608, 68, 184] },
  { id: 'sunrise-flight', x: 718, village: 'drink', label: 'SUNRISE FLIGHT', box: [680, 760, 60, 184] },
  { id: 'store-drink',    x: 860, village: 'drink', label: 'DRINK STORE',    box: [814, 906, 104, 184], store: 'Drink' },
];
const VILLAGES = {
  jelly: { name: 'JELLY VILLAGE', sub: 'Boot · Lasso · Hat — Original & Balance' },
  drink: { name: 'DRINK VILLAGE', sub: '100 ml bottles — Lemon · Lime · Cherry' },
};
const player = { x: 240, y: 224, flip: false, walk: false, target: null };
let camX = 0, near = null, hoverB = null, banner = { text: 'WELCOME TO REBOOT TOWN', sub: 'Walk to a building and press E', t: 3.2 }, lastVillage = 'jelly';
const villageAt = x => (x < 480 ? 'jelly' : 'drink');

// Villagers: little jellies in Jelly Village, little bottles in Drink Village.
const npcs = [];
for (let i = 0; i < 6; i++) npcs.push({ kind: 'jelly', f: FLAVORS[i % 3], line: i % 2, x: 30 + i * 74, y: rnd(206, 248), tx: null, wait: rnd(0, 3), ph: rnd(0, 6) });
for (let i = 0; i < 6; i++) npcs.push({ kind: 'bottle', f: FLAVORS[i % 3], line: (i + 1) % 2, x: 510 + i * 74, y: rnd(206, 248), tx: null, wait: rnd(0, 3), ph: rnd(0, 6) });
const STARS = Array.from({ length: 46 }, (_, i) => [(i * 97) % W, (i * 53) % 120, i % 3]);

function skyColors(k) { // k: 0 = jelly night, 1 = drink sunrise
  return [mix('#110c24', '#2a3a78', k), mix('#2a1b4f', '#e2796a', k), mix('#4b2a66', '#ffd27a', k)];
}
function drawSky(k, sunK = k) {
  const [a, b, c] = skyColors(k), g = C.createLinearGradient(0, 0, 0, GROUND);
  g.addColorStop(0, a); g.addColorStop(.6, b); g.addColorStop(1, c); C.fillStyle = g; C.fillRect(0, 0, W, GROUND);
  C.globalAlpha = 1 - smooth(k * 1.4);
  for (const [x, y, s] of STARS) R(x, y, 1, 1, (Math.floor(t * 2 + x) % 7 === 0 && s) ? '#fff' : '#cfc6ff');
  C.globalAlpha = 1;
  // moon fades out, sun rises
  if (k < .9) { C.globalAlpha = 1 - k; ocirc(400, 34, 10, '#fff4c8'); circ(404, 31, 9, mix('#110c24', '#2a3a78', k)); C.globalAlpha = 1; }
  if (sunK > .05) { const sy = lerp(190, 70, smooth(sunK)); glow(250, sy, 70, 'rgba(255,214,120,1)', .5 * sunK); ocirc(250, sy, 16, '#ffd25a'); R(240, sy - 8, 6, 2, '#fff1b8'); }
}
function mesas(scroll, y, col, seed) {
  let s = seed; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
  const off = ((scroll % 120) + 120) % 120;
  for (let x = -120 - off; x < W + 120; x += 120) {
    const h = 26 + Math.floor(r() * 30), w = 60 + Math.floor(r() * 50);
    R(x, y - h, w, h + 40, col); R(x - 8, y - h + 10, w + 16, h + 30, col);
  }
}
function cactus(x, y, c = '#2f5d2a') {
  shape([[x, y - 22, 6, 22], [x - 6, y - 14, 4, 7], [x - 6, y - 10, 6, 3], [x + 8, y - 18, 4, 8], [x + 6, y - 13, 6, 3]], c);
  R(x + 1, y - 21, 1, 18, mix(c, '#ffffff', .25));
}
function sign(cx, y, label, lit) {
  const w = Math.ceil(textW(label, 8)) + 12, x = Math.round(cx - w / 2);
  O(x, y, w, 12, lit ? NEON : '#1a1a1a'); R(x + 2, y + 12, 2, 6, '#3a2a1a'); R(x + w - 4, y + 12, 2, 6, '#3a2a1a');
  txt(label, cx, y + 6.5, { size: 8, color: lit ? INK : NEON });
}
function door(x, y, w = 14, h = 22, c = '#3d2a14') { O(x, y, w, h, c); R(x + w - 4, y + h / 2, 2, 2, '#ffd36b'); R(x + 2, y + 2, w - 4, 1, mix(c, '#fff', .2)); }
function win(x, y, w, h, c = '#ffd36b') { O(x, y, w, h, c); R(x, y + h / 2 - .5, w, 1, mix(c, INK, .4)); }

function drawBuilding(b, lit) {
  const X = b.x;
  if (b.id === 'lasso-leap') { // giant lime boot
    const c = FLAVOR.lime.jelly[0];
    shape([[X - 24, 98, 34, 64], [X - 24, 150, 54, 34], [X + 28, 158, 8, 26], [X + 34, 166, 6, 18], [X + 38, 172, 4, 12]], c);
    R(X + 2, 152, 26, 2, mix(c, '#fff', .3)); for (let i = 0; i < 4; i++) R(X - 18 + i * 6, 156 + (i % 2) * 3, 4, 1, mix(c, INK, .3));
    shape([[X - 28, 94, 42, 8]], mix(c, INK, .2));
    for (let i = 0; i < 6; i++) R(X - 20 + i * 5, 108, 2, 1, mix(c, INK, .35));
    R(X - 22, 100, 3, 48, mix(c, '#fff', .35));
    ocirc(X - 7, 124, 7, '#ffd36b'); R(X - 7, 117, 1, 14, mix('#ffd36b', INK, .4));
    shape([[X - 30, 176, 10, 8]], '#5a3a1f'); ocirc(X - 32, 172, 3, '#c9c5b2');
    door(X + 6, 162);
    sign(X + 8, 136, b.label, lit);
  } else if (b.id === 'jelly-drop') { // house under a giant cherry hat
    O(X - 36, 138, 72, 46, '#f3e3cf'); for (let i = 0; i < 4; i++) R(X - 36, 146 + i * 10, 72, 1, '#e0c9ae');
    const c = FLAVOR.cherry.jelly[0];
    shape([[X - 56, 126, 112, 8], [X - 50, 122, 100, 4]], c);
    shape([[X - 26, 92, 52, 32]], c); R(X - 4, 92, 8, 4, mix(c, INK, .3));
    R(X - 26, 112, 52, 6, '#151515'); R(X - 2, 112, 4, 6, NEON); R(X - 3, 114, 6, 2, NEON);
    R(X - 22, 96, 3, 14, mix(c, '#fff', .35)); R(X - 52, 126, 20, 2, mix(c, '#fff', .3));
    win(X - 30, 148, 14, 12); win(X + 16, 148, 14, 12); door(X - 7, 162);
    drawJelly(X - 23, 154, 'cherry', 1, 1); drawJelly(X + 23, 154, 'cherry', 0, 1);
    sign(X, 76, b.label, lit);
  } else if (b.id === 'store-jelly') { // black jelly pouch
    shape([[X - 34, 96, 68, 88], [X - 30, 92, 60, 4]], '#171717');
    for (let i = 0; i < 9; i++) R(X - 30 + i * 7, 92, 3, 2, '#2c2c2c');
    R(X - 30, 104, 60, 8, NEON); txt('REBOOT', X, 108.5, { size: 8, color: INK });
    O(X - 24, 118, 48, 26, '#2a3a1c'); drawJelly(X - 13, 134, 'lime', 0); drawJelly(X + 1, 134, 'lemon', 0); drawJelly(X + 15, 134, 'cherry', 0);
    txt('JELLY', X, 152, { size: 8, color: NEON });
    door(X - 7, 162, 14, 22, '#2e2e2e');
    glow(X, 108, 50, 'rgba(177,255,59,1)', .12 + .05 * Math.sin(t * 3));
    sign(X, 76, b.label, lit);
  } else if (b.id === 'bottle-pop') { // giant lemon bottle tower
    shape([[X - 9, 64, 18, 8]], '#0f2a12');
    shape([[X - 9, 72, 18, 14], [X - 18, 86, 36, 6], [X - 24, 92, 48, 92]], '#dff3ea');
    R(X - 22, 118, 44, 64, FLAVOR.lemon.drink[0]); R(X - 22, 118, 44, 2, mix(FLAVOR.lemon.drink[0], '#fff', .4));
    R(X - 24, 136, 48, 18, '#151515'); txt('REBOOT', X, 145.5, { size: 8, color: NEON });
    R(X - 20, 94, 4, 84, 'rgba(255,255,255,.75)');
    for (let i = 0; i < 4; i++) { const by = 176 - ((t * 10 + i * 9) % 50); R(X + 8 - i * 6, by, 2, 2, '#fff9cf'); }
    door(X - 7, 162, 14, 22, '#5c6a2a');
    sign(X, 48, b.label, lit);
  } else if (b.id === 'sunrise-flight') { // balloon port
    const by = 92 + Math.sin(t * 1.6) * 3;
    C.strokeStyle = '#3a2a1a'; C.lineWidth = 1; C.beginPath(); C.moveTo(X - 6, by + 30); C.lineTo(X - 30, 178); C.moveTo(X + 6, by + 30); C.lineTo(X + 30, 178); C.stroke();
    drawBalloon(X, by, 1.25, false);
    O(X - 38, 174, 76, 10, '#6b4226'); R(X - 38, 174, 76, 2, '#8a5a32');
    O(X + 46, 152, 18, 22, '#f3e3cf'); R(X + 46, 152, 18, 4, PINK); R(X + 50, 160, 10, 7, '#7ec8e3');
    sign(X, 150, b.label, lit);
  } else if (b.id === 'store-drink') { // Mixed Box building
    O(X - 44, 112, 88, 72, CREAM); R(X - 44, 112, 88, 14, '#151515'); txt('MIXED BOX OF 3', X, 119.5, { size: 8, color: NEON });
    ['lemon', 'lime', 'cherry'].forEach((f, i) => { ocirc(X - 26 + i * 26, 144, 10, '#dff3ea'); drawBottle(X - 26 + i * 26, 155, f, 0, 1); });
    for (let i = 0; i < 11; i++) R(X - 44 + i * 8, 126, 8, 4, i % 2 ? PINK : CREAM);
    door(X - 7, 162, 14, 22, '#7a3a4a');
    sign(X, 92, b.label, lit);
  }
}

function drawBalloon(x, y, s = 1, burner = false) {
  C.save(); C.translate(Math.round(x), Math.round(y)); C.scale(s, s);
  ocirc(0, 0, 18, FLAVOR.lemon.jelly[0]);
  R(-11, -15, 7, 30, FLAVOR.cherry.jelly[0]); R(4, -15, 7, 30, FLAVOR.lime.jelly[0]); R(-4, -18, 8, 36, FLAVOR.lemon.jelly[0]);
  R(-13, -6, 26, 4, '#151515'); R(-5, -5, 10, 2, NEON);
  R(-8, -14, 3, 6, 'rgba(255,255,255,.55)');
  shape([[-6, 16, 12, 4]], '#2a2a2a');
  R(-6, 20, 1, 8, '#3a2a1a'); R(5, 20, 1, 8, '#3a2a1a');
  if (burner) { R(-2, 20 - Math.random() * 3, 4, 3, '#ffb13b'); R(-1, 19 - Math.random() * 2, 2, 2, '#fff2a8'); }
  C.restore();
}

function drawTown(dt) {
  const k = smooth((camX + 240 - 360) / 240);
  drawSky(k);
  mesas(camX * .2, 150, mix('#24183d', '#8a4e5e', k), 7);
  mesas(camX * .35 + 40, 166, mix('#1b1230', '#6a3a4a', k), 3);
  C.save(); C.translate(-Math.round(camX * .6), 0);
  for (let x = 20; x < WORLD * .6 + W; x += 95) cactus(x, 182, mix('#22401f', '#3a5e2a', k));
  C.restore();
  C.save(); C.translate(-Math.round(camX), 0);
  // ground
  R(0, GROUND, WORLD, 16, mix('#2b2340', '#5a4a3a', .5)); R(0, GROUND, WORLD, 2, '#4a3f5e');
  R(0, GROUND + 16, WORLD, 70, '#b98a5c'); R(0, GROUND + 16, WORLD, 2, '#8a6440');
  for (let i = 0; i < 70; i++) R((i * 71) % WORLD, 206 + (i * 37) % 44, 3, 1, '#a57a4f');
  // lamps + bunting
  for (const lx of [40, 176, 312, 448, 520, 650, 790, 930]) {
    R(lx, 140, 2, 44, '#2a2433'); O(lx - 3, 134, 8, 7, '#ffd36b'); glow(lx + 1, 138, 22, 'rgba(255,214,120,1)', .3 + .05 * Math.sin(t * 4 + lx));
  }
  for (let i = 0; i < 95; i++) { const xx = 40 + i * 10, sag = Math.sin((i % 13.6) / 13.6 * Math.PI) * 6; if (xx > 930) break; R(xx, 140 + sag, 3, 3, [FLAVOR.lime.jelly[0], FLAVOR.lemon.jelly[0], FLAVOR.cherry.jelly[0]][i % 3]); }
  for (const b of BUILDINGS) drawBuilding(b, near === b.id || hoverB === b.id);
  // village gate
  O(440, 108, 6, 76, '#5a3a1f'); O(534, 108, 6, 76, '#5a3a1f'); O(432, 98, 116, 18, '#151515');
  txt('◀ JELLY', 462, 107.5, { size: 8, color: FLAVOR.cherry.jelly[0] }); R(489, 102, 2, 10, '#444'); txt('DRINK ▶', 518, 107.5, { size: 8, color: FLAVOR.lemon.jelly[0] });
  for (const b of BUILDINGS) if (near === b.id || hoverB === b.id) glow(b.x, 178, 30, 'rgba(177,255,59,1)', .25 + .1 * Math.sin(t * 6));
  // actors sorted by depth
  const actors = npcs.map(n => ({ y: n.y, draw: () => n.kind === 'jelly' ? drawJelly(n.x, n.y - 4 - Math.abs(Math.sin((t + n.ph) * 5)) * 3, n.f, n.line, 1, true) : drawBottle(n.x, n.y - Math.abs(Math.sin((t + n.ph) * 4)) * 2, n.f, n.line, 1, true) }));
  actors.push({ y: player.y, draw: () => drawRebu(player.x, player.y, { flip: player.flip, walk: player.walk }) });
  actors.sort((a, b) => a.y - b.y).forEach(a => a.draw());
  if (near && scene === 'town') {
    const b = BUILDINGS.find(q => q.id === near), label = b.store ? 'E · ENTER STORE' : 'E · PLAY';
    const w = textW(label) + 12; panel(player.x - w / 2, player.y - 46, w, 13, CREAM); txt(label, player.x, player.y - 39.5, { color: INK });
  }
  C.restore();
  // banner
  if (banner.t > 0) {
    banner.t -= dt; const a = clamp(banner.t, 0, 1);
    C.globalAlpha = a; panel(W / 2 - 120, 14, 240, 36, '#151515');
    txt(banner.text, W / 2, 26, { size: 16, color: NEON, font: PIX }); txt(banner.sub, W / 2, 41, { size: 8, color: CREAM });
    C.globalAlpha = 1;
  }
  // mini map
  R(W - 92, H - 14, 84, 6, 'rgba(0,0,0,.45)'); R(W - 92, H - 14, 42, 6, 'rgba(249,49,110,.45)'); R(W - 50, H - 14, 42, 6, 'rgba(248,190,20,.45)');
  R(W - 92 + player.x / WORLD * 84 - 1, H - 16, 3, 10, NEON);
}

function updateTown(dt) {
  let dx = 0, dy = 0;
  if (held('ArrowLeft', 'KeyA')) dx--; if (held('ArrowRight', 'KeyD')) dx++;
  if (held('ArrowUp', 'KeyW')) dy--; if (held('ArrowDown', 'KeyS')) dy++;
  if (dx || dy) player.target = null;
  else if (player.target) {
    const tx = player.target.x - player.x, ty = player.target.y - player.y, d = Math.hypot(tx, ty);
    if (d < 3) { const enter = player.target.enter; player.target = null; if (enter) return activate(enter); }
    else { dx = tx / d; dy = ty / d; }
  }
  const sp = 92; const len = Math.hypot(dx, dy) || 1;
  player.x = clamp(player.x + dx / len * sp * dt, 12, WORLD - 12);
  player.y = clamp(player.y + dy / len * sp * .7 * dt, Y_MIN, Y_MAX);
  player.walk = !!(dx || dy); if (dx) player.flip = dx < 0;
  camX = clamp(player.x - W / 2, 0, WORLD - W);
  near = null;
  if (player.y < 216) for (const b of BUILDINGS) if (Math.abs(player.x - b.x) < 24) near = b.id;
  const v = villageAt(player.x);
  if (v !== lastVillage) { lastVillage = v; banner = { text: VILLAGES[v].name, sub: VILLAGES[v].sub, t: 2.6 }; sfx('chime'); }
  for (const n of npcs) {
    const lo = n.kind === 'jelly' ? 16 : 496, hi = n.kind === 'jelly' ? 464 : 944;
    if (n.tx === null) { n.wait -= dt; if (n.wait <= 0) { n.tx = clamp(n.x + rnd(-70, 70), lo, hi); n.ty = rnd(Y_MIN + 4, Y_MAX); } }
    else { const ddx = n.tx - n.x, ddy = n.ty - n.y, d = Math.hypot(ddx, ddy); if (d < 2) { n.tx = null; n.wait = rnd(1, 4); } else { n.x += ddx / d * 26 * dt; n.y += ddy / d * 18 * dt; } }
  }
}

function goVillage(v) {
  if (scene !== 'town') exitGame();
  player.x = v === 'jelly' ? 240 : 720; player.y = 224; player.target = null;
  camX = clamp(player.x - W / 2, 0, WORLD - W);
  lastVillage = v; banner = { text: VILLAGES[v].name, sub: VILLAGES[v].sub, t: 2.6 };
  stage.focus();
}
function activate(id) {
  const b = BUILDINGS.find(q => q.id === id); if (!b) return;
  if (b.store) openStore(b.store); else enterGame(id);
}

/* ================= MINI GAMES ================= */
const INFO = {
  'lasso-leap':     { place: 'JELLY VILLAGE · BOOT BARN', goal: 'Hop through the lasso gates. Jellies = +1 bonus.', how: 'SPACE / CLICK / TAP = HOP' },
  'jelly-drop':     { place: 'JELLY VILLAGE · HAT HOUSE', goal: 'Boot + Lasso + Hat = PACK +5. Dodge tumbleweeds!', how: '← → / A D / MOUSE / DRAG = MOVE' },
  'bottle-pop':     { place: 'DRINK VILLAGE · BOTTLE TOWER', goal: 'Pop bottles that match the order. Box = +3. 30 s.', how: 'CLICK / TAP  ·  OR  Q W E / A S D' },
  'sunrise-flight': { place: 'DRINK VILLAGE · BALLOON PORT', goal: 'Fly from midnight to sunrise. Drops = +15 m.', how: 'HOLD SPACE / CLICK = RISE' },
};
let scene = 'town', G = null;
const pops = [], parts = [];
function pop(x, y, s, c = NEON) { pops.push({ x, y, s, c, t: 0 }); }
function burst(x, y, c, n = 10) { for (let i = 0; i < n; i++) { const a = Math.PI * 2 * i / n + Math.random() * .5; parts.push({ x, y, vx: Math.cos(a) * rnd(30, 80), vy: Math.sin(a) * rnd(30, 80) - 30, c, l: .6 }); } }
function fx(dt) {
  for (const p of parts) { p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 180 * dt; p.l -= dt; R(p.x, p.y, 2, 2, p.c); }
  for (let i = parts.length - 1; i >= 0; i--) if (parts[i].l <= 0) parts.splice(i, 1);
  for (const p of pops) { p.t += dt; txt(p.s, p.x, p.y - p.t * 26, { size: 8, color: p.c, stroke: INK, sw: 3 }); }
  for (let i = pops.length - 1; i >= 0; i--) if (pops[i].t > .8) pops.splice(i, 1);
}
function hud(label, value, extra) {
  panel(8, 8, 98, 22, '#151515'); txt(label, 14, 15, { size: 8, color: '#a7aa9d', align: 'left' });
  txt(String(value), 100, 21, { size: 16, color: NEON, align: 'right' });
  if (extra) txt(extra, W - 10, 16, { size: 8, color: CREAM, align: 'right', stroke: INK });
}
function readyCard() {
  const g = DATA.games[G.id], info = INFO[G.id];
  C.fillStyle = 'rgba(10,8,20,.55)'; C.fillRect(0, 0, W, H);
  panel(90, 44, 300, 170, CREAM);
  txt(info.place, 240, 60, { size: 8, color: '#4c6b16' });
  txt(g.name.toUpperCase(), 240, 82, { size: 32, color: INK, font: DISP, weight: '800' });
  txt(info.goal, 240, 106, { size: 8, color: '#3a3d33' });
  txt(info.how, 240, 122, { size: 8, color: '#3a3d33' });
  R(110, 134, 260, 1, '#d6d4c4');
  const best = bestOf(G.id);
  txt(`POINTS: ${g.rule.toUpperCase()} · MAX ${DATA.runCap} P / RUN`, 240, 146, { size: 8, color: INK });
  txt(best !== null ? `YOUR BEST: ${best} ${g.unit.toUpperCase()}` : 'NO BEST SCORE YET', 240, 160, { size: 8, color: '#6a6d60' });
  const note = DATA.role === 'customer' ? (todayLeft() > 0 ? `${todayLeft()} P LEFT TODAY` : 'DAILY CAP REACHED · PLAY FOR FUN') : DATA.role === 'guest' ? 'GUEST MODE · LOG IN TO EARN POINTS' : 'ADMIN · PLAY ONLY';
  txt(note, 240, 174, { size: 8, color: DATA.role === 'customer' && todayLeft() > 0 ? '#4c6b16' : '#7a4ab0' });
  if (Math.floor(t * 2) % 2) { O(170, 186, 140, 18, NEON); txt('CLICK / SPACE TO START', 240, 195.5, { size: 8, color: INK }); }
}

/* --- 1. LASSO LEAP (Jelly Village) --- */
function makeLeap() {
  return {
    y: 120, vy: 0, gates: [], score: 0, dist: 0, nextGate: 60, speed: 95, dead: false, tilt: 0,
    action() { if (this.phase !== 'play') return; this.vy = -172; sfx('hop'); },
    update(dt) {
      this.speed = Math.min(150, 95 + this.score * 1.2);
      this.dist += this.speed * dt; this.vy = Math.min(this.vy + 520 * dt, 260); this.y += this.vy * dt;
      if (this.y < 26) { this.y = 26; this.vy = 0; }
      this.nextGate -= this.speed * dt;
      if (this.nextGate <= 0) {
        const gap = Math.max(66, 82 - this.score * .6), cy = rnd(70, 196);
        const f = pick(FLAVORS);
        this.gates.push({ x: W + 10, top: cy - gap / 2, bot: cy + gap / 2, passed: false, jelly: Math.random() < .55 ? { f, line: Math.random() < .5 ? 0 : 1, got: false } : null });
        this.nextGate = 150;
      }
      for (const g of this.gates) {
        g.x -= this.speed * dt;
        if (!g.passed && g.x + 24 < 80) { g.passed = true; this.score++; sfx('coin'); pop(92, this.y - 30, '+1'); }
        if (g.jelly && !g.got && Math.hypot(g.x + 12 - 88, (g.top + g.bot) / 2 - (this.y - 12)) < 13) { g.jelly.got = true; this.score++; sfx('coin'); burst(g.x + 12, (g.top + g.bot) / 2, FLAVOR[g.jelly.f].jelly[g.jelly.line]); pop(g.x + 12, (g.top + g.bot) / 2 - 10, 'JELLY +1', FLAVOR[g.jelly.f].jelly[0]); }
        const hx = 80, hy = this.y - 22, hw = 17, hh = 20;
        if (hx + hw > g.x + 2 && hx < g.x + 22 && (hy < g.top || hy + hh > g.bot)) return this.crash();
      }
      this.gates = this.gates.filter(g => g.x > -40);
      if (this.y > 244) return this.crash();
      this.tilt = clamp(this.vy / 600, -.35, .45);
    },
    crash() { if (this.dead) return; this.dead = true; sfx('hit'); burst(88, this.y - 12, REBU, 14); endRun(this.score); },
    draw() {
      drawSky(.15, 0); mesas(this.dist * .25, 186, '#2a1b48', 5); mesas(this.dist * .5 + 60, 206, '#1f1436', 9);
      R(0, 244, W, 26, '#b98a5c'); R(0, 244, W, 2, '#8a6440');
      for (let i = 0; i < 16; i++) R(((i * 41) - this.dist) % W + (((i * 41) - this.dist) % W < 0 ? W : 0), 252 + i % 3 * 5, 4, 1, '#a57a4f');
      for (const g of this.gates) {
        O(g.x, -2, 24, g.top + 2, '#8a5a32'); O(g.x, g.bot, 24, 244 - g.bot, '#8a5a32');
        for (let yy = 6; yy < g.top - 4; yy += 12) R(g.x + 2, yy, 20, 1, '#6e4526');
        for (let yy = g.bot + 8; yy < 240; yy += 12) R(g.x + 2, yy, 20, 1, '#6e4526');
        O(g.x - 3, g.top - 6, 30, 6, '#5a3a1f'); O(g.x - 3, g.bot, 30, 6, '#5a3a1f');
        C.strokeStyle = FLAVOR.lemon.jelly[0]; C.lineWidth = 2; C.beginPath(); C.ellipse(g.x + 12, g.top - 3, 13, 3, 0, 0, Math.PI * 2); C.stroke(); C.beginPath(); C.ellipse(g.x + 12, g.bot + 3, 13, 3, 0, 0, Math.PI * 2); C.stroke();
        if (g.jelly && !g.jelly.got) drawJelly(g.x + 12, (g.top + g.bot) / 2 + Math.sin(t * 5) * 2, g.jelly.f, g.jelly.line, 1.4);
      }
      drawRebu(88, this.y, { tilt: this.tilt, happy: this.vy < 0 });
      hud('GATES', this.score);
    },
  };
}

/* --- 2. JELLY DROP (Jelly Village) --- */
function makeDrop() {
  return {
    x: 240, tx: null, items: [], score: 0, hearts: 3, pack: new Set(), spawn: 0, time: 0, flash: 0,
    action() {},
    move(px) { this.tx = px; },
    update(dt) {
      this.time += dt;
      let dx = 0; if (held('ArrowLeft', 'KeyA')) dx--; if (held('ArrowRight', 'KeyD')) dx++;
      if (dx) { this.tx = null; this.x += dx * 210 * dt; } else if (this.tx !== null) this.x = lerp(this.x, this.tx, Math.min(1, dt * 12));
      this.x = clamp(this.x, 16, W - 16);
      this.spawn -= dt;
      if (this.spawn <= 0) {
        this.spawn = Math.max(.4, .85 - this.time * .01);
        const hazard = Math.random() < Math.min(.32, .14 + this.time * .004);
        this.items.push(hazard ? { hazard: true, x: rnd(14, W - 14), y: -10, v: rnd(80, 100) + this.time * 1.4 }
          : { f: pick(FLAVORS), line: Math.random() < .5 ? 0 : 1, x: rnd(14, W - 14), y: -10, v: rnd(64, 86) + this.time * 1.4, r: rnd(-1, 1) });
      }
      for (const it of this.items) {
        it.y += it.v * dt;
        if (!it.done && it.y > 206 && it.y < 224 && Math.abs(it.x - this.x) < 18) {
          it.done = true;
          if (it.hazard) { this.hearts--; this.flash = .4; sfx('hit'); burst(it.x, it.y, '#a8834f'); if (this.hearts <= 0) return endRun(this.score); }
          else {
            this.score++; sfx('coin'); this.pack.add(FLAVOR[it.f].shape); pop(it.x, 196, '+1', FLAVOR[it.f].jelly[0]);
            if (this.pack.size === 3) { this.score += 5; this.pack.clear(); sfx('chime'); pop(this.x, 176, 'PACK COMPLETE +5', NEON); burst(this.x, 200, NEON, 16); }
          }
        }
      }
      this.items = this.items.filter(it => !it.done && it.y < 280);
      this.flash = Math.max(0, this.flash - dt);
    },
    draw() {
      drawSky(.05, 0); mesas(40, 200, '#2a1b48', 2);
      R(0, 232, W, 38, '#b98a5c'); R(0, 232, W, 2, '#8a6440');
      for (const it of this.items) it.hazard ? drawTumbleweed(it.x, it.y) : drawJelly(it.x, it.y, it.f, it.line, 1.5);
      drawRebu(this.x, 248, { walk: !!(held('ArrowLeft', 'KeyA', 'ArrowRight', 'KeyD')), flip: false });
      drawPackage(this.x, 222, 0, 1.2); // open pouch held over Rebu's head
      if (this.flash) { C.fillStyle = `rgba(255,60,90,${this.flash})`; C.fillRect(0, 0, W, H); }
      hud('SCORE', this.score);
      for (let i = 0; i < 3; i++) shape([[W - 62 + i * 18, 12, 4, 3], [W - 57 + i * 18, 12, 4, 3], [W - 63 + i * 18, 14, 11, 4], [W - 61 + i * 18, 18, 7, 2], [W - 59 + i * 18, 20, 3, 1]], i < this.hearts ? '#ff5c8a' : '#444');
      panel(W / 2 - 46, 8, 92, 22, '#151515'); txt('PACK', W / 2 - 30, 19, { size: 8, color: '#a7aa9d' });
      ['lime', 'lemon', 'cherry'].forEach((f, i) => { C.globalAlpha = this.pack.has(FLAVOR[f].shape) ? 1 : .25; drawJelly(W / 2 - 4 + i * 16, 20, f, 0, 1); C.globalAlpha = 1; });
    },
  };
}

/* --- 3. BOTTLE POP (Drink Village) --- */
function makePop() {
  const slots = []; for (let r = 0; r < 2; r++) for (let c = 0; c < 3; c++) slots.push({ x: 150 + c * 90, y: 142 + r * 84, item: null, key: [['KeyQ', 'KeyW', 'KeyE'], ['KeyA', 'KeyS', 'KeyD']][r][c], hit: 0 });
  return {
    slots, score: 0, time: 30, order: pick(FLAVORS), orderT: 6, spawn: .4, ended: false,
    action() {},
    click(px, py) { for (const s of this.slots) if (Math.abs(px - s.x) < 34 && py > s.y - 50 && py < s.y + 8) return this.hit(s); },
    key(code) { const s = this.slots.find(q => q.key === code); if (s) { this.hit(s); return true; } return false; },
    hit(s) {
      if (this.phase !== 'play' || !s.item || s.item.out) return;
      const it = s.item; it.out = true; s.hit = .25;
      if (it.box) { this.score += 3; sfx('chime'); pop(s.x, s.y - 50, 'MIXED BOX +3', '#ffd84a'); burst(s.x, s.y - 20, '#ffd84a', 14); }
      else if (it.f === this.order) { this.score++; sfx('pop'); pop(s.x, s.y - 50, '+1', FLAVOR[it.f].drink[0]); burst(s.x, s.y - 24, FLAVOR[it.f].drink[0]); }
      else { this.score = Math.max(0, this.score - 1); sfx('wrong'); pop(s.x, s.y - 50, 'WRONG −1', '#ff5c8a'); }
    },
    update(dt) {
      this.time -= dt; this.orderT -= dt;
      if (this.time <= 0 && !this.ended) { this.ended = true; return endRun(this.score); }
      if (this.orderT <= 0) { const prev = this.order; while (this.order === prev) this.order = pick(FLAVORS); this.orderT = 6; sfx('chime'); }
      this.spawn -= dt;
      if (this.spawn <= 0) {
        this.spawn = rnd(.45, .7);
        const free = this.slots.filter(s => !s.item);
        if (free.length) {
          const s = pick(free), life = Math.max(.9, 1.6 - (30 - this.time) * .02);
          s.item = Math.random() < .06 ? { box: true, life, age: 0 } : { f: Math.random() < .45 ? this.order : pick(FLAVORS), line: Math.random() < .5 ? 0 : 1, life, age: 0 };
        }
      }
      for (const s of this.slots) {
        s.hit = Math.max(0, s.hit - dt);
        if (s.item) { s.item.age += dt; if (s.item.out) s.item.age = Math.max(s.item.age, s.item.life); if (s.item.age > s.item.life + .2) s.item = null; }
      }
    },
    draw() {
      drawSky(.55, .3);
      R(0, 70, W, 200, '#3a2433'); for (let i = 0; i < 12; i++) R(i * 40, 70, 20, 200, '#40283a');
      R(0, 66, W, 8, '#151515'); for (let i = 0; i < 24; i++) R(i * 20 + 4, 67, 10, 3, [FLAVOR.lime.jelly[0], FLAVOR.lemon.jelly[0], FLAVOR.cherry.jelly[0]][i % 3]);
      for (const s of this.slots) {
        const it = s.item; let rise = 0;
        if (it) { const a = it.age, l = it.life; rise = a < .15 ? a / .15 : a > l ? Math.max(0, 1 - (a - l) / .2) : 1; }
        O(s.x - 30, s.y - 56, 60, 56, '#24161f'); R(s.x - 30, s.y - 56, 60, 3, '#3a2433'); R(s.x - 26, s.y - 50, 52, 1, '#2e1c28');
        C.save(); C.beginPath(); C.rect(s.x - 40, s.y - 70, 80, 70); C.clip();
        if (it) it.box ? drawBox3(s.x, s.y + 22 - rise * 26, 1.7, true) : drawBottle(s.x, s.y + 40 - rise * 42, it.f, it.line, 2.3, true);
        C.restore();
        O(s.x - 38, s.y, 76, 14, '#6b4226'); R(s.x - 38, s.y, 76, 3, '#8a5a32');
        txt(s.key.slice(3), s.x, s.y + 8, { size: 8, color: '#f3d7a8' });
        if (s.hit) glow(s.x, s.y - 20, 34, 'rgba(255,255,255,1)', s.hit);
      }
      // order ticket
      panel(W / 2 - 70, 8, 140, 44, CREAM);
      txt('ORDER', W / 2 - 32, 19, { size: 8, color: '#6a6d60' }); txt(FLAVOR[this.order].name, W / 2 - 32, 34, { size: 16, color: FLAVOR[this.order].drink[0], stroke: INK, sw: 3 });
      drawBottle(W / 2 + 40, 46, this.order, 0, 1.7);
      R(W / 2 - 66, 47, 132 * clamp(this.orderT / 6, 0, 1), 2, '#c9c5b2');
      hud('SCORE', this.score);
      panel(W - 72, 8, 64, 22, '#151515'); txt(`${Math.max(0, Math.ceil(this.time))}s`, W - 40, 19.5, { size: 16, color: this.time < 6 ? '#ff5c8a' : CREAM });
    },
  };
}

/* --- 4. SUNRISE FLIGHT (Drink Village) --- */
function makeFlight() {
  return {
    y: 120, vy: 0, px: 0, meters: 0, bonus: 0, obs: [], drops: [], nextObs: 1.2, nextDrop: 1.4, dead: false, holding: false, greeted: false,
    get score() { return Math.floor(this.meters + this.bonus); },
    action() {},
    update(dt) {
      const holding = held('Space', 'ArrowUp', 'KeyW') || mouse.down;
      this.holding = holding;
      if (holding && Math.random() < .3) sfx('burn');
      this.vy += (holding ? -330 : 230) * dt; this.vy = clamp(this.vy, -150, 170); this.y += this.vy * dt;
      if (this.y < 30) { this.y = 30; this.vy = 0; }
      const speed = Math.min(115, 62 + this.meters * .03);
      this.px += speed * dt; this.meters = this.px / 10;
      this.nextObs -= dt; this.nextDrop -= dt;
      if (this.nextObs <= 0) { this.nextObs = rnd(1.0, 1.7) * Math.max(.7, 1 - this.meters / 4000); this.obs.push(Math.random() < .6 ? { cloud: true, x: W + 30, y: rnd(40, 230), w: rnd(34, 54) } : { bird: true, x: W + 20, y: rnd(40, 220), vy: rnd(-12, 12) }); }
      if (this.nextDrop <= 0) { this.nextDrop = rnd(2.0, 2.6); this.drops.push({ x: W + 10, y: rnd(50, 220), f: pick(FLAVORS) }); }
      const by = this.y;
      for (const o of this.obs) {
        o.x -= speed * dt * (o.bird ? 1.4 : 1); if (o.bird) o.y += o.vy * dt;
        const hit = o.cloud ? (Math.abs(o.x - 92) < o.w / 2 + 10 && Math.abs(o.y - by) < 16) : (Math.abs(o.x - 92) < 16 && Math.abs(o.y - by) < 16);
        if (hit) return this.crash();
      }
      for (const d of this.drops) { d.x -= speed * dt; if (!d.got && Math.hypot(d.x - 92, d.y - by) < 18) { d.got = true; this.bonus += 15; sfx('coin'); pop(d.x, d.y - 10, '+15 m', FLAVOR[d.f].drink[0]); burst(d.x, d.y, FLAVOR[d.f].drink[0]); } }
      this.obs = this.obs.filter(o => o.x > -60); this.drops = this.drops.filter(d => d.x > -20 && !d.got);
      if (this.y > 238) return this.crash();
      if (!this.greeted && this.meters >= 1200) { this.greeted = true; banner = { text: 'GOOD MORNING!', sub: 'RESTART YOUR DAY', t: 2.4 }; sfx('chime'); }
    },
    crash() { if (this.dead) return; this.dead = true; sfx('hit'); burst(92, this.y, FLAVOR.lemon.jelly[0], 16); endRun(this.score); },
    draw(dt) {
      const k = clamp(this.meters / 1200, 0, 1);
      drawSky(k, k);
      mesas(this.px * .15, 226, mix('#1b1230', '#7a4a5a', k), 4); mesas(this.px * .3 + 50, 246, mix('#140d24', '#5a3444', k), 8);
      for (const d of this.drops) { ocirc(d.x, d.y, 6, FLAVOR[d.f].drink[0]); R(d.x - 2, d.y - 3, 2, 2, '#fff'); }
      for (const o of this.obs) {
        if (o.cloud) { const c = mix('#3a3550', '#6d6080', k); ocirc(o.x - o.w / 4, o.y + 2, 10, c); ocirc(o.x + o.w / 4, o.y + 2, 11, c); ocirc(o.x, o.y - 4, 13, c); R(o.x - 3, o.y + 10, 3, 6, '#ffe066'); R(o.x - 1, o.y + 14, 3, 5, '#ffe066'); }
        else { const f = Math.floor(t * 10) % 2; shape([[o.x - 5, o.y - 2, 10, 5], [o.x - 9, o.y - 4 - f * 3, 5, 2], [o.x + 4, o.y - 4 - f * 3, 5, 2]], '#2a2433'); R(o.x - 6, o.y - 1, 2, 1, '#ffb13b'); }
      }
      drawBalloon(92, this.y - 28, .95, this.holding);
      drawRebu(92, this.y + 2, { s: .7, noBoots: true, happy: true });
      hud('METERS', this.score, this.meters < 1200 ? `SUNRISE IN ${Math.ceil(1200 - this.meters)} m` : 'SUNRISE ✓');
    },
  };
}
const MAKERS = { 'lasso-leap': makeLeap, 'jelly-drop': makeDrop, 'bottle-pop': makePop, 'sunrise-flight': makeFlight };

/* ================= FLOW + SERVER ================= */
let status = DATA.status; // null for guests/admins
const localBest = (() => { try { return JSON.parse(localStorage.getItem('rebootTownBest') || '{}'); } catch (e) { return {}; } })();
function bestOf(id) {
  const a = status && status.best && status.best[id] !== undefined ? status.best[id] : null, b = localBest[id] !== undefined ? localBest[id] : null;
  return a === null ? b : b === null ? a : Math.max(a, b);
}
function todayLeft() { return status ? Math.max(0, DATA.dailyCap - status.today_earned) : 0; }
function pointsFor(id, score) { const g = DATA.games[id]; return Math.min(DATA.runCap, Math.floor(score / g.per) * g.points); }
async function api(path, body) {
  const res = await fetch(path, { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (res.redirected || !(res.headers.get('Content-Type') || '').includes('application/json')) throw new Error('Please sign in again to save points.');
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Could not reach the server.');
  return data;
}
function applyStatus(s) {
  if (!s) return; status = Object.assign(status || {}, s);
  document.querySelectorAll('[data-point-balance]').forEach(el => { el.textContent = s.balance; });
  document.querySelectorAll('[data-game-today]').forEach(el => { el.textContent = s.today_earned; });
  const meter = document.querySelector('[data-game-meter]');
  if (meter) { meter.setAttribute('aria-valuenow', s.today_earned); meter.firstElementChild.style.width = (s.today_earned / s.daily_cap * 100) + '%'; }
  const reset = document.querySelector('[data-game-reset]'); if (reset && s.reset_at) reset.dataset.resetAt = s.reset_at;
}

function enterGame(id) {
  scene = 'game'; G = MAKERS[id](); G.id = id; G.phase = 'ready'; G.run = null;
  pops.length = 0; parts.length = 0; banner.t = 0; keys.clear(); mouse.down = false;
  $('game-back').hidden = false; closeOverlays(); sfx('chime'); stage.focus();
}
function beginRun() {
  G.phase = 'play'; sfx('start');
  if (DATA.role === 'customer') G.run = api('/game/api/runs', { game: G.id }).catch(err => ({ error: err.message }));
}
function exitGame() {
  scene = 'town'; G = null; keys.clear(); mouse.down = false; $('game-back').hidden = true; closeOverlays(); stage.focus();
}
async function endRun(score) {
  if (!G || G.phase === 'over') return;
  G.phase = 'over'; G.endAt = t; const id = G.id, g = DATA.games[id], game = G;
  const prevBest = bestOf(id), isBest = prevBest === null || score > prevBest;
  if (isBest) { localBest[id] = score; try { localStorage.setItem('rebootTownBest', JSON.stringify(localBest)); } catch (e) {} }
  sfx(isBest && score > 0 ? 'win' : 'over');
  $('game-result-place').textContent = INFO[id].place;
  $('game-result-title').textContent = isBest && score > 0 ? 'NEW BEST!' : (id === 'bottle-pop' ? "TIME'S UP!" : 'GAME OVER');
  $('game-result-score').textContent = score.toLocaleString('en-US');
  $('game-result-unit').textContent = g.unit;
  $('game-result-best').textContent = prevBest === null ? 'First run!' : `Best: ${Math.max(prevBest, score).toLocaleString('en-US')} ${g.unit}`;
  const pts = $('game-result-points'); pts.classList.remove('off'); $('game-login').hidden = true;
  const possible = pointsFor(id, score);
  if (DATA.role === 'guest') {
    pts.classList.add('off'); $('game-login').hidden = false;
    pts.textContent = possible > 0 ? `This run is worth ${possible} P. Log in to keep your points next time.` : 'Log in to turn your scores into points.';
  } else if (DATA.role !== 'customer') {
    pts.classList.add('off'); pts.textContent = 'Admin accounts play for fun — no points.';
  } else {
    pts.textContent = 'Saving your score…';
  }
  setTimeout(() => { if (G === game) openOverlay('game-result'); }, 700);
  if (DATA.role !== 'customer') return;
  try {
    const run = await game.run;
    if (!run || run.error) throw new Error(run && run.error ? run.error : 'Could not start this run.');
    const res = await api(`/game/api/runs/${run.run_id}/finish`, { score });
    applyStatus(res);
    if (res.message) { pts.classList.add('off'); pts.textContent = res.message; }
    else if (res.points_earned > 0) pts.textContent = `+${res.points_earned} P added!` + (res.points_earned < res.points_possible ? ' (daily cap reached)' : '') + ` · Today ${res.today_earned} / ${res.daily_cap} P`;
    else if (res.points_possible > 0) { pts.classList.add('off'); pts.textContent = `You hit today’s ${res.daily_cap} P cap. Play for fun — new points after the reset.`; }
    else { pts.classList.add('off'); pts.textContent = `No points this time — ${g.rule}.`; }
  } catch (err) { pts.classList.add('off'); pts.textContent = err.message; }
}

/* ================= OVERLAYS ================= */
function openOverlay(id) { closeOverlays(); const el = $(id); el.hidden = false; const f = el.querySelector('button, a'); if (f) f.focus(); }
function closeOverlays() { for (const id of ['game-result', 'game-store']) $(id).hidden = true; }
const overlayOpen = () => !$('game-result').hidden || !$('game-store').hidden;
function money(v) { return '$' + Number(v).toFixed(2); }
function openStore(line) {
  sfx('chime');
  $('game-store-eyebrow').textContent = line === 'Jelly' ? 'JELLY VILLAGE · STORE' : 'DRINK VILLAGE · STORE';
  $('game-store-title').textContent = line === 'Jelly' ? 'Jelly packages' : 'Reboot drinks';
  $('game-store-note').textContent = (line === 'Jelly'
    ? 'Sold only as line packages: every pack has lime boot, lemon lasso and cherry hat jellies.'
    : '100 ml non-carbonated bottles. Buy single flavors or the Mixed Box of 3.') + ` 100 P = $1 at checkout.`
    + (status ? ` You have ${status.balance} P (${money(status.balance / DATA.pointsPerUsd)}).` : '');
  const grid = $('game-store-grid'); grid.replaceChildren();
  for (const p of DATA.products.filter(q => q.line === line)) {
    const card = document.createElement('div'); card.className = 'game-store-item';
    const img = document.createElement('img'); img.src = p.image; img.alt = p.name; img.loading = 'lazy';
    const box = document.createElement('div');
    const h = document.createElement('h3'); h.textContent = p.name + (p.balance ? ' · Zero Sugar' : '');
    box.append(h);
    for (const o of p.options.slice(0, 2)) { const q = document.createElement('p'); q.textContent = `${o.label} — ${money(o.price)} = ${Math.round(o.price * DATA.pointsPerUsd).toLocaleString('en-US')} P`; box.append(q); }
    const a = document.createElement('a'); a.href = '/products/' + p.slug; a.textContent = 'View product ↗'; box.append(a);
    card.append(img, box); grid.append(card);
  }
  openOverlay('game-store');
}
$('game-retry').addEventListener('click', () => { const id = G ? G.id : null; if (id) enterGame(id); });
$('game-home').addEventListener('click', exitGame);
$('game-back').addEventListener('click', exitGame);
$('game-store-close').addEventListener('click', () => { closeOverlays(); stage.focus(); });
document.querySelectorAll('[data-goto]').forEach(b => b.addEventListener('click', () => goVillage(b.dataset.goto)));
document.querySelectorAll('[data-play]').forEach(b => b.addEventListener('click', () => {
  const bl = BUILDINGS.find(q => q.id === b.dataset.play); player.x = bl.x; player.y = 206; camX = clamp(player.x - W / 2, 0, WORLD - W);
  stage.scrollIntoView({ behavior: 'smooth', block: 'center' }); enterGame(b.dataset.play);
}));

/* ================= INPUT ================= */
const keys = new Set(), mouse = { x: -99, y: -99, down: false };
const held = (...codes) => codes.some(c => keys.has(c));
function canvasPos(e) { const r = cv.getBoundingClientRect(); return { x: (e.clientX - r.left) / r.width * W, y: (e.clientY - r.top) / r.height * H }; }
function primary() { if (!G) return; if (G.phase === 'ready') return beginRun(); if (G.phase === 'play') G.action(); }
cv.addEventListener('pointerdown', e => {
  e.preventDefault(); stage.focus(); unlockAudio();
  const p = canvasPos(e); mouse.x = p.x; mouse.y = p.y; mouse.down = true;
  try { cv.setPointerCapture(e.pointerId); } catch (_) {}
  if (overlayOpen()) return;
  if (scene === 'town') {
    const wx = p.x + camX, b = BUILDINGS.find(q => wx >= q.box[0] && wx <= q.box[1] && p.y >= q.box[2] && p.y <= q.box[3]);
    if (b) { if (Math.abs(player.x - b.x) < 30 && player.y < 222) activate(b.id); else player.target = { x: b.x, y: 206, enter: b.id }; }
    else player.target = { x: clamp(wx, 12, WORLD - 12), y: clamp(p.y, Y_MIN, Y_MAX) };
    return;
  }
  if (G.phase === 'ready') return beginRun();
  if (G.phase === 'play') { if (G.click) G.click(p.x, p.y); else G.action(); if (G.move) G.move(p.x); }
});
cv.addEventListener('pointermove', e => {
  const p = canvasPos(e); mouse.x = p.x; mouse.y = p.y;
  if (scene === 'town') { const wx = p.x + camX; const b = BUILDINGS.find(q => wx >= q.box[0] && wx <= q.box[1] && p.y >= q.box[2] && p.y <= q.box[3]); hoverB = b ? b.id : null; cv.style.cursor = b ? 'pointer' : 'default'; }
  else if (G && G.move && G.phase === 'play' && (e.pointerType === 'mouse' || mouse.down)) G.move(p.x);
});
window.addEventListener('pointerup', () => { mouse.down = false; });
window.addEventListener('pointercancel', () => { mouse.down = false; });
const BLOCK = ['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];
stage.addEventListener('keydown', e => {
  if (e.target !== stage && e.target !== cv) return; // buttons inside overlays keep normal keys
  unlockAudio();
  if (BLOCK.includes(e.code)) e.preventDefault();
  if (e.code === 'Escape') { if (overlayOpen()) { closeOverlays(); if (scene === 'game' && G && G.phase === 'over') exitGame(); return; } if (scene === 'game') return exitGame(); }
  if (overlayOpen()) return;
  keys.add(e.code);
  if (e.repeat) return;
  if (scene === 'town') { if ((e.code === 'KeyE' || e.code === 'Enter' || e.code === 'Space') && near) activate(near); return; }
  if (G.phase === 'play' && G.key && G.key(e.code)) return;
  if (['Space', 'ArrowUp', 'KeyW', 'Enter'].includes(e.code)) primary();
});
stage.addEventListener('keyup', e => keys.delete(e.code));
['game-result', 'game-store'].forEach(id => $(id).addEventListener('keydown', e => {
  if (e.code === 'Escape') { e.stopPropagation(); closeOverlays(); if (scene === 'game' && G && G.phase === 'over') exitGame(); else stage.focus(); }
}));
window.addEventListener('blur', () => { keys.clear(); mouse.down = false; });
const hint = $('game-hint');
stage.addEventListener('focus', () => { hint.hidden = true; });
stage.addEventListener('blur', () => { setTimeout(() => { hint.hidden = stage.contains(document.activeElement); }, 0); });
hint.hidden = false;

/* ================= SOUND ================= */
let AC = null, muted = (() => { try { return localStorage.getItem('rebootTownMute') === '1'; } catch (e) { return false; } })();
function unlockAudio() { if (!AC && !muted) { try { AC = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { AC = null; } } if (AC && AC.state === 'suspended') AC.resume(); }
function tone(f, d, type = 'square', vol = .04, at = 0, slide = 0) {
  if (!AC || muted) return; const t0 = AC.currentTime + at, os = AC.createOscillator(), gn = AC.createGain();
  os.type = type; os.frequency.setValueAtTime(f, t0); if (slide) os.frequency.exponentialRampToValueAtTime(slide, t0 + d);
  gn.gain.setValueAtTime(vol, t0); gn.gain.exponentialRampToValueAtTime(.0005, t0 + d); os.connect(gn).connect(AC.destination); os.start(t0); os.stop(t0 + d + .02);
}
function sfx(n) {
  switch (n) {
    case 'hop': tone(420, .12, 'square', .035, 0, 760); break;
    case 'coin': tone(988, .07); tone(1319, .12, 'square', .035, .06); break;
    case 'pop': tone(660, .06, 'triangle', .07, 0, 1200); break;
    case 'wrong': tone(180, .18, 'sawtooth', .04); break;
    case 'hit': tone(220, .25, 'sawtooth', .05, 0, 70); break;
    case 'chime': tone(784, .1, 'triangle', .05); tone(1047, .16, 'triangle', .05, .08); break;
    case 'start': [523, 659, 784].forEach((f, i) => tone(f, .1, 'square', .035, i * .08)); break;
    case 'win': [523, 659, 784, 1047].forEach((f, i) => tone(f, .14, 'square', .04, i * .09)); break;
    case 'over': [392, 330, 262].forEach((f, i) => tone(f, .16, 'triangle', .05, i * .12)); break;
    case 'burn': tone(90 + Math.random() * 40, .06, 'sawtooth', .012); break;
  }
}
const soundBtn = $('game-sound');
function syncSound() { soundBtn.setAttribute('aria-pressed', String(!muted)); soundBtn.textContent = muted ? '♪ Sound off' : '♪ Sound on'; }
soundBtn.addEventListener('click', () => { muted = !muted; try { localStorage.setItem('rebootTownMute', muted ? '1' : '0'); } catch (e) {} syncSound(); if (!muted) unlockAudio(); });
syncSound();

/* ================= RESET COUNTDOWN ================= */
function tickReset() {
  const el = document.querySelector('[data-game-reset]'); if (!el) return;
  const ms = Date.parse(el.dataset.resetAt) - Date.now();
  if (ms <= 0) { el.textContent = 'now'; api('/game/api/status').then(applyStatus).catch(() => {}); return; }
  const h = Math.floor(ms / 3600000), m = Math.floor(ms % 3600000 / 60000);
  el.textContent = `${h}h ${String(m).padStart(2, '0')}m (midnight UTC)`;
}
tickReset(); setInterval(tickReset, 30000);

/* ================= LOOP ================= */
let last = performance.now();
function frame(now) {
  let dt = Math.min(.05, (now - last) / 1000); last = now;
  if (document.hidden) dt = 0;
  t += dt;
  C.imageSmoothingEnabled = false;
  C.clearRect(0, 0, W, H);
  if (scene === 'town') { if (!overlayOpen()) updateTown(dt); drawTown(dt); }
  else if (G) {
    if (G.phase === 'play' && !overlayOpen()) G.update(dt);
    if (G) { G.draw(dt); fx(dt); if (G.phase === 'ready') readyCard(); if (banner.t > 0 && G.id === 'sunrise-flight') { banner.t -= dt; C.globalAlpha = clamp(banner.t, 0, 1); panel(W / 2 - 100, 70, 200, 36, '#151515'); txt(banner.text, W / 2, 82, { size: 16, color: '#ffd25a' }); txt(banner.sub, W / 2, 97, { size: 8, color: CREAM }); C.globalAlpha = 1; } }
  }
  requestAnimationFrame(frame);
}
camX = clamp(player.x - W / 2, 0, WORLD - W);
(document.fonts && document.fonts.load ? document.fonts.load('8px "Silkscreen"').catch(() => {}) : Promise.resolve()).finally(() => requestAnimationFrame(frame));
})();
