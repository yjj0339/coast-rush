// HUD：小地图（预渲染路网）+ 仪表 + 提示
import * as THREE from 'three';
import { catmull } from './util.js';
import { SURF_NAME } from './physics.js';

const MAP_SIZE = 220;
const WORLD = 2900;   // 小地图覆盖范围

export class Hud {
  constructor(spec, colliders) {
    this.spec = spec;
    this.minimap = document.getElementById('minimap');
    this.ctx = this.minimap.getContext('2d');
    this.speedNum = document.getElementById('speedNum');
    this.gearBadge = document.getElementById('gearBadge');
    this.surfChip = document.getElementById('surfChip');
    this.toastEl = document.getElementById('toast');
    this.nitroFill = document.getElementById('nitroFill');
    this.toastTimer = 0;

    // —— 预渲染底图 ——
    const off = document.createElement('canvas');
    off.width = off.height = 512;
    const c = off.getContext('2d');
    const k = 512 / WORLD;
    const cx = 256, cz = 256;
    const px = x => cx + x * k, pz = z => cz - z * k;
    // 陆地/海洋
    c.fillStyle = '#e7f2dd';
    c.fillRect(0, 0, 512, 512);
    c.fillStyle = '#b8dcf2';
    c.fillRect(0, pz(880), 512, 512);
    // 湖
    c.beginPath();
    c.ellipse(px(spec.lake.x), pz(spec.lake.z), spec.lake.r * k, spec.lake.r * k, 0, 0, 7);
    c.fill();
    // 建筑
    c.fillStyle = '#ccd3da';
    for (const r of colliders.rects) {
      c.fillRect(px(r[0] - r[2]), pz(r[1] - r[3]), r[2] * 2 * k, r[3] * 2 * k);
    }
    // 道路
    const drawRoad = (pts, w, col) => {
      c.strokeStyle = col; c.lineWidth = w; c.lineCap = 'round'; c.lineJoin = 'round';
      c.beginPath();
      pts.forEach((p, i) => i ? c.lineTo(px(p[0]), pz(p[1])) : c.moveTo(px(p[0]), pz(p[1])));
      c.stroke();
    };
    for (const r of spec.roads) {
      const pts = catmull(r.pts, 6, false);
      const w = r.type === 'hw' ? 4.2 : 2.6;
      drawRoad(pts, w + 1.4, '#9aa2ab');
      drawRoad(pts, w, r.type === 'hw' ? '#f2f4f6' : '#e8ebef');
    }
    // 地标
    c.font = 'bold 15px sans-serif';
    c.fillStyle = '#c0392b';
    c.fillText('★', px(colliders.pois.lighthouse[0]) - 6, pz(colliders.pois.lighthouse[1]) + 5);
    this.base = off;
  }

  toast(msg) {
    this.toastEl.textContent = msg;
    this.toastEl.classList.add('show');
    this.toastTimer = 2.2;
  }

  frame(dt, phys, traffic, camYaw) {
    const kmh = Math.round(Math.abs(phys.vF) * 3.6);
    this.speedNum.textContent = kmh;
    const g = phys.gear;
    this.gearBadge.textContent = g === -1 ? 'R' : g === 0 ? 'N' : String(g);
    this.nitroFill.style.width = Math.round((phys.nitro || 0) * 100) + '%';
    this.nitroFill.classList.toggle('boost', !!phys.boosting);
    const s = phys.surface;
    if (this._surf !== s) {
      this._surf = s;
      this.surfChip.textContent = SURF_NAME[s];
      this.surfChip.className = '';
      this.surfChip.id = 'surfChip';
      if (s === 1) this.surfChip.classList.add('gravel');
      else if (s === 2) this.surfChip.classList.add('grass');
      else if (s === 3) this.surfChip.classList.add('sand');
      else if (s === 4) this.surfChip.classList.add('air');
    }
    if (this.toastTimer > 0) {
      this.toastTimer -= dt;
      if (this.toastTimer <= 0) this.toastEl.classList.remove('show');
    }
    this.drawMap(phys, traffic, camYaw);
  }

  drawMap(phys, traffic, camYaw) {
    const c = this.ctx;
    const k = 512 / WORLD;
    c.clearRect(0, 0, MAP_SIZE, MAP_SIZE);
    const me = { mx: 128 + phys.pos.x * k, mz: 128 - phys.pos.z * k };
    c.save();
    c.beginPath();
    c.arc(128, 128, 107, 0, 7);
    c.clip();
    c.translate(128 - me.mx, 128 - me.mz);
    c.drawImage(this.base, 0, 0, 512, 512, -256, -256, 512, 512);
    // 交通
    if (traffic) {
      c.fillStyle = '#5b6b7c';
      for (const car of traffic.cars) {
        c.fillRect(128 + car.x * k - 1.6, 128 - car.z * k - 1.6, 3.2, 3.2);
      }
    }
    // 玩家箭头
    c.translate(me.mx, me.mz);
    c.rotate(phys.yaw);
    c.fillStyle = '#1d9bf0';
    c.strokeStyle = '#fff';
    c.lineWidth = 1.5;
    c.beginPath();
    c.moveTo(0, -7); c.lineTo(5, 6); c.lineTo(0, 3); c.lineTo(-5, 6);
    c.closePath(); c.fill(); c.stroke();
    c.restore();
    // 外框
    c.strokeStyle = 'rgba(60,100,150,.35)';
    c.lineWidth = 2;
    c.beginPath(); c.arc(128, 128, 107, 0, 7); c.stroke();
  }
}
