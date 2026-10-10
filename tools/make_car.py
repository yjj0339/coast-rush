# -*- coding: utf-8 -*-
"""Blender headless：英雄超跑 + 轿车 + 厢式货车 → assets/models/*.glb
坐标约定：脚本内用「游戏坐标」(x右, y上, z车头前)，写出时转 Blender(x, -z, y)
运行: blender -b -P tools/make_car.py
"""
import bpy, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEXDIR = os.path.join(ROOT, 'assets', 'textures')
OUTDIR = os.path.join(ROOT, 'assets', 'models')
os.makedirs(OUTDIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)

def C(x, y, z):
    return (x, -z, y)

def S(r, g, b):
    """sRGB 0-255 → 线性 0-1"""
    return ((r / 255.0) ** 2.2, (g / 255.0) ** 2.2, (b / 255.0) ** 2.2)

def mat(name, color, metallic=0.0, rough=0.5, coat=0.0, coatrough=0.08,
        emit=None, estr=0.0, alpha=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    ci = b.inputs.get('Coat Weight') or b.inputs.get('Clearcoat')
    if ci: ci.default_value = coat
    cri = b.inputs.get('Coat Roughness') or b.inputs.get('Clearcoat Roughness')
    if cri: cri.default_value = coatrough
    if emit is not None:
        ei = b.inputs.get('Emission Color') or b.inputs.get('Emission')
        if ei: ei.default_value = (*emit, 1)
        es = b.inputs.get('Emission Strength')
        if es: es.default_value = estr
    if alpha is not None:
        b.inputs['Alpha'].default_value = alpha
        m.blend_method = 'BLEND'
    return m

def imgmat(name, imgfile, rough=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Roughness'].default_value = rough
    tex = nt.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.load(os.path.join(TEXDIR, imgfile))
    img.pack()
    tex.image = img
    nt.links.new(tex.outputs['Color'], b.inputs['Base Color'])
    return m

M = {
    'CarPaint': mat('CarPaint', S(0, 176, 235), metallic=0.35, rough=0.30, coat=1.0, coatrough=0.05),
    'Canopy':   mat('Canopy',   S(10, 16, 24),   metallic=0.2, rough=0.06, alpha=0.62),
    'Trim':     mat('Trim',     S(14, 15, 18),   metallic=0.3, rough=0.55),
    'TrimDk':   mat('TrimDk',   S(8, 8, 10),     metallic=0.2, rough=0.7),
    'Chrome':   mat('Chrome',   S(228, 232, 238), metallic=1.0, rough=0.12),
    'Tire':     mat('Tire',     S(20, 20, 21),   rough=0.92),
    'Rim':      mat('Rim',      S(196, 202, 210), metallic=0.95, rough=0.18),
    'RimDk':    mat('RimDk',    S(60, 63, 68),   metallic=0.9, rough=0.3),
    'Disc':     mat('Disc',     S(120, 124, 130), metallic=0.85, rough=0.35),
    'Caliper':  mat('Caliper',  S(240, 180, 10), rough=0.35, coat=0.5),
    'Head':     mat('Head',     S(16, 18, 22),   rough=0.15, emit=S(210, 232, 255), estr=5),
    'DRL':      mat('DRL',      S(220, 235, 255), rough=0.2, emit=S(220, 238, 255), estr=7),
    'Tail':     mat('Tail',     S(40, 4, 4),     rough=0.2, emit=S(255, 36, 24), estr=3.5),
    'Interior': mat('Interior', S(24, 25, 28),   rough=0.75),
    'Seat':     mat('Seat',     S(38, 40, 46),   rough=0.8),
    'Screen':   mat('Screen',   S(6, 20, 24),    rough=0.2, emit=S(60, 220, 235), estr=2.5),
    'Plate':    imgmat('Plate', 'plate.png', rough=0.4),
    'SedPaint': mat('SedPaint', S(228, 230, 234), metallic=0.4, rough=0.32, coat=0.8),
    'SGlass':   mat('SGlass',   S(40, 52, 66),   metallic=0.3, rough=0.1),
    'VanPaint': mat('VanPaint', S(240, 244, 248), metallic=0.2, rough=0.4, coat=0.5),
    'VanAccent': mat('VanAccent', S(230, 130, 30), rough=0.5),
}

def assign(obj, m):
    obj.data.materials.append(m)

def rot_bl(rot):
    return (rot[0], -rot[2], rot[1])

def smooth_mesh(me, verts, faces):
    ns = [[0.0, 0.0, 0.0] for _ in verts]
    for f in faces:
        if len(f) < 3: continue
        a, b, c = [verts[f[i]] for i in range(3)]
        u = (b[0]-a[0], b[1]-a[1], b[2]-a[2])
        v = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        for vi in f:
            ns[vi][0] += n[0]; ns[vi][1] += n[1]; ns[vi][2] += n[2]
    flat = []
    for n in ns:
        l = math.sqrt(n[0]**2+n[1]**2+n[2]**2) or 1.0
        flat.append((n[0]/l, n[1]/l, n[2]/l))
    try:
        me.normals_split_custom_set_from_vertices(flat)
    except Exception:
        for p in me.polygons:
            p.use_smooth = True

def loft(name, sections, matl, radial=22, top_exp=0.9, bot_sq=0.45, side_exp=0.72, parent=None):
    """sections: [(z, w, yb, yt)] 游戏坐标放样"""
    verts, faces = [], []
    n = len(sections)
    for (z, w, yb, yt) in sections:
        ym = (yt + yb) / 2; ry = (yt - yb) / 2
        for k in range(radial):
            th = k / radial * math.tau
            c, s = math.cos(th), math.sin(th)
            px = w * (1 if c >= 0 else -1) * abs(c) ** side_exp
            py = ym + ry * (s ** top_exp if s >= 0 else bot_sq * s)
            verts.append(C(px, py, z))
    for i in range(n - 1):
        for k in range(radial):
            a = i * radial + k; b = i * radial + (k + 1) % radial
            c2 = (i + 1) * radial + k; d = (i + 1) * radial + (k + 1) % radial
            faces.append((a, c2, b)); faces.append((b, c2, d))
    for ring, flip in ((0, True), (n - 1, False)):
        z = sections[ring][0]
        yb, yt = sections[ring][2], sections[ring][3]
        ci = len(verts)
        verts.append(C(0, (yt + yb) / 2, z))
        for k in range(radial):
            a = ring * radial + k; b = ring * radial + (k + 1) % radial
            faces.append((ci, b, a) if flip else (ci, a, b))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.update()
    smooth_mesh(me, verts, faces)
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    assign(obj, matl)
    if parent: obj.parent = parent
    return obj

def box(name, dims, loc, matl, rot=(0, 0, 0), bevel=0.015, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=C(*loc), rotation=rot_bl(rot))
    o = bpy.context.active_object
    o.name = name
    o.scale = (dims[0], dims[2], dims[1])
    bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        be = o.modifiers.new('bev', 'BEVEL'); be.width = bevel; be.segments = 2
        bpy.context.view_layer.objects.active = o
        try: bpy.ops.object.modifier_apply(modifier='bev')
        except Exception: pass
    assign(o, matl)
    if parent: o.parent = parent
    return o

def cyl(name, r, depth, loc, matl, axis='x', parent=None, verts=16):
    rot = (0, math.pi / 2, 0) if axis == 'x' else (math.pi / 2, 0, 0) if axis == 'z' else (0, 0, 0)
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                        location=C(*loc), rotation=rot)
    o = bpy.context.active_object; o.name = name
    assign(o, matl)
    if parent: o.parent = parent
    return o

def torus(name, major, minor, loc, matl, parent=None, majseg=28, minseg=10):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
        major_segments=majseg, minor_segments=minseg, location=C(*loc), rotation=(0, math.pi / 2, 0))
    o = bpy.context.active_object; o.name = name
    assign(o, matl)
    if parent: o.parent = parent
    return o

