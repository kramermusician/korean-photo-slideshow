// LoopGrid Web: the browser port of LoopGrid (the native macOS video looper).
// Space records a camera-and-audio take, space again closes it into a loop
// that plays at once, in phase with every other loop. Loops fill an adaptive
// grid. The audio clock lives in worklet.js; this file owns the transport
// state machine, the camera frames, the grid and the keys.

const MAX_LOOPS = 9;
const MEMORY_CAP = 1.5e9;          // bytes of stored video frames
const TAKE_CAP_SEC = 120;
const PREROLL_SEC = 3;
const FRAME_MARGIN_SEC = 0.25;     // frames kept around a loop so the offset can be nudged live
const REFLOW_MS = 250;

const $ = (s) => document.querySelector(s);

const app = {
  ctx: null, node: null, sr: 48000, t0: null,
  master: null, recDest: null, micSource: null,
  stream: null, video: null, off: null, offCtx: null,
  storeW: 480, storeH: 270,
  preroll: [], keepFrom: null,
  loops: [], nextId: 1, selectedId: null,
  state: 'idle', recStart: 0, closeAt: 0, closeLen: 0, countInEnd: 0,
  masterLength: null, masterStart: 0,
  bpm: null, beatOrigin: 0, taps: [],
  quantize: false, sync: true, click: false, countIn: false, instant: false,
  monitor: false, liveReverb: false, mirror: true,
  cameraOffsetMs: 80,
  memoryBytes: 0, inputRms: 0,
  recorder: null, recChunks: [],
  rects: new Map(),
  showBar: true,
  flashTimer: null,
};

// ---------- clock ----------

function now() {
  if (app.t0 == null) return null;
  return Math.round((app.ctx.currentTime - app.t0) * app.sr);
}
function outLatencySamples() {
  const l = app.ctx.outputLatency || app.ctx.baseLatency || 0;
  return Math.round(l * app.sr);
}
function pmod(a, b) { const r = a % b; return r < 0 ? r + b : r; }
function beatLen() { return app.bpm ? (60 / app.bpm) * app.sr : null; }
function barLen() { return app.bpm ? (60 / app.bpm) * app.sr * 4 : null; }
function offsetSamples() { return Math.round(app.cameraOffsetMs / 1000 * app.sr); }

// ---------- messages ----------

function flash(msg, ms = 2600) {
  const el = $('#flash');
  el.textContent = msg;
  el.classList.add('show');
  clearTimeout(app.flashTimer);
  app.flashTimer = setTimeout(() => el.classList.remove('show'), ms);
}
function post(m) { if (app.node) app.node.port.postMessage(m); }
function pushClick() {
  const on = !!app.bpm && (app.click || app.state === 'countIn');
  post({ type: 'click', on, beatLen: beatLen() || 0, barBeats: 4, origin: app.beatOrigin });
}

// ---------- start ----------

async function start() {
  const btn = $('#start');
  btn.disabled = true;
  btn.textContent = 'Asking for the camera and microphone…';
  try {
    app.ctx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'interactive' });
    app.sr = app.ctx.sampleRate;
    await app.ctx.audioWorklet.addModule('worklet.js');
    app.node = new AudioWorkletNode(app.ctx, 'looper', {
      numberOfInputs: 1, numberOfOutputs: 3, outputChannelCount: [2, 1, 1],
    });
    app.node.port.onmessage = (e) => {
      const m = e.data;
      if (m.type === 'start') { app.t0 = m.t0; }
      else if (m.type === 'meter') { app.inputRms = m.rms; }
    };
    app.master = app.ctx.createGain();
    app.recDest = app.ctx.createMediaStreamDestination();
    const conv = app.ctx.createConvolver();
    conv.buffer = makeImpulse(app.ctx, 2.4);
    const wet = app.ctx.createGain(); wet.gain.value = 0.35;
    app.node.connect(app.master, 0);
    app.node.connect(conv, 1); conv.connect(wet); wet.connect(app.master);
    app.node.connect(app.ctx.destination, 2);
    app.master.connect(app.ctx.destination);
    app.master.connect(app.recDest);

    await startMedia();
    if (app.ctx.state !== 'running') await app.ctx.resume();

    $('#gate').classList.add('hidden');
    $('#app').classList.remove('hidden');
    await fillDevicePickers();
    loadSettings();
    requestAnimationFrame(draw);
    flash('Space to record. Headphones recommended, so the speakers do not feed back.', 5000);
  } catch (err) {
    console.error(err);
    btn.disabled = false;
    btn.textContent = 'Start';
    $('#gate-error').textContent = explain(err);
  }
}

