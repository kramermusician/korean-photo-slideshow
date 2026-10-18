// LoopGrid Web: the audio engine. Runs on the audio thread as an AudioWorklet.
//
// This is the clock. `pos` counts every sample rendered since the processor
// started, and everything else in the app (key presses, camera frames, loop
// starts and lengths) is a position on that one line. Live input is written
// to a 130-second ring at its arrival position, so a loop can be cut out of
// the ring after the fact: when a take closes, the samples already in hand
// are copied at once and the tail is filled as the last blocks come in.
//
// Outputs: 0 = loop mix plus optional live monitoring (stereo),
//          1 = reverb send (mono, the main thread convolves it),
//          2 = click (mono, kept out of performance recordings).

const RING_SEC = 130;
const CLICK_SEC = 0.012;

function rampAt(r, p) {
  if (p >= r.start + r.len) return r.to;
  if (p <= r.start) return r.from;
  return r.from + (r.to - r.from) * ((p - r.start) / r.len);
}
function rampTo(r, target, p, n) {
  return { start: p, len: Math.max(1, n), from: rampAt(r, p), to: target };
}
function flat(v) { return { start: 0, len: 1, from: v, to: v }; }

class LooperProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pos = 0;
    this.started = false;
    this.ringN = Math.floor(sampleRate * RING_SEC);
    this.ring = new Float32Array(this.ringN);
    this.slots = new Map();
    this.monitor = false;
    this.liveReverb = false;
    this.click = { on: false, beatLen: 0, barBeats: 4, origin: 0, gain: 0.5 };
    this.meterAcc = 0;
    this.meterN = 0;
    this.port.onmessage = (e) => this.handle(e.data);
  }

  handle(m) {
    const s = m.id != null ? this.slots.get(m.id) : null;
    switch (m.type) {
      case 'close': {
        const slot = {
          id: m.id, start: m.start, length: m.length, filled: 0,
          samples: new Float32Array(m.length),
          activeFrom: m.activeFrom, reverbOn: !!m.reverbOn,
          reverse: false, reverseAt: null, reverseTo: false,
          vol: flat(1), level: flat(1),
        };
        this.fill(slot);
        this.slots.set(m.id, slot);
        break;
      }
      case 'remove': this.slots.delete(m.id); break;
      case 'clear': this.slots.clear(); break;
      case 'mute':
        if (s) s.level = rampTo(s.level, m.on ? 0 : 1, this.pos, Math.round(sampleRate * (m.fade ?? 0.008)));
        break;
      case 'volume':
        if (s) s.vol = rampTo(s.vol, m.value, this.pos, Math.round(sampleRate * 0.04));
        break;
      case 'reverse':
        if (s) { s.reverseAt = m.at ?? this.pos; s.reverseTo = !!m.on; }
        break;
      case 'reverb': if (s) s.reverbOn = !!m.on; break;
      case 'monitor': this.monitor = !!m.on; break;
      case 'liveReverb': this.liveReverb = !!m.on; break;
      case 'click': Object.assign(this.click, m); delete this.click.type; break;
    }
  }

  // Copy whatever the ring already holds of this loop into its own buffer.
  fill(s) {
    const avail = Math.min(s.length, this.pos - s.start);
    if (avail <= s.filled) return;
    const N = this.ringN, ring = this.ring;
    for (let j = s.filled; j < avail; j++) {
      let k = (s.start + j) % N;
      if (k < 0) k += N;
      s.samples[j] = ring[k];
    }
    s.filled = avail;
  }

  process(inputs, outputs) {
    if (!this.started) {
      this.started = true;
      this.port.postMessage({ type: 'start', t0: currentTime, sampleRate });
    }
    const inp = inputs[0] && inputs[0][0];
    const dryL = outputs[0][0], dryR = outputs[0][1];
    const send = outputs[1][0];
    const clk = outputs[2][0];
    const n = dryL.length;
    const p0 = this.pos;
    const N = this.ringN, ring = this.ring;

    if (inp) {
      let k = p0 % N;
      for (let i = 0; i < n; i++) {
        ring[k] = inp[i];
        if (++k === N) k = 0;
        this.meterAcc += inp[i] * inp[i];
      }
      this.meterN += n;
      if (this.meterN >= 2048) {
        this.port.postMessage({ type: 'meter', rms: Math.sqrt(this.meterAcc / this.meterN) });
        this.meterAcc = 0; this.meterN = 0;
      }
    }
    this.pos = p0 + n;

    for (const s of this.slots.values()) {
      if (s.filled < s.length) this.fill(s);
      if (s.reverseAt != null && p0 >= s.reverseAt) { s.reverse = s.reverseTo; s.reverseAt = null; }
      const L = s.length, start = s.start, buf = s.samples, filled = s.filled;
      const rev = s.reverse, rvb = s.reverbOn;
      const volStatic = s.vol.start + s.vol.len <= p0, lvlStatic = s.level.start + s.level.len <= p0;
      const gStatic = (volStatic ? s.vol.to : 1) * (lvlStatic ? s.level.to : 1);
      if (volStatic && lvlStatic && gStatic === 0) continue;
      for (let i = 0; i < n; i++) {
        const p = p0 + i;
        if (p < s.activeFrom) continue;
        let j = (p - start) % L;
        if (j < 0) j += L;
        if (rev) j = L - 1 - j;
        if (j >= filled) continue;
        const g = (volStatic && lvlStatic) ? gStatic : rampAt(s.vol, p) * rampAt(s.level, p);
        const v = buf[j] * g;
        dryL[i] += v;
        if (rvb) send[i] += v;
      }
    }

    if (inp && this.monitor) {
      for (let i = 0; i < n; i++) dryL[i] += inp[i];
      if (this.liveReverb) for (let i = 0; i < n; i++) send[i] += inp[i];
    }
    for (let i = 0; i < n; i++) dryR[i] = dryL[i];

    const c = this.click;
    if (c.on && c.beatLen > 0) {
      const clickLen = sampleRate * CLICK_SEC;
      for (let i = 0; i < n; i++) {
        const k = p0 + i - c.origin;
        if (k < 0) continue;
        const beat = Math.floor(k / c.beatLen);
        const phase = k - beat * c.beatLen;
        if (phase < clickLen) {
          const f = (beat % c.barBeats === 0) ? 1500 : 1000;
          clk[i] = Math.sin(2 * Math.PI * f * phase / sampleRate) * (1 - phase / clickLen) * c.gain;
        }
      }
    }
    return true;
  }
}

registerProcessor('looper', LooperProcessor);