def sphere(name, loc, scale, matl, parent=None, seg=20, ring=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=ring, radius=1.0, location=C(*loc))
    o = bpy.context.active_object; o.name = name
    o.scale = (scale[0], scale[2], scale[1])   # 游戏(x,y,z)→Blender(x,z,y)
    bpy.ops.object.transform_apply(scale=True)
    assign(o, matl)
    if parent: o.parent = parent
    return o

def empty(name, loc, parent=None):
    o = bpy.data.objects.new(name, None)
    o.location = C(*loc)
    bpy.context.collection.objects.link(o)
    if parent: o.parent = parent
    return o

def wheel(parent, tag, x, z, r_tire=0.34, w_tire=0.30, spokes=7, rimstyle='sport'):
    """pivot(转向) → spin(滚动) → 胎/辋/辐条/盘；卡钳静止在 pivot"""
    piv = empty('Wheel' + tag, (x, r_tire, z), parent)
    spin = empty('Spin' + tag, (0, 0, 0), piv)
    inset = 0.045
    torus('Tire' + tag, r_tire - 0.062, 0.098, (0, 0, 0), M['Tire'], spin, 30, 12)
    cyl('Tread' + tag, r_tire - 0.058, w_tire, (0, 0, 0), M['Tire'], axis='x', parent=spin, verts=30)
    cyl('Barrel' + tag, r_tire - 0.10, w_tire - 0.10, (-inset * 0, 0, 0), M['RimDk'], axis='x', parent=spin, verts=24)
    torus('Lip' + tag, r_tire - 0.10, 0.022, (w_tire / 2 - 0.035, 0, 0) if x >= 0 else (-(w_tire / 2 - 0.035), 0, 0),
          M['Rim'], spin, 28, 8)
    sx = (w_tire / 2 - 0.075) if x >= 0 else -(w_tire / 2 - 0.075)
    for i in range(spokes):
        ang = i / spokes * math.tau
        sp = box('Spoke' + tag, (0.045, r_tire * 1.75, 0.055), (sx, 0, 0), M['Rim'], bevel=0.008, parent=spin)
        sp.rotation_euler = (ang, 0, 0)
        if rimstyle == 'sport':
            sp2 = box('Spoke2' + tag, (0.035, r_tire * 1.6, 0.04), (sx * 1.25, 0, 0), M['RimDk'], bevel=0.006, parent=spin)
            sp2.rotation_euler = (ang + math.pi / spokes, 0, 0)
    cyl('Hub' + tag, 0.055, 0.05, (sx * 1.5, 0, 0), M['Chrome'], axis='x', parent=spin, verts=12)
    cyl('Disc' + tag, r_tire - 0.13, 0.045, (-0.02 if x >= 0 else 0.02, 0, 0), M['Disc'], axis='x', parent=piv, verts=20)
    box('Caliper' + tag, (0.07, 0.15, 0.10), (-0.02 if x >= 0 else 0.02, 0.055 * r_tire / 0.34, 0.115 * r_tire / 0.34),
        M['Caliper'], parent=piv)
    return piv

