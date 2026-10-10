// 截图/测试钩子：URL 参数驱动的机位与状态暴露（与主逻辑解耦）
const POSES = {
  spawn: [0, 620, 0], city: [0, 320, 0], coast: [300, 700, 0.4],
  beach: [200, 838, 0.1], hill: [-950, 420, 2.4], lighthouse: [-1030, 622, 0.05],
  highway: [-700, 762, 1.5], lake: [900, 40, 1.2], park: [-80, 160, 0.3],
};

export function setupDevHooks(phys, applyPaint, poseKey, speedRaw) {
  const pose = Object.prototype.hasOwnProperty.call(POSES, poseKey) ? POSES[poseKey] : null;
  if (pose) phys.teleport(pose[0], pose[1], pose[2]);
  if (speedRaw) {
    const v = parseFloat(speedRaw);
    if (Number.isFinite(v)) phys.vF = Math.max(-20, Math.min(80, v));
  }

  const state = { ready: false, x: 0, z: 0, speed: 0, gear: 0, surface: 0, fps: 0, drift: 0 };
  window.__state = state;
  window.__teleport = (x, z, yaw) => phys.teleport(x, z, yaw);
  window.__paint = i => applyPaint(i);
  window.__phys = phys;
  return state;
}
