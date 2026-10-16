// 极速海岸 Coast Rush —— 主程序
import * as THREE from 'three';
import { Sky } from 'three/addons/objects/Sky.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { terrainH } from './height.js';
import { loadAssets, assemble } from './world.js';
import { CarPhysics, SURF } from './physics.js';
import { Traffic } from './traffic.js';
import { SkidMarks, Smoke } from './effects.js';
import { Input } from './input.js';
import { AudioSys } from './audio.js';
import { Hud } from './hud.js';
import { setupDevHooks } from './devhooks.js';
import { clamp, damp, jitter, chance, coin, rrange, rand01 } from './util.js';

const qs = new URLSearchParams(location.search);
const el = id => document.getElementById(id);

// ---------- 渲染器 / 场景 ----------
const canvas = el('gl');
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
} catch (e) {
  el('ldTip').textContent = '设备不支持 WebGL';
  throw e;
}
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.88;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(62, innerWidth / innerHeight, 0.3, 5000);
camera.position.set(0, 4, 626);

// ---------- 数据 ----------
const SPEC = await fetch('assets/data/world-spec.json').then(r => r.json());
const COL = await fetch('assets/data/colliders.json').then(r => r.json());

el('ldTip').textContent = '正在铺装海岸公路…';
const assets = await loadAssets(SPEC, COL, p => {
  el('ldFill').style.width = Math.round(p * 100) + '%';
  el('ldTip').textContent = p < 0.6 ? '正在铺装海岸公路…' : p < 0.95 ? '正在驶入城市…' : '即将出发…';
});

// ---------- 天空 / 环境 / 雾 ----------
const sunDir = new THREE.Vector3(...SPEC.sun.dir).normalize();
const sky = new Sky();
sky.scale.setScalar(4500);
const su = sky.material.uniforms;
su.turbidity.value = 3.4;
su.rayleigh.value = 2.1;
su.mieCoefficient.value = 0.0045;
su.mieDirectionalG.value = 0.8;
su.sunPosition.value.copy(sunDir).multiplyScalar(100);
scene.fog = new THREE.Fog(new THREE.Color(SPEC.fog.color), 520, 2300);

const pmrem = new THREE.PMREMGenerator(renderer);
{
  scene.add(sky);
  const envScene = new THREE.Scene();
  scene.remove(sky); envScene.add(sky);
  const envRT = pmrem.fromScene(envScene);
  scene.add(sky);
  scene.environment = envRT.texture;
  if ('environmentIntensity' in scene) scene.environmentIntensity = 0.55;
}

const sun = new THREE.DirectionalLight(new THREE.Color(SPEC.sun.color[0], SPEC.sun.color[1], SPEC.sun.color[2]), 2.65);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
sun.shadow.camera.near = 30;
sun.shadow.camera.far = 950;
sun.shadow.camera.left = -125; sun.shadow.camera.right = 125;
sun.shadow.camera.top = 125; sun.shadow.camera.bottom = -125;
sun.shadow.bias = -0.00025;
sun.shadow.normalBias = 0.5;
scene.add(sun); scene.add(sun.target);
scene.add(new THREE.HemisphereLight(0xbdd9ff, 0x86a06a, 0.3));

// ---------- 装配世界 ----------
const worldBits = assemble(scene, renderer, assets, SPEC, COL);
window.__world = worldBits;
el('ldFill').style.width = '100%';

const phys = new CarPhysics(SPEC, COL);
const audio = new AudioSys();
const input = new Input();
const skid = new SkidMarks(scene);
const smoke = new Smoke(scene, assets.tex.smoke);
let shake = 0;
const fxCallbacks = {
  impact: s => { audio.impact(s); shake = Math.min(0.7, shake + s * 0.035); },
  bump: k => { shake = Math.min(0.4, shake + k * 0.12); },
};