# ============================================================
#  英雄超跑 Cyro GT
# ============================================================
root = empty('Supercar', (0, 0, 0))

hull = loft('Hull', [
    ( 2.30, 0.34, 0.16, 0.30),
    ( 2.20, 0.66, 0.12, 0.38),
    ( 2.02, 0.88, 0.10, 0.47),
    ( 1.78, 0.99, 0.09, 0.55),
    ( 1.50, 1.03, 0.09, 0.62),
    ( 1.12, 0.98, 0.09, 0.67),
    ( 0.72, 0.95, 0.10, 0.71),
    ( 0.28, 0.94, 0.10, 0.73),
    (-0.22, 0.96, 0.10, 0.75),
    (-0.85, 1.01, 0.10, 0.78),
    (-1.45, 1.05, 0.11, 0.72),
    (-1.95, 0.97, 0.14, 0.66),
    (-2.20, 0.85, 0.20, 0.58),
    (-2.32, 0.68, 0.24, 0.50),
], M['CarPaint'], radial=26, parent=root)

canopy = loft('Canopy', [
    ( 0.98, 0.52, 0.60, 0.70),
    ( 0.62, 0.70, 0.62, 0.92),
    ( 0.16, 0.77, 0.65, 1.04),
    (-0.34, 0.76, 0.66, 1.03),
    (-0.95, 0.69, 0.67, 0.93),
    (-1.48, 0.54, 0.69, 0.79),
], M['Canopy'], radial=20, top_exp=0.75, parent=root)

# 轮拱爆宽（叶片状凸起嵌入侧围）
sphere('FlareFR', ( 0.99, 0.50, 1.50), (0.15, 0.20, 0.72), M['CarPaint'], root, 18, 10)
sphere('FlareFL', (-0.99, 0.50, 1.50), (0.15, 0.20, 0.72), M['CarPaint'], root, 18, 10)
sphere('FlareRR', ( 1.01, 0.52, -1.42), (0.17, 0.22, 0.78), M['CarPaint'], root, 18, 10)
sphere('FlareRL', (-1.01, 0.52, -1.42), (0.17, 0.22, 0.78), M['CarPaint'], root, 18, 10)