function explain(err) {
  const n = err && err.name;
  if (n === 'NotAllowedError') return 'Camera or microphone access was refused. Allow both in the address bar and press Start again.';
  if (n === 'NotFoundError') return 'No camera or microphone was found.';
  if (n === 'NotReadableError') return 'The camera is in use by another app. Close it and try again.';
  return 'Could not start: ' + (err && err.message ? err.message : err);
}

function makeImpulse(ctx, seconds) {
  const n = Math.floor(ctx.sampleRate * seconds);
  const buf = ctx.createBuffer(2, n, ctx.sampleRate);
  for (let c = 0; c < 2; c++) {
    const d = buf.getChannelData(c);
    for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 2.6);
  }
  return buf;
}

async function startMedia(camId, micId) {
  const constraints = {
    audio: {
      echoCancellation: false, noiseSuppression: false, autoGainControl: false,
      ...(micId ? { deviceId: { exact: micId } } : {}),
    },
    video: {
      width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 },
      ...(camId ? { deviceId: { exact: camId } } : {}),
    },
  };
  const stream = await navigator.mediaDevices.getUserMedia(constraints);
  if (app.stream) app.stream.getTracks().forEach((t) => t.stop());
  if (app.micSource) app.micSource.disconnect();
  app.stream = stream;
  app.micSource = app.ctx.createMediaStreamSource(new MediaStream(stream.getAudioTracks()));
  app.micSource.connect(app.node);

  const video = app.video || document.createElement('video');
  video.muted = true; video.playsInline = true; video.autoplay = true;
  video.srcObject = new MediaStream(stream.getVideoTracks());
  await video.play();
  if (!app.video) {
    app.video = video;
    setupStore();
    scheduleFrame();
  }
}

function setupStore() {
  if (typeof OffscreenCanvas !== 'undefined') {
    app.off = new OffscreenCanvas(app.storeW, app.storeH);
  } else {
    app.off = document.createElement('canvas');
    app.off.width = app.storeW; app.off.height = app.storeH;
  }
  app.offCtx = app.off.getContext('2d', { alpha: false });
}

// ---------- camera frames ----------

function scheduleFrame() {
  const v = app.video;
  if ('requestVideoFrameCallback' in v) {
    v.requestVideoFrameCallback(() => { captureFrame(); scheduleFrame(); });
  } else {
    requestAnimationFrame(() => { captureFrame(); scheduleFrame(); });
  }
}

let framePending = false;
function captureFrame() {
  const p = now();
  if (p == null || app.video.readyState < 2 || framePending) return;
  const vw = app.video.videoWidth, vh = app.video.videoHeight;
  if (!vw || !vh) return;
  // Cover-crop the camera into a 16:9 store frame.
  const sa = vw / vh, ta = app.storeW / app.storeH;
  let sx = 0, sy = 0, sw = vw, sh = vh;
  if (sa > ta) { sw = vh * ta; sx = (vw - sw) / 2; } else { sh = vw / ta; sy = (vh - sh) / 2; }
  app.offCtx.drawImage(app.video, sx, sy, sw, sh, 0, 0, app.storeW, app.storeH);
  if (app.off.transferToImageBitmap) {
    const bmp = app.off.transferToImageBitmap();
    app.preroll.push({ pos: p, bmp, owners: 0 });
    prunePreroll(p);
  } else {
    framePending = true;
    createImageBitmap(app.off).then((bmp) => {
      framePending = false;
      app.preroll.push({ pos: p, bmp, owners: 0 });
      prunePreroll(now() ?? p);
    }, () => { framePending = false; });
  }
}

function prunePreroll(p) {
  const floor = p - PREROLL_SEC * app.sr;
  const keep = app.keepFrom;
  const next = [];
  for (const e of app.preroll) {
    if (e.owners > 0) continue;            // a loop holds it; it leaves the pre-roll
    if (e.pos >= floor || (keep != null && e.pos >= keep)) next.push(e);
    else e.bmp.close();
  }
  app.preroll = next;
}

function fillFrames(loop) {
  const from = loop.start - FRAME_MARGIN_SEC * app.sr;
  const to = loop.start + loop.length + FRAME_MARGIN_SEC * app.sr;
  const have = new Set(loop.frames);
  for (const e of app.preroll) {
    if (e.pos >= from && e.pos < to && !have.has(e)) { e.owners++; loop.frames.push(e); }
  }
  loop.frames.sort((a, b) => a.pos - b.pos);
}

function releaseFrames(loop) {
  for (const e of loop.frames) {
    e.owners--;
    if (e.owners <= 0) e.bmp.close();
  }
  loop.frames = [];
}

function frameFor(loop, playPos) {
  const fr = loop.frames;
  if (!fr.length) return null;
  let q = pmod(playPos - loop.start, loop.length);
  if (loop.reverse) q = loop.length - 1 - q;
  const target = loop.start + q + offsetSamples();
  let lo = 0, hi = fr.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (fr[mid].pos < target) lo = mid + 1; else hi = mid;
  }
  if (lo > 0 && Math.abs(fr[lo - 1].pos - target) < Math.abs(fr[lo].pos - target)) lo--;
  return fr[lo].bmp;
}

