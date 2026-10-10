// 交通 AI：沿路网环线巡航的轿车/货车 + 路边停车
import * as THREE from 'three';
import { terrainH } from './height.js';
import { catmull } from './util.js';

const PASTELS = [0xe8eaee, 0xc23b3b, 0x2f6fc0, 0x30443e, 0xd8b13c, 0x7a8290, 0x274a33, 0x96682e];

class Route {
  constructor(pts, closed) {
    this.pts = catmull(pts, 4.0, closed);
    this.len = [0];
    for (let i = 1; i < this.pts.length; i++) {
      this.len.push(this.len[i - 1] + Math.hypot(this.pts[i][0] - this.pts[i - 1][0], this.pts[i][1] - this.pts[i - 1][1]));
    }
    this.total = this.len[this.len.length - 1];
  }
  at(s) {
    s = ((s % this.total) + this.total) % this.total;
    let lo = 0, hi = this.len.length - 1;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (this.len[mid] < s) lo = mid + 1; else hi = mid; }
    const i = Math.max(1, lo);
    const t = (s - this.len[i - 1]) / Math.max(0.001, this.len[i] - this.len[i - 1]);
    const a = this.pts[i - 1], b = this.pts[i];
    const dx = b[0] - a[0], dz = b[1] - a[1];
    const l = Math.hypot(dx, dz) || 1;
    return { x: a[0] + dx * t, z: a[1] + dz * t, dx: dx / l, dz: dz / l };
  }
}

export class Traffic {
  constructor(scene, spec, sedanGLTF, vanGLTF, onCollide) {
    this.cars = [];
    this.scene = scene;
    this.onCollide = onCollide;
    const routes = spec.routes.map(r => new Route(r.pts, r.closed));
    const plan = [
      { r: 0, n: 5 }, { r: 1, n: 5 }, { r: 2, n: 4 }, { r: 3, n: 3 }, { r: 4, n: 3 },
    ];
    let vi = 0;
    for (const { r, n } of plan) {
      const route = routes[r];
      const hw = routes[r].pts && spec.routes[r].id === 'coast' ? 4.3 : 3.1;
      for (let k = 0; k < n; k++) {
        const isVan = (vi % 4) === 3;
        const src = isVan ? vanGLTF : sedanGLTF;
        const obj = src.scene.clone(true);
        // 每台车独立车漆
        const paintName = isVan ? 'VanPaint' : 'SedPaint';
        obj.traverse(o => {
          if (o.isMesh && o.material && o.material.name === paintName) {
            o.material = o.material.clone();
            o.material.color.setHex(PASTELS[(vi * 3 + 1) % PASTELS.length]);
          }
          if (o.isMesh) { o.castShadow = true; o.receiveShadow = false; }
        });
        scene.add(obj);
        const car = {
          obj, route, s: route.total * (k / n) + Math.random() * 30,
          speed: spec.routes[r].speed[0] + Math.random() * (spec.routes[r].speed[1] - spec.routes[r].speed[0]),
          lane: hw, wobble: Math.random() * 10, wheels: [], yaw: 0, x: 0, z: 0, brakeT: 0,
        };
        obj.traverse(o => { if (/^S?Spin/i.test(o.name)) car.wheels.push(o); });
        this.cars.push(car);
        vi++;
      }
    }
    // —— 路边停车 ——
    this.parked = [];
    const gridRoads = spec.roads.filter(r => r.type === 'st');
    for (let k = 0; k < 10; k++) {
      const road = gridRoads[Math.floor(Math.random() * gridRoads.length)];
      const a = road.pts[0], b = road.pts[1];
      const t = 0.2 + Math.random() * 0.6;
      const x = a[0] + (b[0] - a[0]) * t, z = a[1] + (b[1] - a[1]) * t;
      const vertical = Math.abs(b[0] - a[0]) < 1;
      const side = Math.random() < 0.5 ? 1 : -1;
      const ox = vertical ? side * 4.6 : 0, oz = vertical ? 0 : side * 4.6;
      const yaw = vertical ? 0 : Math.PI / 2;
      const px = x + ox, pz = z + oz;
      const obj = sedanGLTF.scene.clone(true);
      obj.traverse(o => {
        if (o.isMesh && o.material && o.material.name === 'SedPaint') {
          o.material = o.material.clone();
          o.material.color.setHex(PASTELS[(k * 5 + 2) % PASTELS.length]);
        }
        if (o.isMesh) { o.castShadow = true; }
      });
      obj.position.set(px, terrainH(px, pz), pz);
      obj.rotation.y = yaw + (Math.random() - 0.5) * 0.06;
      scene.add(obj);
      this.parked.push({ x: px, z: pz });
      onCollide.addStaticCircle(px, pz, 1.35);
    }
  }

  update(dt, player) {
    for (const c of this.cars) {
      // 前方有玩家则刹车
      let target = c.speed;
      const ahead = c.route.at(c.s + 9);
      const dpx = player.x - ahead.x, dpz = player.z - ahead.z;
      if (dpx * dpx + dpz * dpz < 81) {
        const here = c.route.at(c.s);
        const toP = (player.x - here.x) * c.route.at(c.s).dx + (player.z - here.z) * c.route.at(c.s).dz;
        if (toP > -2) target = Math.min(target, 2.5);
      }
      c.cur = c.cur === undefined ? c.speed : c.cur;
      c.cur += (target - c.cur) * Math.min(1, dt * 2.2);
      c.s += c.cur * dt;
      const p = c.route.at(c.s);
      const nx = -p.dz, nz = p.dx;   // 右侧车道
      const wob = Math.sin(c.wobble + c.s * 0.02) * 0.35;
      c.x = p.x + nx * (c.lane + wob);
      c.z = p.z + nz * (c.lane + wob);
      c.yaw = Math.atan2(p.dx, p.dz);
      c.obj.position.set(c.x, terrainH(c.x, c.z), c.z);
      c.obj.rotation.y = c.yaw;
      for (const w of c.wheels) w.rotation.x -= c.cur * dt / 0.33;

      // 与玩家碰撞
      const dx = player.x - c.x, dz = player.z - c.z;
      const d2 = dx * dx + dz * dz;
      if (d2 < 2.6 * 2.6 && d2 > 0.001) {
        const d = Math.sqrt(d2);
        const nx = dx / d, nz = dz / d;
        this.onCollide.hit(nx, nz, d, 2.6, c.cur);
        c.cur *= 0.4;
      }
    }
  }
}