# 前脸
box('Splitter', (1.72, 0.045, 0.42), (0, 0.085, 2.16), M['TrimDk'], bevel=0.008, parent=root)
box('Grille', (0.98, 0.16, 0.08), (0, 0.26, 2.27), M['TrimDk'], bevel=0, parent=root)
for sx in (0.34, -0.34):
    box('IntakeF', (0.26, 0.10, 0.10), (sx, 0.22, 2.24), M['TrimDk'], bevel=0, parent=root)
for sx in (0.86, -0.86):   # 犬牙风刀
    box('Canard', (0.20, 0.02, 0.24), (sx, 0.20, 2.12), M['Trim'], rot=(0.18, 0, 0.1), bevel=0, parent=root)
box('Badge', (0.09, 0.09, 0.02), (0, 0.44, 2.315), M['Chrome'], bevel=0, parent=root)

# 大灯总成（暗盒 + 透镜 + DRL）
for sx, sgn in ((0.60, 1), (-0.60, -1)):
    box('HeadHouse', (0.40, 0.10, 0.30), (sx, 0.545, 2.02), M['TrimDk'], rot=(0, -0.30 * sgn, -0.12 * sgn), bevel=0.01, parent=root)
    box('HeadLens', (0.30, 0.06, 0.20), (sx, 0.575, 2.07), M['Head'], rot=(0, -0.30 * sgn, -0.12 * sgn), bevel=0.01, parent=root)
    box('DRLa', (0.34, 0.025, 0.045), (sx, 0.47, 2.16), M['DRL'], rot=(0, -0.25 * sgn, -0.05 * sgn), bevel=0, parent=root)
    box('DRLb', (0.045, 0.025, 0.20), (sx + 0.17 * sgn, 0.505, 2.02), M['DRL'], rot=(0, 0, 0), bevel=0, parent=root)

# 侧裙 / 侧进气 / 尾部扩散
for sx in (0.99, -0.99):
    box('Skirt', (0.09, 0.10, 1.55), (sx, 0.115, -0.28), M['TrimDk'], bevel=0.01, parent=root)
    box('SideIntake', (0.10, 0.30, 0.55), (sx * 0.965, 0.46, -1.02), M['TrimDk'], rot=(0, 0, 0.06), bevel=0.01, parent=root)
    box('FenderVent', (0.06, 0.05, 0.30), (sx * 0.985, 0.665, 0.78), M['TrimDk'], rot=(0, 0, -0.25 * (1 if sx > 0 else -1)), bevel=0, parent=root)
box('Diffuser', (1.42, 0.17, 0.36), (0, 0.20, -2.16), M['TrimDk'], bevel=0.01, parent=root)
for i in (-1.5, -0.5, 0.5, 1.5):
    box('Fin', (0.025, 0.14, 0.32), (i * 0.31, 0.20, -2.18), M['Trim'], bevel=0, parent=root)
for sx in (0.30, 0.46, -0.30, -0.46):   # 四出排气
    cyl('Exh', 0.052, 0.16, (sx, 0.315, -2.30), M['Chrome'], axis='z', parent=root, verts=14)
    cyl('ExhIn', 0.038, 0.17, (sx, 0.315, -2.305), M['TrimDk'], axis='z', parent=root, verts=12)

# 尾灯贯穿带 + 下雾灯
box('TailBar', (1.50, 0.055, 0.045), (0, 0.60, -2.315), M['Tail'], bevel=0, parent=root)
box('TailLo', (1.20, 0.035, 0.035), (0, 0.42, -2.30), M['Tail'], bevel=0, parent=root)
box('PlateR', (0.36, 0.10, 0.025), (0, 0.50, -2.33), M['Plate'], bevel=0, parent=root)
box('PlateF', (0.36, 0.10, 0.025), (0, 0.335, 2.315), M['Plate'], bevel=0, parent=root)

# 主动尾翼（天鹅颈）
box('Wing', (1.52, 0.04, 0.34), (0, 1.055, -2.00), M['CarPaint'], rot=(-0.11, 0, 0), bevel=0.012, parent=root)
box('WingGurney', (1.52, 0.05, 0.025), (0, 1.075, -2.14), M['TrimDk'], bevel=0, parent=root)
for sx in (0.45, -0.45):
    box('WingNeck', (0.05, 0.30, 0.05), (sx, 0.905, -1.94), M['TrimDk'], rot=(0.5, 0, 0), bevel=0.006, parent=root)