function updateMemory() {
  let frames = 0;
  for (const l of app.loops) frames += l.frames.length;
  app.memoryBytes = frames * app.storeW * app.storeH * 4;
}

// ---------- transport ----------

function space() {
  const p = now();
  if (p == null) return flash('Audio is not running yet');
  switch (app.state) {
    case 'idle': case 'armed': beginTake(p); break;
    case 'recording': closeTake(p); break;
    case 'countIn': cancelCountIn(); break;
    default: break;
  }
}

// `pinned` fixes the take's start (instant loop mode starts the next take
// exactly where the last loop closed); otherwise it is now, snapped.
function beginTake(p, pinned) {
  if (app.loops.length >= MAX_LOOPS) return flash('All 9 tiles are full. Shift+number clears one.');
  if (app.memoryBytes >= MEMORY_CAP) return flash('Loop memory is at the cap. Clear a tile first.');
  const bar = barLen();
  if (app.countIn && app.loops.length === 0 && bar) {
    app.beatOrigin = p;
    app.countInEnd = p + Math.round(bar);
    app.recStart = app.countInEnd;
    app.keepFrom = app.recStart - Math.round(0.2 * app.sr);
    app.state = 'countIn';
    pushClick();
    return;
  }
  if (app.countIn && app.loops.length === 0) flash('No tempo, so no count-in: tap T first');
  app.recStart = pinned != null ? pinned : snapToGrid(p);
  app.keepFrom = Math.min(app.recStart, p) - Math.round(0.2 * app.sr);
  app.state = 'recording';
}

function cancelCountIn() {
  app.state = 'idle';
  app.keepFrom = null;
  pushClick();
  flash('Count-in cancelled');
}

function closeTake(p) {
  const start = app.recStart;
  const raw = snapToGrid(p) - start;
  if (raw <= 0.1 * app.sr) return discardTake();
  const len = snapLength(raw);
  if (app.masterLength == null) {
    app.masterLength = len;
    app.masterStart = start;
    app.beatOrigin = start;
    pushClick();
  }
  app.closeLen = len;
  app.closeAt = start + len;
  if (app.closeAt > p) app.state = 'closing';
  else finalize(p);
}

function finalize(activeFrom) {
  const loop = {
    id: app.nextId++, start: app.recStart, length: app.closeLen,
    activeFrom: Math.max(activeFrom, app.recStart + app.closeLen),
    frames: [], muted: false, volume: 1, reverse: false, reverbOn: app.liveReverb, ready: false,
  };
  post({ type: 'close', id: loop.id, start: loop.start, length: loop.length, activeFrom: loop.activeFrom, reverbOn: loop.reverbOn });
  fillFrames(loop);
  app.loops.push(loop);
  app.selectedId = loop.id;
  app.state = 'armed';
  relayout();
  if (app.instant) beginTake(activeFrom, loop.start + loop.length);
  const wait = Math.max(0.35, app.cameraOffsetMs / 1000 + 0.25);
  setTimeout(() => {
    if (!app.loops.includes(loop)) { if (app.state !== 'recording' && app.state !== 'closing') app.keepFrom = null; return; }
    fillFrames(loop);
    loop.ready = true;
    if (app.state !== 'recording' && app.state !== 'closing') app.keepFrom = null;
    prunePreroll(now() ?? 0);
    updateMemory();
  }, wait * 1000);
  updateMemory();
}

function discardTake() {
  app.state = app.loops.length ? 'armed' : 'idle';
  app.keepFrom = null;
  flash('Take discarded');
}

function removeLoop(loop) {
  const i = app.loops.indexOf(loop);
  if (i < 0) return;
  app.loops.splice(i, 1);
  post({ type: 'remove', id: loop.id });
  releaseFrames(loop);
  if (app.selectedId === loop.id) app.selectedId = app.loops.length ? app.loops[app.loops.length - 1].id : null;
  if (app.loops.length === 0) {
    app.masterLength = null;
    if (app.state === 'armed') app.state = 'idle';
  }
  updateMemory();
  relayout();
}

function clearAll() {
  if (app.state === 'recording' || app.state === 'closing') discardTake();
  for (const l of app.loops.slice()) removeLoop(l);
  post({ type: 'clear' });
  app.state = 'idle';
  flash('Cleared');
}

function tick(p) {
  if (app.state === 'countIn' && p >= app.countInEnd) {
    app.state = 'recording';
    pushClick();
  }
  if (app.state === 'closing' && p >= app.closeAt) finalize(p);
  if (app.state === 'recording' && p - app.recStart > TAKE_CAP_SEC * app.sr) { flash('Take capped at 2 minutes'); closeTake(p); }
}

