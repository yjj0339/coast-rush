// 特效：漂移胎痕（环缓冲四边形）+ 轮胎烟/扬尘（点精灵）
import * as THREE from 'three';

export class SkidMarks {
  constructor(scene) {
    this.MAX = 1100;
    this.head = 0;
    const g = new THREE.BufferGeometry();
    this.pos = new Float32Array(this.MAX * 4 * 3);
    this.alpha = new Float32Array(this.MAX * 4);
    const idx = new Uint32Array(this.MAX * 6);
    for (let i = 0; i < this.MAX; i++) {
      const b = i * 4, o = i * 6;
      idx[o] = b; idx[o + 1] = b + 1; idx[o + 2] = b + 2;
      idx[o + 3] = b + 1; idx[o + 4] = b + 3; idx[o + 5] = b + 2;
    }
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('aAlpha', new THREE.BufferAttribute(this.alpha, 1).setUsage(THREE.DynamicDrawUsage));
    g.setIndex(new THREE.BufferAttribute(idx, 1));
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false,
      vertexShader: `attribute float aAlpha; varying float vA;
        void main(){ vA=aAlpha; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
      fragmentShader: `varying float vA;
        void main(){ gl_FragColor=vec4(0.09,0.09,0.10,vA*0.55); }`,
    });
    this.mesh = new THREE.Mesh(g, mat);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = 2;
    scene.add(this.mesh);
    this.last = {};
  }
  // wheelKey: FL/FR; 返回是否落痕
  trail(key, x, y, z, dirx, dirz, active, width = 0.3) {
    const prev = this.last[key];
    if (!active || !prev) { this.last[key] = { x, z }; return; }
    const dx = x - prev.x, dz = z - prev.z;
    const l = Math.hypot(dx, dz);
    if (l < 0.45) return;
    const i = this.head;
    this.head = (this.head + 1) % this.MAX;
    const nx = -dz / l * width / 2, nz = dx / l * width / 2;
    const b = i * 4;
    const set = (k, px, pz, a) => {
      this.pos[(b + k) * 3] = px; this.pos[(b + k) * 3 + 1] = y + 0.03; this.pos[(b + k) * 3 + 2] = pz;
      this.alpha[b + k] = a;
    };
    set(0, prev.x - nx, prev.z - nz, 0.85);
    set(1, prev.x + nx, prev.z + nz, 0.85);
    set(2, x - nx, z - nz, 0.85);
    set(3, x + nx, z + nz, 0.85);
    this.last[key] = { x, z };
    this.dirty = true;
  }
  update() {
    if (!this.dirty) return;
    const g = this.mesh.geometry;
    g.attributes.position.needsUpdate = true;
    g.attributes.aAlpha.needsUpdate = true;
    this.dirty = false;
  }
}

export class Smoke {
  constructor(scene, texture) {
    this.N = 150;
    this.head = 0;
    this.items = [];
    const g = new THREE.BufferGeometry();
    this.pos = new Float32Array(this.N * 3);
    this.life = new Float32Array(this.N);
    this.size = new Float32Array(this.N);
    this.col = new Float32Array(this.N * 3);
    this.vel = new Float32Array(this.N * 3);
    for (let i = 0; i < this.N; i++) this.items.push({ ttl: 1, t: 0 });
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('aLife', new THREE.BufferAttribute(this.life, 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('aSize', new THREE.BufferAttribute(this.size, 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('aCol', new THREE.BufferAttribute(this.col, 3).setUsage(THREE.DynamicDrawUsage));
    const mat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false,
      uniforms: { map: { value: texture } },
      vertexShader: `attribute float aLife; attribute float aSize; attribute vec3 aCol;
        varying float vL; varying vec3 vC;
        void main(){
          vL=aLife; vC=aCol;
          vec4 mv = modelViewMatrix*vec4(position,1.0);
          float grow = 1.0 + (1.0-aLife)*2.4;
          gl_PointSize = aSize*grow*(240.0/max(1.0,-mv.z));
          gl_Position = projectionMatrix*mv;
        }`,
      fragmentShader: `uniform sampler2D map; varying float vL; varying vec3 vC;
        void main(){
          vec4 t = texture2D(map, gl_PointCoord);
          gl_FragColor = vec4(vC, t.a*vL*0.42);
        }`,
    });
    this.points = new THREE.Points(g, mat);
    this.points.frustumCulled = false;
    scene.add(this.points);
  }
  emit(x, y, z, vx, vy, vz, color, size) {
    const i = this.head;
    this.head = (this.head + 1) % this.N;
    this.pos[i * 3] = x; this.pos[i * 3 + 1] = y; this.pos[i * 3 + 2] = z;
    this.vel[i * 3] = vx; this.vel[i * 3 + 1] = vy; this.vel[i * 3 + 2] = vz;
    this.life[i] = 1; this.size[i] = size;
    this.col[i * 3] = color[0]; this.col[i * 3 + 1] = color[1]; this.col[i * 3 + 2] = color[2];
    this.items[i].ttl = 0.75 + Math.random() * 0.5;
    this.items[i].t = 0;
    this.dirty = true;
  }
  update(dt) {
    let any = false;
    for (let i = 0; i < this.N; i++) {
      const it = this.items[i];
      if (it.t >= it.ttl) { if (this.life[i] > 0) { this.life[i] = 0; any = true; } continue; }
      it.t += dt;
      const k = Math.max(0, 1 - it.t / it.ttl);
      this.life[i] = k;
      this.pos[i * 3] += this.vel[i * 3] * dt;
      this.pos[i * 3 + 1] += this.vel[i * 3 + 1] * dt;
      this.pos[i * 3 + 2] += this.vel[i * 3 + 2] * dt;
      this.vel[i * 3] *= 0.92; this.vel[i * 3 + 2] *= 0.92;
      any = true;
    }
    if (!any && !this.dirty) return;
    const g = this.points.geometry;
    g.attributes.position.needsUpdate = true;
    g.attributes.aLife.needsUpdate = true;
    g.attributes.aSize.needsUpdate = true;
    g.attributes.aCol.needsUpdate = true;
    this.dirty = false;
  }
}
