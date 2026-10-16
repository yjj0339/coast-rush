// 街机化极品飞车风物理：抓地分层(柏油/砂石/草地/沙地/水域)、漂移、坡度、碰撞
import { terrainH } from './height.js';
import { clamp, catmull, SpatialHash, segDist2 } from './util.js';

export const SURF = { ASPHALT: 0, GRAVEL: 1, GRASS: 2, SAND: 3, WATER: 4 };
export const SURF_NAME = ['柏油', '砂石', '草地', '沙滩', '水域'];

const LAT_ACC = [13.5, 6.0, 5.0, 4.6, 3.0];
const LAT_DAMP = [6.5, 3.2, 2.6, 2.4, 1.6];
const ROLL = [0.5, 2.2, 7.0, 8.0, 16.0];
const ACC_MUL = [1.0, 0.75, 0.5, 0.42, 0.25];
const SLIP = [0.34, 0.85, 1.0, 1.0, 0.6];

export class CarPhysics {
  constructor(spec, colliders) {
    this.spec = spec;
    this.pos = { x: spec.spawn.x, y: 0, z: spec.spawn.z };
    this.yaw = spec.spawn.yaw || 0;
    this.vF = 0; this.vR = 0; this.vy = 0;
    this.steer = 0;
    this.grounded = true;
    this.surface = SURF.ASPHALT;
    this.drift = 0;          // 0..1 漂移强度（供特效/音效）
    this.impact = 0;         // 本帧碰撞强度
    this.gear = 0; this.rpm = 0;
    this.nitro = 0.4; this.boosting = false;
    this.waterT = 0;
    this.roadSamples = [];

    this.roadHash = new SpatialHash(24);
    for (const road of spec.roads) {
      const pts = catmull(road.pts, 3.0, false);
      for (let i = 0; i < pts.length; i++) {
        const [x, z] = pts[i];
        const smp = { x, z, w: road.w, dx: 0, dz: 1 };
        if (i > 0) {
          const p = pts[i - 1];
          const d = Math.hypot(x - p[0], z - p[1]) || 1;
          smp.dx = (x - p[0]) / d; smp.dz = (z - p[1]) / d;
          const prev = this.roadSamples[this.roadSamples.length - 1];
          prev.dx = smp.dx; prev.dz = smp.dz;
        }
        this.roadSamples.push(smp);
        this.roadHash.add(x, z, { w: road.w, idx: this.roadSamples.length - 1 });
      }
    }
    this.rectHash = new SpatialHash(30);
    for (const r of colliders.rects) this.rectHash.add(r[0], r[1], r);
    this.circleHash = new SpatialHash(30);
    for (const c of colliders.circles) this.circleHash.add(c[0], c[1], c);
    this.railSegs = [];
    this.railHash = new SpatialHash(30);
    for (const poly of colliders.rails) {
      for (let i = 0; i < poly.length - 2; i += 2) {
        const seg = [poly[i], poly[i + 1], poly[i + 2], poly[i + 3]];
        this.railSegs.push(seg);
        this.railHash.add((seg[0] + seg[2]) / 2, (seg[1] + seg[3]) / 2, seg);
      }
    }
    this._q = [];
    this.teleport(spec.spawn.x, spec.spawn.z, spec.spawn.yaw || 0);
  }

  surfaceAt(x, z) {
    const h = terrainH(x, z);
    const near = this.roadHash.query(x, z, 26, this._q);
    let best = 1e9, bestW = 0;
    for (const p of near) {
      const d = Math.hypot(p.x - x, p.z - z);
      if (d < best) { best = d; bestW = p.data.w; }
    }
    if (best < bestW / 2 + 1.2) return SURF.ASPHALT;
    if (best < bestW / 2 + 3.5) return SURF.GRAVEL;
    const lk = this.spec.lake;
    if (Math.hypot(x - lk.x, z - lk.z) < lk.r - 8 && h < lk.y + 0.4) return SURF.WATER;
    if (z > 815 && h < this.spec.sea.y + 0.25) return SURF.WATER;   // 开进海里
    if (z > 824 && h < 0.6) return SURF.SAND;
    return SURF.GRASS;
  }

  teleport(x, z, yaw) {
    this.pos.x = x; this.pos.z = z;
    this.pos.y = terrainH(x, z);
    this.yaw = yaw;
    this.vF = this.vR = this.vy = 0;
    this.steer = 0;
    this.waterT = 0;
  }

  respawnNearest() {
    let best = 1e18, bi = 0;
    for (let i = 0; i < this.roadSamples.length; i++) {
      const s = this.roadSamples[i];
      const d = (s.x - this.pos.x) ** 2 + (s.z - this.pos.z) ** 2;
      if (d < best) { best = d; bi = i; }
    }
    const s = this.roadSamples[bi];
    this.teleport(s.x, s.z, Math.atan2(s.dx, s.dz));
  }