// ---------- snapping (mirrors AppModel.swift) ----------

function snapToGrid(p) {
  if (!app.quantize) return p;
  let unit, origin;
  const beat = beatLen();
  if (beat) { unit = beat; origin = app.beatOrigin; }
  else if (app.masterLength) { unit = app.masterLength / 4; origin = app.masterStart; }
  else return p;
  const k = Math.round((p - origin) / unit);
  return origin + Math.round(k * unit);
}

function snapLength(raw) {
  const L = app.masterLength, bar = barLen();
  if (L) {
    if (app.sync) {
      const maxMult = Math.max(1, Math.floor((125 * app.sr) / L));
      const n = Math.round(raw / L);
      let mults = [0.25, 0.5, 1];
      if (n > 1) mults.push(n, n - 1);
      if (n > maxMult) { mults = mults.filter((m) => m <= maxMult).concat([maxMult]); flash('Take trimmed to the longest that fits (' + maxMult + ' loops)'); }
      if (bar) mults = mults.filter((m) => { const bars = (L * m) / bar; return Math.abs(bars - Math.round(bars)) < 0.01 && bars >= 1; });
      if (!mults.length) mults = [1];
      const cands = mults.map((m) => Math.round(L * m));
      return cands.reduce((a, b) => (Math.abs(a - raw) <= Math.abs(b - raw) ? a : b));
    }
    if (bar) return Math.round(Math.max(1, Math.round(raw / bar)) * bar);
    if (app.quantize) { const q = L / 4; return Math.round(Math.max(1, Math.round(raw / q)) * q); }
    return raw;
  }
  if (bar) return Math.round(Math.max(1, Math.round(raw / bar)) * bar);
  return raw;
}

// ---------- tempo ----------

function tapTempo() {
  if (app.loops.length || app.state !== 'idle') return flash('Tap tempo works before the first loop');
  const p = now(); if (p == null) return;
  if (app.taps.length && p - app.taps[app.taps.length - 1] > 2 * app.sr) app.taps = [];
  app.taps.push(p);
  if (app.taps.length > 5) app.taps.shift();
  if (app.taps.length < 2) return flash('Tap…');
  const avg = (app.taps[app.taps.length - 1] - app.taps[0]) / (app.taps.length - 1);
  app.bpm = Math.round((60 * app.sr / avg) * 10) / 10;
  app.beatOrigin = p;
  pushClick();
  flash(app.bpm.toFixed(1) + ' BPM');
}

function freeMode() {
  if (app.loops.length) return flash('Free mode needs an empty grid');
  app.bpm = null; app.taps = [];
  pushClick();
  flash('Free mode: the first loop sets the length');
}

function beatsAt(p, wall) {
  const beat = beatLen();
  if (p != null && beat) return (p - app.beatOrigin) / beat;
  if (p != null && app.masterLength) return (p - app.masterStart) / (app.masterLength / 4);
  return wall * 0.0005;
}
function nextGridPos(p) {
  const beat = beatLen();
  const unit = beat || (app.masterLength ? app.masterLength / 4 : null);
  if (!unit) return p;
  const origin = beat ? app.beatOrigin : app.masterStart;
  const k = Math.ceil((p - origin) / unit);
  return origin + Math.round(k * unit);
}

// ---------- loop controls ----------

function selected() { return app.loops.find((l) => l.id === app.selectedId) || null; }
function toggleMute(i) {
  const l = app.loops[i]; if (!l) return;
  l.muted = !l.muted;
  post({ type: 'mute', id: l.id, on: l.muted, fade: 0.008 });
}
function selectNext() {
  if (!app.loops.length) return;
  const i = app.loops.findIndex((l) => l.id === app.selectedId);
  app.selectedId = app.loops[(i + 1) % app.loops.length].id;
}
function volume(delta) {
  const l = selected(); if (!l) return flash('No loop selected');
  l.volume = Math.max(0, Math.min(1.5, Math.round((l.volume + delta) * 10) / 10));
  post({ type: 'volume', id: l.id, value: l.volume });
  flash('Loop ' + (app.loops.indexOf(l) + 1) + ' volume ' + Math.round(l.volume * 100) + '%');
}
function toggleReverse() {
  const l = selected(); if (!l) return flash('No loop selected');
  const p = now(); const at = nextGridPos(p);
  l.reverse = !l.reverse;
  post({ type: 'reverse', id: l.id, on: l.reverse, at });
  setTimeout(() => {}, 0);
  flash('Loop ' + (app.loops.indexOf(l) + 1) + (l.reverse ? ' reversed on the next beat' : ' forward on the next beat'));
}
function toggleReverb() {
  const l = selected(); if (!l) return flash('No loop selected');
  l.reverbOn = !l.reverbOn;
  post({ type: 'reverb', id: l.id, on: l.reverbOn });
  flash('Loop ' + (app.loops.indexOf(l) + 1) + ' reverb ' + (l.reverbOn ? 'on' : 'off'));
}
function nudgeOffset(ms) {
  app.cameraOffsetMs = Math.max(-250, Math.min(250, app.cameraOffsetMs + ms));
  $('#set-offset').value = app.cameraOffsetMs;
  $('#set-offset-val').textContent = app.cameraOffsetMs + ' ms';
  saveSettings();
  flash('Camera offset ' + app.cameraOffsetMs + ' ms');
}