box('WingBrake', (0.5, 0.02, 0.02), (0, 1.078, -1.87), M['Tail'], bevel=0, parent=root)

# 后视镜
for sx, sgn in ((1.0, 1), (-1.0, -1)):
    box('MirStalk', (0.14, 0.035, 0.05), (sx * 1.0, 0.80, 0.62), M['TrimDk'], rot=(0, 0, 0.5 * sgn), bevel=0, parent=root)
    box('Mirror', (0.17, 0.10, 0.075), (sx * 1.10, 0.825, 0.58), M['CarPaint'], bevel=0.02, parent=root)

# 引擎盖百叶 + 机窗
for i in range(6):
    box('Louver', (0.72, 0.012, 0.09), (0, 0.775 - i * 0.004, -1.02 - i * 0.13), M['TrimDk'], rot=(-0.35, 0, 0), bevel=0, parent=root)
box('EngGlass', (0.55, 0.02, 0.42), (0, 0.77, -0.62), M['Canopy'], rot=(0.1, 0, 0), bevel=0, parent=root)

# 内饰（透过座舱玻璃可见）
box('CockpitTub', (1.30, 0.35, 1.70), (0, 0.52, -0.35), M['Interior'], bevel=0.02, parent=root)
for sx in (0.36, -0.36):
    box('SeatBase', (0.44, 0.14, 0.48), (sx, 0.56, -0.42), M['Seat'], bevel=0.03, parent=root)
    box('SeatBack', (0.44, 0.55, 0.13), (sx, 0.78, -0.66), M['Seat'], rot=(-0.16, 0, 0), bevel=0.03, parent=root)
box('Dash', (1.26, 0.13, 0.34), (0, 0.665, 0.44), M['Interior'], bevel=0.02, parent=root)
box('Screen', (0.40, 0.025, 0.22), (0, 0.735, 0.40), M['Screen'], rot=(-0.35, 0, 0), bevel=0, parent=root)
steer = torus('SteerRim', 0.155, 0.028, (-0.36, 0.70, 0.18), M['Interior'], majseg=22, minseg=8)
steer.rotation_euler = (math.radians(68), 0, 0)
box('Console', (0.22, 0.16, 0.60), (0, 0.60, -0.05), M['Interior'], bevel=0.02, parent=root)
box('IFloor', (1.55, 0.05, 4.30), (0, 0.078, 0), M['TrimDk'], bevel=0, parent=root)

wheel(root, 'FL',  0.90,  1.50, r_tire=0.37, w_tire=0.32)
wheel(root, 'FR', -0.90,  1.50, r_tire=0.37, w_tire=0.32)
wheel(root, 'RL',  0.92, -1.42, r_tire=0.39, w_tire=0.36)
wheel(root, 'RR', -0.92, -1.42, r_tire=0.39, w_tire=0.36)

# ============================================================
#  街车·轿车 Sedan
# ============================================================
sroot = empty('Sedan', (0, 0, 0))
loft('SedHull', [
    ( 2.10, 0.74, 0.24, 0.52),
    ( 1.75, 0.86, 0.16, 0.66),
    ( 0.90, 0.90, 0.14, 0.78),
    ( 0.00, 0.90, 0.14, 0.80),
    (-1.10, 0.90, 0.15, 0.78),
    (-1.95, 0.84, 0.20, 0.66),
    (-2.25, 0.72, 0.26, 0.58),
], M['SedPaint'], radial=16, parent=sroot)
loft('SedGlass', [
    ( 0.92, 0.60, 0.70, 0.80),
    ( 0.45, 0.72, 0.76, 1.12),
    (-0.35, 0.72, 0.76, 1.14),
    (-1.05, 0.62, 0.76, 0.86),
], M['SGlass'], radial=14, top_exp=0.8, parent=sroot)
for sx in (0.52, -0.52):
    box('SedHead', (0.34, 0.09, 0.08), (sx, 0.56, 2.10), M['Head'], bevel=0.01, parent=sroot)
    box('SedTail', (0.36, 0.09, 0.06), (sx, 0.60, -2.24), M['Tail'], bevel=0.01, parent=sroot)
