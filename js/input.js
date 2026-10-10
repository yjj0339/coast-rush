// 键盘 + 触屏输入
export class Input {
  constructor() {
    this.keys = {};
    this.touch = { gas: 0, brake: 0, left: 0, right: 0, hand: 0 };
    this.anyKeyAt = 0;
    addEventListener('keydown', e => {
      if (e.repeat) return;
      this.keys[e.code] = true;
      this.anyKeyAt = performance.now();
      if (['Space', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.code)) e.preventDefault();
      this.onKey && this.onKey(e.code);
    });
    addEventListener('keyup', e => { this.keys[e.code] = false; });
    addEventListener('blur', () => { this.keys = {}; });
    this.bindTouch('tGas', 'gas');
    this.bindTouch('tBrake', 'brake');
    this.bindTouch('tLeft', 'left');
    this.bindTouch('tRight', 'right');
    this.bindTouch('tHandbrake', 'hand');
  }
  bindTouch(id, prop) {
    const el = document.getElementById(id);
    if (!el) return;
    const on = e => { e.preventDefault(); this.touch[prop] = 1; el.classList.add('press'); this.anyKeyAt = performance.now(); };
    const off = e => { e.preventDefault(); this.touch[prop] = 0; el.classList.remove('press'); };
    el.addEventListener('pointerdown', on);
    el.addEventListener('pointerup', off);
    el.addEventListener('pointercancel', off);
    el.addEventListener('pointerleave', off);
  }
  get throttle() {
    let t = 0;
    if (this.keys.KeyW || this.keys.ArrowUp) t += 1;
    if (this.touch.gas) t += 1;
    return Math.min(1, t);
  }
  get brake() {
    let b = 0;
    if (this.keys.KeyS || this.keys.ArrowDown) b += 1;
    if (this.touch.brake) b += 1;
    return Math.min(1, b);
  }
  get steer() {
    let s = 0;
    if (this.keys.KeyA || this.keys.ArrowLeft) s -= 1;
    if (this.keys.KeyD || this.keys.ArrowRight) s += 1;
    if (this.touch.left) s -= 1;
    if (this.touch.right) s += 1;
    return s;
  }
  get handbrake() {
    return (this.keys.Space || this.touch.hand) ? 1 : 0;
  }
}