// ---------- performance recording ----------

function toggleRecord() {
  if (app.recorder) { app.recorder.stop(); return; }
  if (typeof MediaRecorder === 'undefined') return flash('This browser cannot record video');
  const canvas = $('#grid');
  const vs = canvas.captureStream(30);
  const stream = new MediaStream([...vs.getVideoTracks(), ...app.recDest.stream.getAudioTracks()]);
  const mime = ['video/mp4;codecs=avc1,mp4a.40.2', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4']
    .find((m) => MediaRecorder.isTypeSupported(m));
  const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 8e6, audioBitsPerSecond: 192e3 });
  app.recChunks = [];
  rec.ondataavailable = (e) => { if (e.data.size) app.recChunks.push(e.data); };
  rec.onstop = () => {
    const ext = (rec.mimeType || mime || '').includes('mp4') ? 'mp4' : 'webm';
    const blob = new Blob(app.recChunks, { type: rec.mimeType || mime });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'loopgrid-web-' + new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19) + '.' + ext;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    app.recorder = null;
    flash('Performance saved to your downloads (' + ext + ')');
  };
  rec.start(1000);
  app.recorder = rec;
  flash('Recording the performance. R again to stop and save.');
}

// ---------- layout ----------

function gridShape(n) {
  if (n <= 1) return [1, 1];
  if (n === 2) return [2, 1];
  if (n <= 4) return [2, 2];
  if (n <= 6) return [3, 2];
  return [3, 3];
}

function tileKeys() {
  const keys = app.loops.map((l) => 'loop' + l.id);
  if (app.loops.length < MAX_LOOPS) keys.push('live');
  return keys;
}

function targets(W, H) {
  const keys = tileKeys();
  const n = keys.length;
  const [cols, rows] = gridShape(n);
  const gap = Math.max(4, Math.round(Math.min(W, H) * 0.008));
  const tw = Math.min((W - gap * (cols + 1)) / cols, ((H - gap * (rows + 1)) / rows) * 16 / 9);
  const th = tw * 9 / 16;
  const gw = cols * tw + (cols - 1) * gap, gh = rows * th + (rows - 1) * gap;
  const x0 = (W - gw) / 2, y0 = (H - gh) / 2;
  const out = new Map();
  keys.forEach((k, i) => {
    const row = Math.floor(i / cols);
    const inRow = Math.min(cols, n - row * cols);
    const rowW = inRow * tw + (inRow - 1) * gap;
    const col = i - row * cols;
    const x = (W - rowW) / 2 + col * (tw + gap);
    const y = y0 + row * (th + gap);
    out.set(k, { x, y, w: tw, h: th });
  });
  void x0;
  return out;
}

let lastW = 0, lastH = 0;
function relayout() { lastW = 0; }   // forces a retarget on the next frame

function rectFor(key, target, t) {
  let r = app.rects.get(key);
  if (!r) { r = { from: target, to: target, t0: t - REFLOW_MS }; app.rects.set(key, r); }
  if (r.to.x !== target.x || r.to.y !== target.y || r.to.w !== target.w || r.to.h !== target.h) {
    r.from = currentRect(r, t); r.to = target; r.t0 = t;
  }
  return currentRect(r, t);
}
function currentRect(r, t) {
  let u = Math.min(1, (t - r.t0) / REFLOW_MS);
  u = u < 0.5 ? 2 * u * u : -1 + (4 - 2 * u) * u;
  return {
    x: r.from.x + (r.to.x - r.from.x) * u, y: r.from.y + (r.to.y - r.from.y) * u,
    w: r.from.w + (r.to.w - r.from.w) * u, h: r.from.h + (r.to.h - r.from.h) * u,
  };
}

// ---------- drawing ----------

function drawCover(g, img, iw, ih, r, mirror) {
  const sa = iw / ih, ta = r.w / r.h;
  let sx = 0, sy = 0, sw = iw, sh = ih;
  if (sa > ta) { sw = ih * ta; sx = (iw - sw) / 2; } else { sh = iw / ta; sy = (ih - sh) / 2; }
  g.save();
  if (mirror) { g.translate(r.x + r.w, r.y); g.scale(-1, 1); g.drawImage(img, sx, sy, sw, sh, 0, 0, r.w, r.h); }
  else g.drawImage(img, sx, sy, sw, sh, r.x, r.y, r.w, r.h);
  g.restore();
}