  step(dt, input, fx) {
    const S = this.surface = this.surfaceAt(this.pos.x, this.pos.z);
    this.impact = 0;
    const inWater = S === SURF.WATER;
    const sy = Math.sin(this.yaw), cy = Math.cos(this.yaw);

    if (this.grounded && !inWater) {
      // —— 纵向 ——
      let a = 0;
      const v = this.vF;
      if (input.throttle > 0) {
        const pw = 15.8 * Math.max(0, 1 - Math.pow(Math.max(0, v) / 86, 2.6));
        a += input.throttle * pw * ACC_MUL[S];
      }
      if (input.brake > 0) {
        if (v > 0.6) a -= 30 * input.brake * (S === 0 ? 1 : 0.72);
        else if (v > -13) a -= 7.5 * input.brake * ACC_MUL[S];
      }
      a -= 0.0011 * v * Math.abs(v) + ROLL[S] * Math.sign(v) * Math.min(1, Math.abs(v) / 2 + 0.15);
      if (input.handbrake) a -= 5.5 * Math.sign(v) * Math.min(1, Math.abs(v));
      // —— 氮气：漂移积攒，Shift 释放 ——
      const wantBoost = input.nitro > 0 && this.nitro > 0.02 && v > 3 && !input.handbrake;
      this.boosting = wantBoost;
      if (wantBoost) {
        a += 9.6;
        this.nitro = Math.max(0, this.nitro - dt / 3.4);
      } else {
        this.nitro = Math.min(1, this.nitro + dt * (0.03 + this.drift * 0.24));
      }
      // 坡度重力分量
      const e = 1.5;
      const gx = (terrainH(this.pos.x + e, this.pos.z) - terrainH(this.pos.x - e, this.pos.z)) / (2 * e);
      const gz = (terrainH(this.pos.x, this.pos.z + e) - terrainH(this.pos.x, this.pos.z - e)) / (2 * e);
      const slopeF = gx * sy + gz * cy;   // 前方上坡为正 → 减速；下坡 → 助推
      a -= 9.8 * slopeF * 0.85;
      if (S === SURF.GRASS || S === SURF.SAND) a += (Math.random() - 0.5) * Math.min(3, Math.abs(v) * 0.12);
      this.vF += a * dt;

      // —— 转向（抓地极限限制横摆）——
      const maxSteer = 0.58 / (1 + Math.abs(this.vF) * 0.052);
      this.steer += (input.steer * maxSteer - this.steer) * Math.min(1, dt * 7);
      const yawRaw = this.vF / 2.9 * Math.tan(this.steer);
      const latMax = LAT_ACC[S] * (input.handbrake ? 0.52 : 1);
      let yaw;
      if (Math.abs(yawRaw * this.vF) > latMax) {
        const clamped = Math.sign(yawRaw) * latMax / Math.max(Math.abs(this.vF), 0.5);
        // 前轮抓不住的部分变成滑移
        this.vR += -(yawRaw - clamped) * this.vF * dt * 1.15;
        yaw = clamped;
      } else yaw = yawRaw;
      if (input.handbrake) yaw *= 1.22;
      this.yaw += yaw * dt;
      // 弯中离心甩尾
      const slipK = SLIP[S] * (input.handbrake ? 1.7 : 1);
      this.vR += -yaw * this.vF * dt * slipK;
      // 侧向阻尼
      this.vR *= Math.exp(-LAT_DAMP[S] * (input.handbrake ? 0.32 : 1) * dt);
    } else if (inWater) {
      this.vF *= Math.exp(-2.8 * dt); this.vR *= Math.exp(-3.5 * dt);
      this.waterT += dt;
    }

    // —— 空中/落地 ——
    const groundY = terrainH(this.pos.x, this.pos.z);
    if (this.grounded) {
      if (this.pos.y > groundY + 0.28 && this.vy <= 0) {
        this.grounded = false;
        this.vy = Math.max(0, this.pos.y - groundY) * 2;
      } else {
        this.pos.y = groundY;
      }
    }
    if (!this.grounded) {
      this.vy -= 22 * dt;
      this.pos.y += this.vy * dt;
      this.pos.x += sy * this.vF * dt + cy * this.vR * dt;
      this.pos.z += cy * this.vF * dt - sy * this.vR * dt;
      if (this.pos.y <= groundY) {
        this.pos.y = groundY; this.grounded = true;
        if (this.vy < -7) { this.impact = Math.min(12, -this.vy * 0.8); fx.impact && fx.impact(this.impact); }
        this.vy = 0;
      }
    } else {
      this.pos.x += sy * this.vF * dt + cy * this.vR * dt;
      this.pos.z += cy * this.vF * dt - sy * this.vR * dt;
    }

    // —— 碰撞 ——
    const R = 1.12;
    let velx = sy * this.vF + cy * this.vR;
    let velz = cy * this.vF - sy * this.vR;

    // 建筑（轴对齐矩形）
    const rects = this.rectHash.query(this.pos.x, this.pos.z, 8, this._q);
    for (const p of rects) {
      const [cx, cz, hw, hd] = p.data;
      const dx = this.pos.x - clamp(this.pos.x, cx - hw, cx + hw);
      const dz = this.pos.z - clamp(this.pos.z, cz - hd, cz + hd);
      let nx = 0, nz = 0, pen = 0;
      if (dx === 0 && dz === 0) {
        const px = hw + R - Math.abs(this.pos.x - cx);
        const pz2 = hd + R - Math.abs(this.pos.z - cz);
        if (px < pz2) { nx = Math.sign(this.pos.x - cx) || 1; pen = px; }
        else { nz = Math.sign(this.pos.z - cz) || 1; pen = pz2; }
      } else {
        const d = Math.hypot(dx, dz);
        if (d >= R) continue;
        nx = dx / (d || 1); nz = dz / (d || 1); pen = R - d;
      }
      this.pos.x += nx * pen; this.pos.z += nz * pen;
      const vn = velx * nx + velz * nz;
      if (vn < 0) {
        velx -= nx * vn * 1.45; velz -= nz * vn * 1.45;
        this.impact = Math.max(this.impact, -vn);
      }
    }
    // 圆柱（灯杆/树/灯塔…）
    const circles = this.circleHash.query(this.pos.x, this.pos.z, 8, this._q);
    for (const p of circles) {
      const [cx, cz, cr] = p.data;
      const dx = this.pos.x - cx, dz = this.pos.z - cz;
      const rr = cr + R;
      const d2 = dx * dx + dz * dz;
      if (d2 >= rr * rr || d2 < 1e-9) continue;
      const d = Math.sqrt(d2);
      const nx = dx / d, nz = dz / d;
      this.pos.x = cx + nx * rr; this.pos.z = cz + nz * rr;
      const vn = velx * nx + velz * nz;
      if (vn < 0) {
        velx -= nx * vn * 1.4; velz -= nz * vn * 1.4;
        this.impact = Math.max(this.impact, -vn);
      }
    }
    // 护栏（线段）
    const rails = this.railHash.query(this.pos.x, this.pos.z, 10, this._q);
    for (const p of rails) {
      const [ax, az, bx, bz] = p.data;
      const [d2, t] = segDist2(this.pos.x, this.pos.z, ax, az, bx, bz);
      const rr = R + 0.45;
      if (d2 >= rr * rr) continue;
      const d = Math.sqrt(d2) || 0.001;
      const qx = ax + (bx - ax) * t, qz = az + (bz - az) * t;
      const nx = (this.pos.x - qx) / d, nz = (this.pos.z - qz) / d;
      this.pos.x = qx + nx * rr; this.pos.z = qz + nz * rr;
      const vn = velx * nx + velz * nz;
      if (vn < 0) {
        velx -= nx * vn * 1.35; velz -= nz * vn * 1.35;
        this.impact = Math.max(this.impact, -vn * 0.8);
      }
    }
    // 世界边界
    const LIM = this.spec.limit;
    if (Math.abs(this.pos.x) > LIM) { this.pos.x = Math.sign(this.pos.x) * LIM; velx *= -0.3; }
    if (Math.abs(this.pos.z) > LIM) { this.pos.z = Math.sign(this.pos.z) * LIM; velz *= -0.3; }

    // 回写局部速度
    this.vF = velx * sy + velz * cy;
    this.vR = velx * cy - velz * sy;
    if (this.impact > 3.5) fx.impact && fx.impact(this.impact);

    // 漂移强度
    const slideSpeed = Math.abs(this.vR);
    const sp = Math.abs(this.vF);
    this.drift = clamp((slideSpeed - 2.2) / 7, 0, 1) * clamp(sp / 8, 0, 1);
    if (inWater && this.waterT > 1.4) this.respawnNearest();

    // 挡位/转速
    const bands = [0, 9, 17, 26, 37, 52, 70, 1000];
    const av = Math.abs(this.vF);
    let g = 1;
    while (g < 6 && av > bands[g]) g++;
    this.gear = this.vF < -0.5 ? -1 : (av < 0.5 ? 0 : g);
    const lo = bands[g - 1], hi = bands[g];
    this.rpm = clamp(0.18 + (av - lo) / (hi - lo) * 0.82, 0, 1);
    if (this.gear <= 0) this.rpm = clamp(av / 12, 0, 0.6);

    return { surface: S, impact: this.impact, drift: this.drift };
  }
}
