// 通用工具：Catmull-Rom 采样、空间哈希、缓动
export function catmull(pts, step = 3.0, closed = false) {
  const P = closed ? pts.concat([pts[0]]) : pts.slice();
  const n = P.length;
  const out = [];
  const pt = i => closed ? P[((i % (n - 1)) + (n - 1)) % (n - 1)] : P[Math.max(0, Math.min(n - 1, i))];
  for (let i = 0; i < n - 1; i++) {
    const p0 = pt(i - 1), p1 = pt(i), p2 = pt(i + 1), p3 = pt(i + 2);
    const seg = Math.hypot(p1[0] - p2[0], p1[1] - p2[1]);
    const k = Math.max(2, Math.round(seg / step));
    for (let j = 0; j < k; j++) {
      const t = j / k, t2 = t * t, t3 = t2 * t;
      const x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3);
      const z = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3);
      out.push([x, z]);
    }
  }
  out.push(closed ? [pts[0][0], pts[0][1]] : [pts[n - 1][0], pts[n - 1][1]]);
  return out;
}

export class SpatialHash {
  constructor(cell = 20) { this.cell = cell; this.map = new Map(); }
  key(x, z) { return Math.floor(x / this.cell) + ',' + Math.floor(z / this.cell); }
  add(x, z, data) {
    const k = this.key(x, z);
    if (!this.map.has(k)) this.map.set(k, []);
    this.map.get(k).push({ x, z, data });
  }
  query(x, z, radius, out) {
    out.length = 0;
    const r = Math.ceil(radius / this.cell);
    const cx = Math.floor(x / this.cell), cz = Math.floor(z / this.cell);
    for (let i = -r; i <= r; i++) for (let j = -r; j <= r; j++) {
      const bucket = this.map.get((cx + i) + ',' + (cz + j));
      if (bucket) for (const p of bucket) out.push(p);
    }
    return out;
  }
}

export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export const lerp = (a, b, t) => a + (b - a) * t;
// 帧率无关阻尼趋近
export const damp = (a, b, k, dt) => lerp(a, b, 1 - Math.exp(-k * dt));

// 点到线段距离²（附带最近点参数）
export function segDist2(px, pz, ax, az, bx, bz) {
  const dx = bx - ax, dz = bz - az;
  const l2 = dx * dx + dz * dz;
  let t = l2 > 0 ? ((px - ax) * dx + (pz - az) * dz) / l2 : 0;
  t = clamp(t, 0, 1);
  const qx = ax + dx * t - px, qz = az + dz * t - pz;
  return [qx * qx + qz * qz, t];
}

// 视觉抖动等非密码学用途的随机数统一出口
export const rand01 = Math.random;
export const jitter = s => (rand01() - 0.5) * s;      // 居中抖动
export const chance = p => rand01() > 1 - p;          // 概率判定
export const coin = () => (rand01() > 0.5 ? 1 : -1);  // 二选一
export const rrange = (a, b) => a + rand01() * (b - a); // 区间随机