function draw(t) {
  requestAnimationFrame(draw);
  const p = now();
  if (p != null) tick(p);
  const canvas = $('#grid');
  const cw = canvas.clientWidth, ch = canvas.clientHeight;
  const dpr = Math.min(window.devicePixelRatio || 1, 1920 / Math.max(1, cw));
  const W = Math.round(cw * dpr), H = Math.round(ch * dpr);
  if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; lastW = 0; }
  const g = canvas.getContext('2d');
  g.fillStyle = '#0c0e12';
  g.fillRect(0, 0, W, H);
  if (p == null) return;

  if (lastW !== W || lastH !== H) { app.targets = targets(W, H); lastW = W; lastH = H; }
  const keys = tileKeys();
  for (const k of app.rects.keys()) if (!keys.includes(k)) app.rects.delete(k);

  const playPos = p - outLatencySamples();
  const beatsNow = beatsAt(p, t);
  const beatPhase = beatsNow - Math.floor(beatsNow);
  const scale = dpr;

  for (const key of keys) {
    const r = rectFor(key, app.targets.get(key), t);
    g.save();
    g.beginPath();
    roundRect(g, r.x, r.y, r.w, r.h, 10 * scale);
    g.clip();
    if (key === 'live') {
      const v = app.video;
      if (v && v.videoWidth) drawCover(g, v, v.videoWidth, v.videoHeight, r, app.mirror);
      if (app.state === 'countIn') {
        g.fillStyle = 'rgba(255,170,60,' + (0.35 * (1 - beatPhase)) + ')';
        g.fillRect(r.x, r.y, r.w, r.h);
      }
    } else {
      const loop = app.loops.find((l) => 'loop' + l.id === key);
      const bmp = loop ? frameFor(loop, playPos) : null;
      let alpha = loop.muted ? 0.3 : 1;
      alpha *= 0.4 + 0.6 * Math.min(1, loop.volume);
      g.globalAlpha = alpha;
      if (bmp) drawCover(g, bmp, app.storeW, app.storeH, r, app.mirror);
      else { g.fillStyle = '#1b1f26'; g.fillRect(r.x, r.y, r.w, r.h); }
      g.globalAlpha = 1;
      drawLabel(g, loop, r, scale);
    }
    g.restore();
    // border
    g.lineWidth = 3 * scale;
    let stroke = 'rgba(255,255,255,0.08)';
    if (key === 'live') {
      if (app.state === 'recording' || app.state === 'closing') stroke = '#e6453f';
      else if (app.state === 'countIn') stroke = '#f0a33a';
      else if (app.state === 'armed') stroke = 'rgba(78,205,196,0.45)';
    } else if ('loop' + app.selectedId === key) { stroke = '#4ecdc4'; }
    g.strokeStyle = stroke;
    g.beginPath(); roundRect(g, r.x + 1.5 * scale, r.y + 1.5 * scale, r.w - 3 * scale, r.h - 3 * scale, 9 * scale); g.stroke();
  }
  updateHud(p, beatsNow);
}

function roundRect(g, x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r);
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath();
}

function drawLabel(g, loop, r, s) {
  const i = app.loops.indexOf(loop) + 1;
  const pad = 10 * s, size = Math.max(14, Math.round(r.h * 0.07));
  g.font = '600 ' + size + 'px system-ui, sans-serif';
  g.textBaseline = 'top';
  const items = [String(i)];
  if (loop.muted) items.push('MUTE');
  if (loop.reverse) items.push('REV');
  if (loop.reverbOn) items.push('VERB');
  if (loop.volume !== 1) items.push(Math.round(loop.volume * 100) + '%');
  let x = r.x + pad;
  for (const txt of items) {
    const w = g.measureText(txt).width + 12 * s;
    g.fillStyle = txt === String(i) ? 'rgba(78,205,196,0.85)' : 'rgba(0,0,0,0.55)';
    g.beginPath(); roundRect(g, x, r.y + pad, w, size + 8 * s, 6 * s); g.fill();
    g.fillStyle = txt === String(i) ? '#0c0e12' : '#fff';
    g.fillText(txt, x + 6 * s, r.y + pad + 4 * s);
    x += w + 6 * s;
  }
  // progress line along the bottom
  const q = pmod((now() - outLatencySamples()) - loop.start, loop.length) / loop.length;
  g.fillStyle = 'rgba(78,205,196,0.7)';
  g.fillRect(r.x, r.y + r.h - 3 * s, r.w * q, 3 * s);
}

// ---------- HUD ----------

const hudCache = {};
function setText(id, txt) { if (hudCache[id] !== txt) { hudCache[id] = txt; $(id).textContent = txt; } }
function setFlag(id, on) { $(id).classList.toggle('on', !!on); }