let traffic = null;
try {
  traffic = new Traffic(scene, SPEC, worldBits.sedan, worldBits.van, {
    hit: (nx, nz, d, rr) => {
      phys.pos.x += nx * (rr - d); phys.pos.z += nz * (rr - d);
      const sy = Math.sin(phys.yaw), cy = Math.cos(phys.yaw);
      let velx = sy * phys.vF + cy * phys.vR, velz = cy * phys.vF - sy * phys.vR;
      const vn = velx * nx + velz * nz;
      if (vn < 0) { velx -= nx * vn * 1.5; velz -= nz * vn * 1.5; }
      phys.vF = velx * sy + velz * cy; phys.vR = velx * cy - velz * sy;
      if (-vn > 3.5) { audio.impact(-vn); shake = Math.min(0.7, shake + -vn * 0.03); }
    },
    addStaticCircle: (x, z, r) => phys.circleHash.add(x, z, [x, z, r]),
  });
} catch (e) { console.error('traffic init', e); }

const hud = new Hud(SPEC, COL);

// ---------- 测速板 & 海岸冲刺 ----------
const BOARDS = (COL.pois && COL.pois.boards) || [];
const GATES = (COL.pois && COL.pois.gates) || [];
const boardCd = BOARDS.map(() => 0);
const flashEl = el('flash');
function cameraFlash() {
  flashEl.classList.add('snap');
  setTimeout(() => flashEl.classList.remove('snap'), 60);
}
let trapCd = 0;
function updateTraps(dt) {
  trapCd = Math.max(0, trapCd - dt);
  for (let i = 0; i < BOARDS.length; i++) {
    if (boardCd[i] > 0) { boardCd[i] -= dt; continue; }
    const dx = phys.pos.x - BOARDS[i][0], dz = phys.pos.z - BOARDS[i][1];
    if (dx * dx + dz * dz < 64) {
      boardCd[i] = 6;
      if (trapCd > 0) continue;
      trapCd = 1.0;
      cameraFlash();
      const kmh = Math.round(Math.abs(phys.vF) * 3.6);
      const key = 'cr_board_best_' + i;
      const old = parseInt(localStorage.getItem(key) || '0');
      if (kmh > old) {
        localStorage.setItem(key, String(kmh));
        hud.toast('📡 测速点 ' + i + '：' + kmh + ' km/h（新纪录！曾是 ' + old + '）');
      } else {
        hud.toast('📡 测速点 ' + i + '：' + kmh + ' km/h（纪录 ' + old + '）');
      }
      audio.impact(3);
    }
  }
}

let sprint = null;   // null=未开始; {phase:'count'|'run', t, split}
const sprintEl = el('sprintTimer');
const promptEl = el('prompt');
const near = (p, r) => { const dx = phys.pos.x - p[0], dz = phys.pos.z - p[1]; return dx * dx + dz * dz < r * r; };
function sprintPress() {
  if (GATES.length < 3) return;
  if (sprint) {
    sprint = null;
    sprintEl.classList.add('hidden');
    hud.toast('已放弃冲刺');
    return;
  }
  if (!near(GATES[0], 30)) { hud.toast('先开到西侧起点的冲刺门架下'); return; }
  sprint = { phase: 'count', t: 2.4, split: false };
  sprintEl.classList.remove('hidden');
}
function updateSprint(dt) {
  if (!sprint) {
    if (!promptEl.classList.contains('hidden')) promptEl.classList.add('hidden');
    if (GATES.length >= 3 && near(GATES[0], 22)) {
      promptEl.textContent = '⚡ 按 G 开始海岸冲刺（2.5km 滨海公路）';
      promptEl.classList.remove('hidden');
    }
    return;
  }
  if (sprint.phase === 'count') {
    sprint.t -= dt;
    sprintEl.classList.add('count');
    sprintEl.textContent = sprint.t > 1.6 ? '3' : sprint.t > 0.8 ? '2' : '1';
    if (sprint.t <= 0) {
      sprint.phase = 'run';
      sprint.t = 0;
      sprintEl.classList.remove('count');
      audio.impact(4);
    }
    return;
  }
  // 计时中
  sprint.t += dt;
  sprintEl.textContent = sprint.t.toFixed(2) + ' s';
  if (!sprint.split && near(GATES[1], 16)) {
    sprint.split = true;
    hud.toast('中途点 ' + sprint.t.toFixed(2) + ' s');
  }
  if (near(GATES[2], 16)) {
    if (sprint.split) {
      const t = sprint.t;
      const best = parseFloat(localStorage.getItem('cr_sprint_best') || '0');
      if (!best || t < best) {
        localStorage.setItem('cr_sprint_best', t.toFixed(2));
        hud.toast('🏁 冲刺完成 ' + t.toFixed(2) + ' s —— 新纪录！（旧 ' + best.toFixed(2) + '）');
      } else {
        hud.toast('🏁 冲刺完成 ' + t.toFixed(2) + ' s（最佳 ' + best.toFixed(2) + '）');
      }
      audio.impact(6);
    } else {
      hud.toast('漏掉中途点，成绩无效（再试一次）');
    }
    sprint = null;
    sprintEl.classList.add('hidden');
  } else if (near(GATES[0], 14) && sprint.t > 6) {
    sprint = null;
    sprintEl.classList.add('hidden');
    hud.toast('已放弃冲刺');
  }
}


