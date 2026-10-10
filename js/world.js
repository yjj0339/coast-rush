// 世界装配：GLB 加载、材质修补、水面、云
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { terrainH } from './height.js';

export function loadAssets(spec, colliders, onProgress) {
  const manager = new THREE.LoadingManager();
  const loader = new GLTFLoader(manager);
  const texLoader = new THREE.TextureLoader(manager);

  const result = { glbs: {}, tex: {} };
  const files = [
    ['world', 'assets/models/world.glb'],
    ['car', 'assets/models/car.glb'],
    ['sedan', 'assets/models/sedan.glb'],
    ['van', 'assets/models/van.glb'],
  ];
  for (const [key, url] of files) {
    loader.load(url, g => { result.glbs[key] = g; }, undefined, err => console.error('load fail', url, err));
  }
  result.tex.cloud = texLoader.load('assets/textures/cloud.png');
  result.tex.smoke = texLoader.load('assets/textures/smoke.png');
  result.tex.waterN = texLoader.load('assets/textures/water_n.png');

  manager.onProgress = (url, done, total) => onProgress(done / total);
  return new Promise((resolve, reject) => {
    manager.onLoad = () => resolve(result);
    manager.onError = url => reject(new Error('资源加载失败: ' + url));
  });
}

function patchWorldMats(root) {
  root.traverse(o => {
    if (!o.isMesh) return;
    o.receiveShadow = true;
    o.castShadow = o.material && ['BldGlass', 'BldRes', 'BldShop'].includes(o.material.name);
    const m = o.material;
    if (!m) return;
    if (m.map) { m.map.anisotropy = 8; m.map.colorSpace = THREE.SRGBColorSpace; }
    if (m.name === 'Terrain') m.vertexColors = true;
    if (m.name === 'Asphalt') { m.roughness = 0.92; }
    if (m.name === 'FacGlass') { m.roughness = 0.28; m.metalness = 0.1; m.envMapIntensity = 0.9; }
    if (m.name === 'MarkW' || m.name === 'MarkY') { m.roughness = 0.6; }
    if (m.name === 'Frond') { m.side = THREE.DoubleSide; }
    if (m.name === 'Sail') { m.side = THREE.DoubleSide; }
  });
}

function upgradeCarPaint(root) {
  const paints = {};
  root.traverse(o => {
    if (!o.isMesh) return;
    o.castShadow = true;
    const m = o.material;
    if (!m) return;
    if (m.map) m.map.colorSpace = THREE.SRGBColorSpace;
    if (m.name === 'CarPaint' || m.name === 'SedPaint' || m.name === 'VanPaint') {
      const phys = new THREE.MeshPhysicalMaterial({
        color: m.color.clone(),
        metalness: m.metalness !== undefined ? m.metalness : 0.4,
        roughness: 0.28,
        clearcoat: 1.0,
        clearcoatRoughness: 0.06,
        envMapIntensity: 1.25,
      });
      phys.name = m.name;
      o.material = phys;
      paints[m.name] = phys;
    }
    if (m.transparent) { m.depthWrite = false; o.renderOrder = 3; }
  });
  return paints;
}

function findWheels(root) {
  const wheels = {};
  root.traverse(o => {
    if (/^Spin(FL|FR|RL|RR)$/.test(o.name)) wheels[o.name] = o;
    if (/^Wheel(FL|FR|RL|RR)$/.test(o.name)) wheels[o.name] = o;
  });
  return wheels;
}

export function assemble(scene, renderer, assets, spec, colliders) {
  const world = assets.glbs.world.scene;
  patchWorldMats(world);
  scene.add(world);

  // 水面（海 + 湖）
  const waterMat = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(spec.sea.color),
    roughness: 0.13, metalness: 0.0,
    normalMap: assets.tex.waterN,
    normalScale: new THREE.Vector2(0.55, 0.55),
    transparent: true, opacity: 0.99,
    envMapIntensity: 1.35,
  });
  assets.tex.waterN.wrapS = assets.tex.waterN.wrapT = THREE.RepeatWrapping;
  assets.tex.waterN.repeat.set(90, 90);
  const sea = new THREE.Mesh(new THREE.PlaneGeometry(7200, 7200), waterMat);
  sea.rotation.x = -Math.PI / 2;
  sea.position.set(0, spec.sea.y, 0);
  scene.add(sea);
  const lake = new THREE.Mesh(new THREE.CircleGeometry(spec.lake.r + 6, 40), waterMat);
  lake.rotation.x = -Math.PI / 2;
  lake.position.set(spec.lake.x, spec.lake.y, spec.lake.z);
  scene.add(lake);

  // 云（公告板精灵）
  const clouds = [];
  const cloudMat = new THREE.SpriteMaterial({ map: assets.tex.cloud, transparent: true, opacity: 0.62, depthWrite: false });
  for (let i = 0; i < 12; i++) {
    const s = new THREE.Sprite(cloudMat);
    const a = i / 12 * Math.PI * 2 + Math.random();
    const r = 300 + Math.random() * 1300;
    s.position.set(Math.cos(a) * r, 260 + Math.random() * 170, Math.sin(a) * r);
    const sc = 260 + Math.random() * 420;
    s.scale.set(sc, sc * 0.42, 1);
    scene.add(s);
    clouds.push(s);
  }

  const car = assets.glbs.car.scene;
  const paints = upgradeCarPaint(car);
  const wheels = findWheels(car);
  scene.add(car);

  const sedan = assets.glbs.sedan;
  const van = assets.glbs.van;
  upgradeCarPaint(sedan.scene);
  upgradeCarPaint(van.scene);
  // 模板从场景摘除（traffic 用 clone）
  scene.remove(sedan.scene);
  scene.remove(van.scene);

  return { world, car, paints, wheels, waterMat, clouds, sedan, van };
}