function updateHud(p, beats) {
  const stateName = { idle: 'Idle', countIn: 'Count-in', recording: 'Recording', closing: 'Closing', armed: 'Armed' }[app.state];
  setText('#hud-state', stateName);
  $('#hud-state').dataset.state = app.state;
  setText('#hud-mode', app.bpm ? app.bpm.toFixed(1) + ' BPM' : (app.masterLength ? 'Free, loop ' + (app.masterLength / app.sr).toFixed(2) + ' s' : 'Free'));
  const beatEl = $('#hud-beat');
  const phase = beats - Math.floor(beats);
  const live = (app.bpm || app.masterLength) && p != null;
  beatEl.style.opacity = live ? String(1 - Math.min(1, phase * 3) * 0.8) : '0.2';
  const bar = live ? (Math.floor(Math.floor(beats) / 4) + 1) + '.' + (pmod(Math.floor(beats), 4) + 1) : '';
  setText('#hud-bar', bar);
  setFlag('#hud-q', app.quantize);
  setFlag('#hud-s', app.sync);
  setFlag('#hud-m', app.click);
  setFlag('#hud-c', app.countIn);
  setFlag('#hud-i', app.instant);
  setFlag('#hud-rec', !!app.recorder);
  setText('#hud-mem', (app.memoryBytes / 1e6).toFixed(0) + ' MB');
  const lvl = Math.min(1, app.inputRms * 4);
  $('#meter-fill').style.width = (lvl * 100).toFixed(0) + '%';
  $('#meter-fill').style.background = lvl > 0.9 ? '#e6453f' : '#4ecdc4';
  setText('#hud-loops', app.loops.length + '/' + MAX_LOOPS);
}

// ---------- keys ----------

function handleKey(code, shift, repeat) {
  if (repeat && (code === 'Space' || code === 'KeyT')) return true;
  const digit = /^Digit([1-9])$/.exec(code);
  if (digit) {
    const i = Number(digit[1]) - 1;
    if (shift) { if (app.loops[i]) removeLoop(app.loops[i]); }
    else toggleMute(i);
    return true;
  }
  switch (code) {
    case 'Space': space(); return true;
    case 'Escape':
      if (app.state === 'recording' || app.state === 'closing') discardTake();
      else if (app.state === 'countIn') cancelCountIn();
      else closeDialogs();
      return true;
    case 'KeyQ': app.quantize = !app.quantize; flash('Quantize ' + (app.quantize ? 'on' : 'off')); return true;
    case 'KeyS': app.sync = !app.sync; flash('Loop sync ' + (app.sync ? 'on' : 'off')); return true;
    case 'KeyT': tapTempo(); return true;
    case 'KeyF': freeMode(); return true;
    case 'KeyM': app.click = !app.click; pushClick(); flash(app.bpm ? 'Click ' + (app.click ? 'on' : 'off') : 'Click needs a tempo: tap T'); return true;
    case 'KeyI': app.instant = !app.instant; flash(app.instant ? 'Instant loop on: space closes a loop and starts the next take at once' : 'Instant loop off: space closes, space again records'); return true;
    case 'KeyC': app.countIn = !app.countIn; flash('Count-in ' + (app.countIn ? 'on' : 'off')); return true;
    case 'KeyR': toggleRecord(); return true;
    case 'BracketLeft': nudgeOffset(-5); return true;
    case 'BracketRight': nudgeOffset(5); return true;
    case 'Delete': case 'Backspace':
      if (shift) clearAll();
      else if (app.state === 'recording' || app.state === 'closing') discardTake();
      else if (app.loops.length) removeLoop(app.loops[app.loops.length - 1]);
      return true;
    case 'KeyH': app.showBar = !app.showBar; $('#bar').classList.toggle('hidden', !app.showBar); return true;
    case 'Tab': selectNext(); return true;
    case 'ArrowUp': volume(0.1); return true;
    case 'ArrowDown': volume(-0.1); return true;
    case 'KeyB': toggleReverse(); return true;
    case 'KeyV': if (shift) { app.liveReverb = !app.liveReverb; post({ type: 'liveReverb', on: app.liveReverb }); flash('Live reverb ' + (app.liveReverb ? 'on: the next take keeps it' : 'off')); } else toggleReverb(); return true;
    case 'Slash': if (shift) toggleDialog('#help'); return true;
    case 'Comma': toggleDialog('#settings'); return true;
    case 'Enter': toggleFullscreen(); return true;
    default: return false;
  }
}

document.addEventListener('keydown', (e) => {
  if (!app.ctx) return;
  const tag = (e.target && e.target.tagName) || '';
  if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (handleKey(e.code, e.shiftKey, e.repeat)) e.preventDefault();
});