// ---------- 车辆外观 ----------
const carObj = worldBits.car;
// 氮气尾焰（挂在车身，四出排气口，加色混合青色火焰）
const flames = [];
{
  const fg = new THREE.ConeGeometry(0.075, 0.9, 8);
  const fm = new THREE.MeshBasicMaterial({
    color: 0x9fecff, transparent: true, opacity: 1.0,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  for (const fxp of [0.30, 0.46, -0.30, -0.46]) {
    const f = new THREE.Mesh(fg, fm);
    f.rotation.x = -Math.PI / 2;          // 锥尖朝车尾
    f.position.set(fxp, 0.315, -2.58);
    f.visible = false;
    carObj.add(f);
    flames.push(f);
  }
}
const spins = ['SpinFL', 'SpinFR', 'SpinRL', 'SpinRR'].map(n => worldBits.wheels[n]).filter(Boolean);
const fronts = ['WheelFL', 'WheelFR'].map(n => worldBits.wheels[n]).filter(Boolean);
const PAINTS = [
  [0x00b0e6, '迈阿密青'], [0xff5a1f, '落日橙'], [0xe03131, '烈焰红'],
  [0xffd400, '竞速黄'], [0xf4f6f8, '珍珠白'], [0x18202a, '曜石黑'],
];
let paintIdx = parseInt(localStorage.getItem('cr_paint') || '0') || 0;
function applyPaint(i) {
  paintIdx = ((i % PAINTS.length) + PAINTS.length) % PAINTS.length;
  const p = worldBits.paints.CarPaint;
  if (p) p.color.setHex(PAINTS[paintIdx][0]);
  localStorage.setItem('cr_paint', String(paintIdx));
}
applyPaint(paintIdx);

// ---------- 画质 ----------
const QNAME = { high: '高', medium: '中', low: '低' };
const QLIST = ['high', 'medium', 'low'];
let quality = qs.get('q') && QLIST.includes(qs.get('q')) ? qs.get('q')
  : (localStorage.getItem('cr_quality') || (matchMedia('(pointer: coarse)').matches ? 'medium' : 'high'));
let composer = null;
let camMode = 0;
function buildComposer(samples, bloom) {
  const rt = new THREE.WebGLRenderTarget(innerWidth, innerHeight, {
    samples, type: THREE.HalfFloatType,
  });
  const c = new EffectComposer(renderer, rt);
  c.addPass(new RenderPass(scene, camera));
  if (bloom) c.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), bloom, 0.35, 1.0));
  c.addPass(new OutputPass());
  return c;
}
function setShadowSize(n) {
  if (sun.shadow.mapSize.x !== n) {
    sun.shadow.mapSize.set(n, n);
    if (sun.shadow.map) { sun.shadow.map.dispose(); sun.shadow.map = null; }
  }
}
function applyQuality(q) {
  quality = q;
  localStorage.setItem('cr_quality', q);
  if (q === 'high') {
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    setShadowSize(4096);
    composer = buildComposer(4, 0.26);
  } else if (q === 'medium') {
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    setShadowSize(2048);
    composer = buildComposer(2, 0.2);
  } else {
    renderer.setPixelRatio(1);
    setShadowSize(1024);
    composer = null;
  }
  onResize();
  el('btnQuality').textContent = '✨ 画质:' + QNAME[q];
}

