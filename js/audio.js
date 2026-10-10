// WebAudio 合成音效：引擎(双振荡器+齿轮换挡) / 风 / 轮胎啸叫 / 碰撞
export class AudioSys {
  constructor() {
    this.ctx = null;
    this.enabled = true;
    this.started = false;
  }
  ensure() {
    if (this.started) { this.ctx.resume && this.ctx.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    this.ctx = new AC();
    const c = this.ctx;
    this.master = c.createGain();
    this.master.gain.value = 0.9;
    this.master.connect(c.destination);

    // —— 引擎 ——
    this.engGain = c.createGain(); this.engGain.gain.value = 0;
    this.engFilter = c.createBiquadFilter();
    this.engFilter.type = 'lowpass'; this.engFilter.frequency.value = 950; this.engFilter.Q.value = 1.2;
    this.osc1 = c.createOscillator(); this.osc1.type = 'sawtooth';
    this.osc2 = c.createOscillator(); this.osc2.type = 'square';
    this.osc2G = c.createGain(); this.osc2G.gain.value = 0.45;
    this.osc1.connect(this.engFilter);
    this.osc2.connect(this.osc2G); this.osc2G.connect(this.engFilter);
    this.engFilter.connect(this.engGain); this.engGain.connect(this.master);
    this.osc1.start(); this.osc2.start();

    // —— 噪声源（风/胎叫共用 buffer）——
    const len = c.sampleRate * 1.2;
    const buf = c.createBuffer(1, len, c.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    this.noiseBuf = buf;

    this.wind = c.createBufferSource(); this.wind.buffer = buf; this.wind.loop = true;
    this.windF = c.createBiquadFilter(); this.windF.type = 'bandpass'; this.windF.frequency.value = 480; this.windF.Q.value = 0.6;
    this.windG = c.createGain(); this.windG.gain.value = 0;
    this.wind.connect(this.windF); this.windF.connect(this.windG); this.windG.connect(this.master);
    this.wind.start();

    this.skid = c.createBufferSource(); this.skid.buffer = buf; this.skid.loop = true;
    this.skidF = c.createBiquadFilter(); this.skidF.type = 'bandpass'; this.skidF.frequency.value = 950; this.skidF.Q.value = 2.2;
    this.skidG = c.createGain(); this.skidG.gain.value = 0;
    this.skid.connect(this.skidF); this.skidF.connect(this.skidG); this.skidG.connect(this.master);
    this.skid.start();

    this.started = true;
  }
  toggle() {
    this.enabled = !this.enabled;
    if (this.enabled) this.ensure();
    if (this.master) this.master.gain.value = this.enabled ? 0.9 : 0;
    return this.enabled;
  }
  // rpm: 0..1（换挡内分数） throttle: 0..1 speed: m/s drift: 0..1
  update(rpm, throttle, speed, drift, dt) {
    if (!this.started || !this.enabled) return;
    const c = this.ctx, t = c.currentTime;
    const f = 62 + rpm * 168 + throttle * 14;
    this.osc1.frequency.setTargetAtTime(f, t, 0.03);
    this.osc2.frequency.setTargetAtTime(f * 0.5, t, 0.03);
    this.engFilter.frequency.setTargetAtTime(500 + rpm * 1800 + throttle * 600, t, 0.05);
    const target = 0.05 + throttle * 0.085 + rpm * 0.03 + Math.min(1, speed / 80) * 0.015;
    this.engGain.gain.setTargetAtTime(this.enabled ? target : 0, t, 0.08);
    this.windG.gain.setTargetAtTime(Math.min(0.16, (speed / 82) ** 2 * 0.2), t, 0.15);
    this.skidG.gain.setTargetAtTime(drift * 0.14, t, 0.05);
  }
  impact(strength) {
    if (!this.started || !this.enabled) return;
    const c = this.ctx, t = c.currentTime;
    const s = Math.min(1, strength / 14);
    const src = c.createBufferSource(); src.buffer = this.noiseBuf;
    const f = c.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = 500 + s * 900;
    const g = c.createGain();
    g.gain.setValueAtTime(0.5 * s, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.28);
    src.connect(f); f.connect(g); g.connect(this.master);
    src.start(t); src.stop(t + 0.3);
    const o = c.createOscillator(); o.type = 'sine'; o.frequency.value = 58;
    const og = c.createGain();
    og.gain.setValueAtTime(0.4 * s, t);
    og.gain.exponentialRampToValueAtTime(0.001, t + 0.22);
    o.connect(og); og.connect(this.master);
    o.start(t); o.stop(t + 0.24);
  }
}