// ---------- dialogs, settings, bar ----------

function toggleDialog(sel) {
  const el = $(sel);
  const open = el.classList.contains('open');
  closeDialogs();
  if (!open) el.classList.add('open');
}
function closeDialogs() { document.querySelectorAll('.dialog').forEach((d) => d.classList.remove('open')); }
function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
}

async function fillDevicePickers() {
  const devs = await navigator.mediaDevices.enumerateDevices();
  const cam = $('#set-cam'), mic = $('#set-mic');
  cam.innerHTML = ''; mic.innerHTML = '';
  for (const d of devs) {
    if (d.kind !== 'videoinput' && d.kind !== 'audioinput') continue;
    const o = document.createElement('option');
    o.value = d.deviceId; o.textContent = d.label || d.kind;
    (d.kind === 'videoinput' ? cam : mic).appendChild(o);
  }
  const vt = app.stream.getVideoTracks()[0], at = app.stream.getAudioTracks()[0];
  if (vt) cam.value = vt.getSettings().deviceId || cam.value;
  if (at) mic.value = at.getSettings().deviceId || mic.value;
}

function saveSettings() {
  try {
    localStorage.setItem('loopgrid-web', JSON.stringify({ offset: app.cameraOffsetMs, mirror: app.mirror, store: app.storeW }));
  } catch (_) { /* private window */ }
}
function loadSettings() {
  try {
    const s = JSON.parse(localStorage.getItem('loopgrid-web') || '{}');
    if (typeof s.offset === 'number') app.cameraOffsetMs = s.offset;
    if (typeof s.mirror === 'boolean') app.mirror = s.mirror;
    if (s.store === 640 || s.store === 480 || s.store === 320) { app.storeW = s.store; app.storeH = s.store * 9 / 16; setupStore(); }
  } catch (_) { /* ignore */ }
  $('#set-offset').value = app.cameraOffsetMs;
  $('#set-offset-val').textContent = app.cameraOffsetMs + ' ms';
  $('#set-mirror').checked = app.mirror;
  $('#set-monitor').checked = app.monitor;
  $('#set-store').value = String(app.storeW);
}

function wireUi() {
  $('#start').addEventListener('click', start);
  document.querySelectorAll('#bar button[data-code]').forEach((b) => {
    b.addEventListener('click', () => { handleKey(b.dataset.code, b.dataset.shift === '1', false); b.blur(); });
  });
  document.querySelectorAll('[data-dialog]').forEach((b) => b.addEventListener('click', () => toggleDialog(b.dataset.dialog)));
  document.querySelectorAll('.dialog .close').forEach((b) => b.addEventListener('click', closeDialogs));
  $('#set-offset').addEventListener('input', (e) => { app.cameraOffsetMs = Number(e.target.value); $('#set-offset-val').textContent = app.cameraOffsetMs + ' ms'; saveSettings(); });
  $('#set-mirror').addEventListener('change', (e) => { app.mirror = e.target.checked; saveSettings(); });
  $('#set-monitor').addEventListener('change', (e) => { app.monitor = e.target.checked; post({ type: 'monitor', on: app.monitor }); if (app.monitor) flash('Monitoring on: use headphones or it feeds back'); });
  $('#set-store').addEventListener('change', (e) => {
    if (app.loops.length) { flash('Change the frame size on an empty grid'); e.target.value = String(app.storeW); return; }
    app.storeW = Number(e.target.value); app.storeH = app.storeW * 9 / 16; setupStore(); saveSettings();
  });
  $('#set-cam').addEventListener('change', () => startMedia($('#set-cam').value, $('#set-mic').value).catch((err) => flash(explain(err))));
  $('#set-mic').addEventListener('change', () => startMedia($('#set-cam').value, $('#set-mic').value).catch((err) => flash(explain(err))));
  $('#grid').addEventListener('click', (e) => {
    // Click a loop tile to select it; click its number to mute.
    if (!app.targets) return;
    const canvas = $('#grid');
    const dpr = canvas.width / canvas.clientWidth;
    const x = e.offsetX * dpr, y = e.offsetY * dpr;
    for (const loop of app.loops) {
      const r = app.targets.get('loop' + loop.id);
      if (r && x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h) {
        if (x < r.x + r.h * 0.2 && y < r.y + r.h * 0.2) toggleMute(app.loops.indexOf(loop));
        else app.selectedId = loop.id;
        return;
      }
    }
  });
  const ok = navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.AudioWorkletNode;
  if (!ok) {
    $('#start').disabled = true;
    $('#gate-error').textContent = window.isSecureContext
      ? 'This browser is missing the camera or AudioWorklet API. Use a current Chrome, Edge, Firefox or Safari.'
      : 'This page needs HTTPS (or localhost) to open the camera.';
  }
}

document.addEventListener('DOMContentLoaded', wireUi);