// ---------- UI 动作（命名函数，键盘与按钮共用） ----------
function cycleQuality() {
  applyQuality(QLIST[(QLIST.indexOf(quality) + 1) % QLIST.length]);
  hud.toast('画质：' + QNAME[quality]);
}
function toggleAudio() {
  const on = audio.toggle();
  el('btnAudio').textContent = on ? '🔊 声音' : '🔇 静音';
}
function doReset() { phys.respawnNearest(); hud.toast('已回到最近道路'); }
function cycleCam() { camMode = (camMode + 1) % 3; hud.toast(['追踪视角', '远景视角', '引擎盖视角'][camMode]); }
function cyclePaint() { applyPaint(paintIdx + 1); hud.toast('车色：' + PAINTS[paintIdx][1]); }

el('btnQuality').onclick = cycleQuality;
el('btnAudio').onclick = toggleAudio;
el('btnReset').onclick = doReset;
el('btnCam').onclick = cycleCam;
el('btnColor').onclick = cyclePaint;

input.onKey = code => {
  if (code === 'KeyR') doReset();
  else if (code === 'KeyV') cycleCam();
  else if (code === 'KeyC') cyclePaint();
  else if (code === 'KeyM') toggleAudio();
  else if (code === 'KeyQ') cycleQuality();
  else if (code === 'KeyG') sprintPress();
};

if (matchMedia('(pointer: coarse)').matches) el('touchUI').classList.remove('hidden');
applyQuality(quality);

// ---------- 相机 ----------
const camPos = new THREE.Vector3(0, 5, 630);
const camLook = new THREE.Vector3();
const carUp = new THREE.Vector3(0, 1, 0);

function updateCamera(dt, speedN) {
  const sy = Math.sin(phys.yaw), cy = Math.cos(phys.yaw);
  const driftSide = clamp(phys.vR * 0.10, -1.4, 1.4);
  let desired, look, stiff = 6.5;
  if (camMode === 2) {
    desired = new THREE.Vector3(phys.pos.x - sy * 0.35, phys.pos.y + 1.12, phys.pos.z - cy * 0.35);
    look = new THREE.Vector3(phys.pos.x + sy * 40, phys.pos.y + 1.4, phys.pos.z + cy * 40);
    stiff = 26;
  } else {
    const back = camMode === 0 ? 6.3 : 10.8;
    const up = camMode === 0 ? 2.5 : 3.7;
    desired = new THREE.Vector3(
      phys.pos.x - sy * back + cy * driftSide,
      phys.pos.y + up,
      phys.pos.z - cy * back - sy * driftSide);
    look = new THREE.Vector3(phys.pos.x + sy * 2.4, phys.pos.y + 1.25, phys.pos.z + cy * 2.4);
  }
  const k = 1 - Math.exp(-stiff * dt);
  camPos.lerp(desired, k);
  camLook.lerp(look, Math.min(1, k * 1.6));
  shake = Math.max(0, shake - dt * 1.6);
  const rumble = speedN > 0.72 ? (speedN - 0.72) * 0.16 : 0;
  const sh = shake + rumble;
  camera.position.copy(camPos);
  if (sh > 0.001) {
    camera.position.x += jitter(sh);
    camera.position.y += jitter(sh * 0.7);
    camera.position.z += jitter(sh);
  }
  camera.lookAt(camLook);
  const targetFov = 62 + 15 * Math.pow(speedN, 1.6) + (camMode === 2 ? 4 : 0);
  if (Math.abs(camera.fov - targetFov) > 0.05) {
    camera.fov = damp(camera.fov, targetFov, 4, dt);
    camera.updateProjectionMatrix();
  }
}

