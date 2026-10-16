# -*- coding: utf-8 -*-
"""极速海岸 世界规格（单一事实来源）
用法（stdout 重定向落盘，本脚本不直接写文件）:
  python tools/worldspec.py            > assets/data/world-spec.json
  python tools/worldspec.py --heightjs > js/height.js
  python tools/worldspec.py --verify   # 用 node js/_verify.mjs 比对两份高度实现
游戏坐标：x 向东，z 向北，y 向上。地图 2600x2600。
"""
import json, math, subprocess, sys, os

def _sstep(t):
    return t*t*(3.0-2.0*t)

def terrain_h(x, z):
    ax = abs(x)
    az = abs(z)
    b1 = 20.0*math.sin(x*0.00155+1.3)*math.cos(z*0.00142+0.7)
    b2 = 10.0*math.sin(x*0.0041+0.5)*math.sin(z*0.0036+2.1)
    b3 = 3.2*math.sin(x*0.0105+2.0)*math.cos(z*0.0092+0.3)
    base = b1+b2+b3
    u = min(1.0, max((ax-600.0)/180.0, (az-620.0)/180.0, 0.0))
    m = u*u*(3.0-2.0*u)                                # 城市压平掩码(0城内 1野外,必须clamp到1)
    c = _sstep(min(max((z-480.0)/320.0, 0.0), 1.0))    # 海岸条带
    roll = 1.0-0.92*c
    micro = 0.5*math.sin(x*0.021+1.7)*math.cos(z*0.017+0.9)
    h = (base+micro)*m*roll
    # 西岬灯塔山
    h += 52.0*math.exp(-((x+980.0)**2+(z-560.0)**2)/(2.0*240.0**2))
    # 东湖洼地
    h -= 11.0*math.exp(-((x-1050.0)**2+(z-60.0)**2)/(2.0*150.0**2))
    # 南岭 / 东丘 点缀
    h += 22.0*math.exp(-((x+380.0)**2+(z+900.0)**2)/(2.0*280.0**2))
    h += 18.0*math.exp(-((x-880.0)**2+(z+700.0)**2)/(2.0*240.0**2))
    # 海滩下坡
    cd = _sstep(min(max((z-820.0)/110.0, 0.0), 1.0))
    h -= 12.0*cd
    # 边境山脉（天然围墙）
    r = math.sqrt(x*x+(z+150.0)**2)
    e = _sstep(min(max((r-1120.0)/380.0, 0.0), 1.0))
    ang = math.atan2(z+150.0, x)
    coast_gap = 1.0 - _sstep(min(max((z-460.0)/220.0, 0.0), 1.0))   # 海岸走廊让山退场
    h += e*coast_gap*(62.0+26.0*math.sin(3.0*ang+1.2)+14.0*math.sin(7.0*ang+0.4))
    return h

JS_H = r'''
export function terrainH(x, z) {
  const ax = Math.abs(x);
  const az = Math.abs(z);
  const b1 = 20.0*Math.sin(x*0.00155+1.3)*Math.cos(z*0.00142+0.7);
  const b2 = 10.0*Math.sin(x*0.0041+0.5)*Math.sin(z*0.0036+2.1);
  const b3 = 3.2*Math.sin(x*0.0105+2.0)*Math.cos(z*0.0092+0.3);
  const base = b1+b2+b3;
  const u = Math.min(1.0, Math.max((ax-600.0)/180.0, (az-620.0)/180.0, 0.0));
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
  const coastGap = 1.0 - sstep(Math.min(Math.max((z-460.0)/220.0, 0.0), 1.0));
  h += e*coastGap*(62.0+26.0*Math.sin(3.0*ang+1.2)+14.0*Math.sin(7.0*ang+0.4));
  return h;
}
'''

def R(id, type, w, pts):
    return dict(id=id, type=type, w=w, pts=pts)

HWY = [(-1300,700),(-1050,745),(-700,795),(-300,828),(100,822),(500,795),(900,758),(1300,700)]
VERT_XS = [-480,-320,-160,0,160,320,480]
HORZ_ZS = [-560,-400,-240,-80,80,240,400,560]

