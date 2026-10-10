// 地形高度公式——与 tools/worldspec.py 中的 terrain_h 保持一致（python tools/worldspec.py --verify 校验）
function sstep(t){return t*t*(3-2*t);}

export function terrainH(x, z) {
  const ax = Math.abs(x);
  const az = Math.abs(z);
  const b1 = 20.0*Math.sin(x*0.00155+1.3)*Math.cos(z*0.00142+0.7);
  const b2 = 10.0*Math.sin(x*0.0041+0.5)*Math.sin(z*0.0036+2.1);
  const b3 = 3.2*Math.sin(x*0.0105+2.0)*Math.cos(z*0.0092+0.3);
  const base = b1+b2+b3;
  const u = Math.max((ax-600.0)/180.0, (az-620.0)/180.0, 0.0);
  const m = u*u*(3.0-2.0*u);
  const c = sstep(Math.min(Math.max((z-480.0)/320.0, 0.0), 1.0));
  const roll = 1.0-0.92*c;
  const micro = 0.5*Math.sin(x*0.021+1.7)*Math.cos(z*0.017+0.9);
  let h = (base+micro)*m*roll;
  h += 52.0*Math.exp(-((x+980.0)**2+(z-560.0)**2)/(2.0*240.0**2));
  h -= 11.0*Math.exp(-((x-1050.0)**2+(z-60.0)**2)/(2.0*150.0**2));
  h += 22.0*Math.exp(-((x+380.0)**2+(z+900.0)**2)/(2.0*280.0**2));
  h += 18.0*Math.exp(-((x-880.0)**2+(z+700.0)**2)/(2.0*240.0**2));
  const cd = sstep(Math.min(Math.max((z-820.0)/110.0, 0.0), 1.0));
  h -= 12.0*cd;
  const r = Math.sqrt(x*x+(z+150.0)**2);
  const e = sstep(Math.min(Math.max((r-1120.0)/380.0, 0.0), 1.0));
  const ang = Math.atan2(z+150.0, x);
  h += e*(62.0+26.0*Math.sin(3.0*ang+1.2)+14.0*Math.sin(7.0*ang+0.4));
  return h;
}

export function terrainSlope(x, z, eps) {
  eps = eps || 1.2;
  const hx = terrainH(x+eps, z) - terrainH(x-eps, z);
  const hz = terrainH(x, z+eps) - terrainH(x, z-eps);
  return Math.hypot(hx, hz) / (2*eps);
}