// ---------- 车辆姿态 ----------
let aLongSm = 0;
function updateCarVisual(dt) {
  const e = 1.5;
  const gx = (terrainH(phys.pos.x + e, phys.pos.z) - terrainH(phys.pos.x - e, phys.pos.z)) / (2 * e);
  const gz = (terrainH(phys.pos.x, phys.pos.z + e) - terrainH(phys.pos.x, phys.pos.z - e)) / (2 * e);
  const upT = new THREE.Vector3(-gx, 1, -gz).normalize();
  carUp.lerp(upT, 1 - Math.exp(-9 * dt)).normalize();
  const fwd0 = new THREE.Vector3(Math.sin(phys.yaw), 0, Math.cos(phys.yaw));
  const right = new THREE.Vector3().crossVectors(carUp, fwd0).normalize();
  const fwd = new THREE.Vector3().crossVectors(right, carUp).normalize().negate();
  const m = new THREE.Matrix4().makeBasis(right, carUp, fwd);
  carObj.quaternion.setFromRotationMatrix(m);
  const rollQ = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), clamp(-phys.vR * 0.014, -0.08, 0.08));
  const pitchQ = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), clamp(-aLongSm * 0.0032, -0.05, 0.05));
  carObj.quaternion.multiply(rollQ).multiply(pitchQ);
  carObj.position.set(phys.pos.x, phys.pos.y, phys.pos.z);
  for (const s of spins) s.rotation.x -= phys.vF * dt / 0.38;
  for (const f of fronts) f.rotation.y = phys.steer * 1.15;
}

// ---------- 胎痕/烟 ----------
let skidAcc = 0;
function rearWheelWorld(side) {
  const lx = side * 0.86, lz = -1.45;
  return {
    x: phys.pos.x + Math.sin(phys.yaw) * lz + Math.cos(phys.yaw) * lx,
    z: phys.pos.z + Math.cos(phys.yaw) * lz - Math.sin(phys.yaw) * lx,
  };
}
function updateEffects(dt, res) {
  const sp = Math.abs(phys.vF);
  const asphalt = res.surface === SURF.ASPHALT;
  const drifting = res.drift > 0.22 || (input.handbrake && sp > 6);
  skidAcc += dt;
  if (skidAcc > 0.02) {
    skidAcc = 0;
    for (const side of [-1, 1]) {
      const w = rearWheelWorld(side);
      skid.trail(side > 0 ? 'R' : 'L', w.x, phys.pos.y, w.z,
        Math.sin(phys.yaw), Math.cos(phys.yaw), asphalt && (drifting || (input.brake && sp > 22)));
    }
  }
  skid.update();
  if (asphalt && drifting && chance(res.drift * 0.9)) {
    const side = coin();
    const w = rearWheelWorld(side);
    smoke.emit(w.x, phys.pos.y + 0.25, w.z,
      jitter(2) - phys.vR * 0.2, 0.9 + rand01(), jitter(2),
      [0.82, 0.82, 0.84], rrange(0.9, 1.6));
  }
  if (!asphalt && res.surface !== SURF.WATER && sp > 7 && chance(0.5)) {
    const side = coin();
    const w = rearWheelWorld(side);
    let dust = [0.62, 0.55, 0.4];
    if (res.surface === SURF.SAND) dust = [0.88, 0.78, 0.55];
    smoke.emit(w.x, phys.pos.y + 0.2, w.z,
      jitter(1.5), 0.7 + rand01(), jitter(1.5), dust, rrange(0.8, 1.6));
  }
  smoke.update(dt);
}

// ---------- 测试钩子 ----------
const devState = setupDevHooks(phys, applyPaint, qs.get('pose') || '', qs.get('speed') || '');
if (qs.get('orbit')) camMode = 3;
if (qs.get('hud') === '0') { el('hud').classList.add('hidden'); el('touchUI').classList.add('hidden'); }

// ---------- 启动 ----------
let started = false;
const shotMode = qs.get('hud') === '0';
el('btnStart').disabled = false;
el('btnStart').textContent = shotMode ? '进入（截图模式）' : '进 入 驾 驶';
function startGame() {
  started = true;
  el('loader').classList.add('hidden');
  if (!shotMode) {
    el('hud').classList.remove('hidden');
    if (matchMedia('(pointer: coarse)').matches) el('touchUI').classList.remove('hidden');
  }
  audio.ensure();
}
el('btnStart').onclick = startGame;
if (shotMode) startGame();

function onResize() {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  if (composer) composer.setSize(innerWidth, innerHeight);
}
addEventListener('resize', onResize);
onResize();