def build_roads():
    roads = [R('hwy','hw',17,HWY)]
    for x in VERT_XS:
        roads.append(R('st_v%d'%x,'st',13,[(x,-560),(x,820)]))
    for z in HORZ_ZS:
        roads.append(R('st_h%d'%z,'st',13,[(-560,z),(560,z)]))
    roads.append(R('climb','cn',9,[(-660,742),(-800,700),(-920,600),(-880,480),(-980,380),
                                    (-1100,440),(-1120,580),(-1030,640)]))
    roads.append(R('south','cn',10,[(-160,-560),(-300,-680),(-560,-760),(-860,-780),(-1080,-640),
                                     (-1150,-380),(-1060,-140),(-900,-60),(-680,-160),(-600,-360),(-480,-520)]))
    roads.append(R('east','cn',10,[(320,-560),(520,-700),(800,-780),(1060,-700),(1200,-440),
                                    (1230,-160),(1150,100),(980,300),(900,520),(800,680),(720,772)]))
    return roads

ROUTES = [
    dict(id='coast',  closed=False, speed=[12,17], pts=HWY),
    dict(id='citybg', closed=True,  speed=[8,12],  pts=[(-480,240),(480,240),(480,-80),(-480,-80)]),
    dict(id='dtown',  closed=True,  speed=[7,11],  pts=[(-160,80),(160,80),(160,-240),(-160,-240)]),
    dict(id='eastlp', closed=False, speed=[10,14], pts=[(320,-560),(520,-700),(800,-780),(1060,-700),(1200,-440),(1230,-160),(1150,100),(980,300),(900,520),(800,680),(720,772)]),
    dict(id='southlp',closed=False, speed=[9,13],  pts=[(-160,-560),(-300,-680),(-560,-760),(-860,-780),(-1080,-640),(-1150,-380),(-1060,-140),(-900,-60),(-680,-160),(-600,-360),(-480,-520)]),
]

SPEC = dict(
    size=2600, limit=1450,
    sun=dict(dir=[-0.45,0.78,-0.44], color=[1.0,0.97,0.9], intensity=3.1),
    fog=dict(color='#d8eaf7', near=420, far=1650),
    sea=dict(y=-3.2, color='#2a86c8'),
    spawn=dict(x=0, z=620, yaw=0),
    lighthouse=dict(x=-1040, z=600),
    lake=dict(x=1050, z=60, r=150, y=-2.6),
    roads=build_roads(),
    routes=ROUTES,
)

def verify():
    # 固定采样网格（两侧一致、无需随机数）
    pts = []
    for i in range(-13, 14):
        for j in range(-13, 14):
            pts.append((i*100 + (37 if i % 3 else -21), j*100 + (53 if j % 2 else -77)))
    pts += [(0,620),(-1040,600),(1050,60),(0,830),(1300,700),(720,772),(-980,380)]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run(['node', os.path.join('js', '_verify.mjs')],
                       capture_output=True, text=True, cwd=root)
    if r.returncode != 0:
        print('node 运行失败:', (r.stderr or '')[:800]); sys.exit(1)
    grid = json.loads(r.stdout)
    worst = 0.0; worstpt = None
    for (x, z) in pts:
        pv = terrain_h(x, z)
        jv = grid.get(str(x)+','+str(z))
        if jv is None:
            print('!! 缺采样点', x, z); sys.exit(1)
        d = abs(pv - jv)
        if d > worst: worst, worstpt = d, (x, z)
    print('采样 %d 点, 最大误差 %.3e @ %s' % (len(pts), worst, worstpt))
    if worst > 1e-9:
        print('!! 高度公式不一致'); sys.exit(1)
    print('高度公式 Python/JS 一致性 OK')

if __name__ == '__main__':
    if '--verify' in sys.argv:
        verify()
    elif '--heightjs' in sys.argv:
        js = ('// 由 tools/worldspec.py 自动生成——地形高度，勿手改\n'
              'function sstep(t){return t*t*(3-2*t);}\n' + JS_H +
              '\nexport function terrainSlope(x,z,eps){eps=eps||1.2;'
              'const hx=terrainH(x+eps,z)-terrainH(x-eps,z);'
              'const hz=terrainH(x,z+eps)-terrainH(x,z-eps);'
              'return Math.hypot(hx,hz)/(2*eps);}\n')
        sys.stdout.write(js)
    else:
        sys.stdout.write(json.dumps(SPEC, ensure_ascii=False))