box('SedGrille', (0.72, 0.14, 0.06), (0, 0.36, 2.16), M['TrimDk'], bevel=0, parent=sroot)
box('SedPlate', (0.34, 0.10, 0.02), (0, 0.32, 2.19), M['Plate'], bevel=0, parent=sroot)
for sx in (0.86, -0.86):
    box('SedSkirt', (0.07, 0.08, 2.0), (sx, 0.14, -0.1), M['TrimDk'], bevel=0, parent=sroot)
for i, (x, z) in enumerate(((0.80, 1.35), (-0.80, 1.35), (0.80, -1.40), (-0.80, -1.40))):
    piv = empty('SWheel%d' % i, (x, 0.33, z), sroot)
    spin = empty('SSpin%d' % i, (0, 0, 0), piv)
    cyl('STire%d' % i, 0.33, 0.22, (0, 0, 0), M['Tire'], axis='x', parent=spin, verts=18)
    cyl('SRim%d' % i, 0.20, 0.23, (0, 0, 0), M['Rim'], axis='x', parent=spin, verts=14)
    for k in range(4):
        sp = box('SSpoke%d' % i, (0.04, 0.56, 0.045), (0.11 if x >= 0 else -0.11, 0, 0), M['RimDk'], bevel=0, parent=spin)
        sp.rotation_euler = (k / 4 * math.tau + 0.4, 0, 0)

# ============================================================
#  街车·厢式货车 Van
# ============================================================
vroot = empty('Van', (0, 0, 0))
loft('VanHull', [
    ( 2.35, 0.86, 0.30, 0.85),
    ( 2.05, 0.98, 0.24, 1.35),
    ( 1.35, 1.02, 0.22, 1.85),
    ( 0.20, 1.02, 0.22, 1.92),
    (-1.60, 1.02, 0.24, 1.92),
    (-2.55, 0.98, 0.30, 1.86),
    (-2.95, 0.88, 0.36, 1.70),
], M['VanPaint'], radial=16, top_exp=0.95, bot_sq=0.8, side_exp=0.5, parent=vroot)
loft('VanGlass', [
    ( 1.55, 0.80, 0.95, 1.78),
    ( 0.90, 0.86, 0.95, 1.84),
], M['SGlass'], radial=14, top_exp=0.9, bot_sq=0.8, parent=vroot)
box('VanStripe', (2.05, 0.30, 0.06), (0, 0.95, -0.6), M['VanAccent'], bevel=0, parent=vroot)
for sx in (0.58, -0.58):
    box('VanHead', (0.30, 0.12, 0.08), (sx, 0.62, 2.34), M['Head'], bevel=0.01, parent=vroot)
    box('VanTail', (0.26, 0.30, 0.06), (sx, 1.05, -2.93), M['Tail'], bevel=0.01, parent=vroot)
box('VanGrille', (0.9, 0.2, 0.06), (0, 0.55, 2.36), M['TrimDk'], bevel=0, parent=vroot)
for i, (x, z) in enumerate(((0.86, 1.55), (-0.86, 1.55), (0.86, -1.85), (-0.86, -1.85))):
    cyl('VTire%d' % i, 0.40, 0.26, (x, 0.40, z), M['Tire'], axis='x', parent=vroot, verts=16)
    cyl('VRim%d' % i, 0.24, 0.27, (x, 0.40, z), M['Rim'], axis='x', parent=vroot, verts=12)

# ============================================================
#  导出
# ============================================================
def export_sel(rootlist, path):
    bpy.ops.object.select_all(action='DESELECT')
    def sel(o):
        o.select_set(True)
        for ch in o.children: sel(ch)
    for r in rootlist: sel(r)
    kw = dict(filepath=path, export_format='GLB', export_apply=True,
              export_yup=True, export_animations=False, export_skins=False,
              export_morph=False, export_cameras=False, export_lights=False)
    try:
        bpy.ops.export_scene.gltf(use_selection=True, **kw)
    except TypeError:
        bpy.ops.export_scene.gltf(**kw)
    print('EXPORTED', path, os.path.getsize(path) // 1024, 'KB')

export_sel([root], os.path.join(OUTDIR, 'car.glb'))
export_sel([sroot], os.path.join(OUTDIR, 'sedan.glb'))
export_sel([vroot], os.path.join(OUTDIR, 'van.glb'))
print('DONE')