// ---------- 主循环 ----------
const clock = new THREE.Clock();
let fpsAcc = 0, fpsN = 0, mapAcc = 0;
let driftAcc = 0, driftHold = 0, airT = 0, speedlineOn = false;
function tick() {
  requestAnimationFrame(tick);
  const dt = Math.min(clock.getDelta(), 0.05);
  fpsAcc += dt; fpsN++;
  if (fpsAcc > 0.5) { devState.fps = fpsN / fpsAcc; fpsAcc = 0; fpsN = 0; }

  const speedN = clamp(Math.abs(phys.vF) / 86, 0, 1);
  const res = { surface: phys.surface, drift: phys.drift };
  if (started) {
    const n = dt > 0.02 ? 2 : 1;
    for (let i = 0; i < n; i++) {
      const r = phys.step(dt / n, input, fxCallbacks);
      if (i === 0) Object.assign(res, r);
    }
    aLongSm = aLongSm * 0.9 + phys.vF * 0.1;
    if (traffic) traffic.update(dt, phys.pos);
    updateEffects(dt, res);
    updateTraps(dt);
    updateSprint(dt);

    // —— 漂移计分（结束 0.9s 后结算弹幕）——
    if (res.drift > 0.3) {
      driftAcc += res.drift * Math.abs(phys.vF) * dt * 14;
      driftHold = 0.9;
    } else if (driftAcc > 0) {
      driftHold -= dt;
      if (driftHold <= 0) {
        const pts = Math.round(driftAcc);
        if (pts > 80) hud.toast('漂移 +' + pts);
        driftAcc = 0;
      }
    }
    // —— 腾空提示 ——
    if (!phys.grounded) airT += dt;
    else { if (airT > 0.85) hud.toast('腾空飞跃！'); airT = 0; }
  }
  updateCarVisual(dt);

  // —— 氮气视觉：尾焰闪烁 + 速度线 + FOV 冲刺 ——
  const boosting = !!phys.boosting && phys.nitro > 0.02;
  for (const f of flames) {
    f.visible = boosting;
    if (boosting) f.scale.set(0.7 + rand01() * 0.7, 0.8 + rand01() * 1.9, 0.7 + rand01() * 0.7);
  }
  const sl = el('speedlines');
  const wantSl = boosting && speedN > 0.25;
  if (wantSl !== speedlineOn) { speedlineOn = wantSl; }
  sl.style.opacity = wantSl ? String(0.35 + speedN * 0.4) : '0';

  if (camMode === 3) {
    const t = performance.now() * 0.00012;
    camera.position.set(phys.pos.x + Math.cos(t) * 15, phys.pos.y + 5.2, phys.pos.z + Math.sin(t) * 15);
    camera.lookAt(phys.pos.x, phys.pos.y + 0.9, phys.pos.z);
    camPos.copy(camera.position);
  } else {
    updateCamera(dt, speedN + (boosting ? 0.16 : 0));
  }

  sun.position.set(phys.pos.x + sunDir.x * 430, phys.pos.y + sunDir.y * 430, phys.pos.z + sunDir.z * 430);
  sun.target.position.set(phys.pos.x, phys.pos.y, phys.pos.z);
  sun.target.updateMatrixWorld();

  worldBits.waterMat.normalMap.offset.x = performance.now() * 0.000012;
  worldBits.waterMat.normalMap.offset.y = performance.now() * 0.0000085;
  for (const c of worldBits.clouds) {
    c.position.x += dt * 1.6;
    if (c.position.x > 1700) c.position.x = -1700;
  }

  audio.update(phys.rpm, input.throttle, Math.abs(phys.vF), res.drift, boosting, dt);

  mapAcc += dt;
  if (mapAcc > 0.08 && started) { hud.frame(mapAcc, phys, traffic, camMode); mapAcc = 0; }

  devState.ready = true;
  devState.x = phys.pos.x; devState.z = phys.pos.z;
  devState.speed = Math.abs(phys.vF) * 3.6;
  devState.gear = phys.gear; devState.surface = phys.surface; devState.drift = phys.drift;
  devState.nitro = phys.nitro; devState.boosting = boosting;

  if (composer) composer.render();
  else renderer.render(scene, camera);
}
tick();
