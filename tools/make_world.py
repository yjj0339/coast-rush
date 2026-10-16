# -*- coding: utf-8 -*-
"""Blender headless：开放世界地形/路网/城市/植被/道具 → assets/models/world.glb
并往 stdout 打印 @@COLLIDERS@@ ... @@END@@ JSON（碰撞体/护栏/POI）
运行: blender -b -P tools/make_world.py
"""
import bpy, math, os, sys, json, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEXDIR = os.path.join(ROOT, 'assets', 'textures')
OUTDIR = os.path.join(ROOT, 'assets', 'models')
sys.path.insert(0, HERE)
import worldspec as WS

terrain_h = WS.terrain_h
SPEC = WS.SPEC
rng = random.Random(2026)

bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------------- 基础工具 ----------------
def C(x, y, z): return (x, -z, y)
def S(r, g, b): return ((r/255.0)**2.2, (g/255.0)**2.2, (b/255.0)**2.2)

def mat(name, color, metallic=0.0, rough=0.6, emit=None, estr=0.0, doubleside=False, alpha=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    if emit is not None:
        ei = b.inputs.get('Emission Color') or b.inputs.get('Emission')
        if ei: ei.default_value = (*emit, 1)
        es = b.inputs.get('Emission Strength')
        if es: es.default_value = estr
    if alpha is not None:
        b.inputs['Alpha'].default_value = alpha
        m.blend_method = 'BLEND'
    if doubleside:
        m.use_backface_culling = False
    return m

def imgmat(name, imgfile, rough=0.7, factor=None, doubleside=False, metallic=0.0, vcol=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metallic
    if factor:
        b.inputs['Base Color'].default_value = (*factor, 1)
    tex = nt.nodes.new('ShaderNodeTexImage')
    img = bpy.data.images.load(os.path.join(TEXDIR, imgfile))
    img.pack()
    tex.image = img
    out_sock = tex.outputs['Color']
    if vcol:
        vc = nt.nodes.new('ShaderNodeVertexColor')
        vc.layer_name = 'col'
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        # 5.x 的 Mix 节点同名插槽多套，按索引取 Color 那组: in6=A in7=B out2=Result
        mix.inputs['Factor'].default_value = 1.0
        nt.links.new(tex.outputs['Color'], mix.inputs[6])
        nt.links.new(vc.outputs['Color'], mix.inputs[7])
        out_sock = mix.outputs[2]
    nt.links.new(out_sock, b.inputs['Base Color'])
    if doubleside: m.use_backface_culling = False
    return m

MT = {
    'Terrain':  imgmat('Terrain', 'grass.png', rough=0.9, vcol=True),
    'Beach':    imgmat('Beach', 'sand.png', rough=0.95),
    'Asphalt':  imgmat('Asphalt', 'asphalt.png', rough=0.85),
    'Sidewalk': imgmat('Sidewalk', 'sidewalk.png', rough=0.8),
    'FacGlass': imgmat('FacGlass', 'fac_glass.png', rough=0.35, metallic=0.15),
    'FacRes':   imgmat('FacRes', 'fac_res.png', rough=0.7),
    'FacShop':  imgmat('FacShop', 'fac_shop.png', rough=0.6),
    'Bark':     imgmat('Bark', 'bark.png', rough=0.9),
    'Billboard':imgmat('Billboard', 'billboard.png', rough=0.5, doubleside=True),
    'MarkW':    mat('MarkW', S(235, 235, 232), rough=0.7),
    'MarkY':    mat('MarkY', S(230, 185, 40), rough=0.7),
    'Curb':     mat('Curb', S(176, 178, 182), rough=0.8),
    'Roof':     mat('Roof', S(120, 122, 126), rough=0.85),
    'RoofDk':   mat('RoofDk', S(88, 90, 94), rough=0.85),
    'TrimDk':   mat('TrimDk', S(30, 31, 34), rough=0.7),
    'Pole':     mat('Pole', S(70, 74, 80), metallic=0.6, rough=0.5),
    'Rail':     mat('Rail', S(168, 174, 182), metallic=0.7, rough=0.45),
    'TrunkPalm': mat('TrunkPalm', S(112, 88, 62), rough=0.9),
    'Frond':    mat('Frond', S(52, 128, 58), rough=0.8, doubleside=True),
    'Pine':     mat('Pine', S(38, 96, 52), rough=0.85),
    'Rock':     mat('Rock', S(128, 126, 120), rough=0.95),
    'Mount':    mat('Mount', S(96, 122, 96), rough=1.0),
    'LhWhite':  mat('LhWhite', S(238, 236, 230), rough=0.6),
    'LhRed':    mat('LhRed', S(200, 40, 34), rough=0.6),
    'Lantern':  mat('Lantern', S(255, 244, 200), rough=0.3, emit=S(255, 240, 190), estr=4),
    'Umbrella1': mat('Umbrella1', S(226, 76, 60), rough=0.7, doubleside=True),
    'Umbrella2': mat('Umbrella2', S(60, 130, 200), rough=0.7, doubleside=True),
    'Sail':     mat('Sail', S(242, 244, 248), rough=0.7, doubleside=True),
    'Boat':     mat('Boat', S(236, 240, 244), rough=0.4, metallic=0.1),
    'Lawn':     imgmat('Lawn', 'grass.png', rough=0.9, factor=(0.72, 0.88, 0.66)),
    'Fountain': mat('Fountain', S(180, 216, 232), rough=0.15, metallic=0.1),
    'Bench':    mat('Bench', S(142, 100, 66), rough=0.8),
    'TreeBlob': mat('TreeBlob', S(70, 140, 62), rough=0.9),
    'Green':    mat('Green', S(46, 110, 60), rough=0.8),
}

def smooth_normals(verts, faces):
    ns = [[0.0, 0.0, 0.0] for _ in verts]
    for f in faces:
        if len(f) < 3: continue
        a, b, c = [verts[f[i]] for i in range(3)]
        u = (b[0]-a[0], b[1]-a[1], b[2]-a[2])
        v = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        for vi in f:
            ns[vi][0] += n[0]; ns[vi][1] += n[1]; ns[vi][2] += n[2]
    out = []
    for n in ns:
        l = math.sqrt(n[0]**2+n[1]**2+n[2]**2) or 1.0
        out.append((n[0]/l, n[1]/l, n[2]/l))
    return out

GROUPS = {}   # name -> [obj]
def put(obj, group):
    GROUPS.setdefault(group, []).append(obj)
    return obj

def mesh_obj(name, verts, faces, matl, uvs=None, cols=None, group=None, normals=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.update()
    if uvs:
        uvl = me.uv_layers.new(name='UVMap')
        for i, uv in enumerate(uvs):
            if i < len(uvl.data): uvl.data[i].uv = uv
    if cols:
        ca = me.color_attributes.new(name='col', type='FLOAT_COLOR', domain='CORNER')
        for i, f in enumerate(faces):
            for k, vi in enumerate(f):
                ca.data[i*3+k].color = (*cols[vi], 1.0) if len(f) == 3 else (*cols[vi], 1.0)
    if normals is None and len(faces) < 60000:
        try: me.normals_split_custom_set_from_vertices(smooth_normals(verts, faces))
        except Exception: pass
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(matl)
    if group: put(obj, group)
    return obj

def box(name, dims, loc, matl, rot=(0, 0, 0), group=None, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=C(*loc), rotation=rot_bl(rot))
    o = bpy.context.active_object; o.name = name
    o.scale = (dims[0], dims[2], dims[1])
    bpy.ops.object.transform_apply(scale=True)
    if bevel > 0:
        be = o.modifiers.new('bev', 'BEVEL'); be.width = bevel; be.segments = 2
        bpy.context.view_layer.objects.active = o
        try: bpy.ops.object.modifier_apply(modifier='bev')
        except Exception: pass
    o.data.materials.append(matl)
    if group: put(o, group)
    return o

def rot_bl(rot): return (rot[0], -rot[2], rot[1])

# ---- 缓存图元（bmesh 一次生成，实例共享网格；材质按(图元,材质)缓存） ----
_PRIM_CACHE = {}

def _prim_mesh(kind, matl):
    key = (kind, matl.name)
    if key in _PRIM_CACHE:
        return _PRIM_CACHE[key]
    import bmesh
    bm = bmesh.new()
    if kind == 'box':
        bmesh.ops.create_cube(bm, size=1.0)
    elif kind == 'cyl':
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=12, radius1=1.0, radius2=1.0, depth=1.0)
    elif kind == 'cone':
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=10, radius1=1.0, radius2=0.001, depth=1.0)
    elif kind == 'sphere':
        bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=1.0)
    me = bpy.data.meshes.new('prim_' + kind + '_' + matl.name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(matl)
    _PRIM_CACHE[key] = me
    return me

def box(name, dims, loc, matl, rot=(0, 0, 0), group=None, bevel=0):
    o = bpy.data.objects.new(name, _prim_mesh('box', matl))
    o.location = C(*loc)
    o.rotation_euler = rot_bl(rot)
    o.scale = (dims[0], dims[2], dims[1])
    bpy.context.collection.objects.link(o)
    if group: put(o, group)
    return o

def cyl(name, r, depth, loc, matl, axis='y', group=None, verts=12):
    o = bpy.data.objects.new(name, _prim_mesh('cyl', matl))
    o.location = C(*loc)
    if axis == 'x':
        o.rotation_euler = (0, math.pi / 2, 0)
        o.scale = (r, r, depth)
    elif axis == 'z':
        o.rotation_euler = (math.pi / 2, 0, 0)
        o.scale = (r, depth, r)
    else:
        o.scale = (r, r, depth)
    bpy.context.collection.objects.link(o)
    if group: put(o, group)
    return o

def cone(name, r, depth, loc, matl, group=None, verts=10):
    o = bpy.data.objects.new(name, _prim_mesh('cone', matl))
    o.location = C(*loc)
    o.scale = (r, r, depth)
    bpy.context.collection.objects.link(o)
    if group: put(o, group)
    return o

def sphere(name, loc, scale, matl, group=None, seg=14, ring=8):
    o = bpy.data.objects.new(name, _prim_mesh('sphere', matl))
    o.location = C(*loc)
    o.scale = (scale[0], scale[2], scale[1])
    bpy.context.collection.objects.link(o)
    if group: put(o, group)
    return o

# ---------------- 采样/几何生成 ----------------
def catmull(pts, step=3.0, closed=False):
    """Catmull-Rom 采样为折线（游戏坐标 x,z）"""
    P = list(pts)
    if closed: P = P + [P[0]]
    n = len(P)
    out = []
    def pt(i):
        if closed: return P[i % (n-1)]
        return P[max(0, min(n-1, i))]
    for i in range(n-1):
        p0, p1, p2, p3 = pt(i-1), pt(i), pt(i+1), pt(i+2)
        seg = math.hypot(p1[0]-p2[0], p1[1]-p2[1])
        k = max(2, int(seg/step))
        for j in range(k):
            t = j/k
            t2, t3 = t*t, t*t*t
            x = 0.5*((2*p1[0]) + (-p0[0]+p2[0])*t + (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2 + (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            z = 0.5*((2*p1[1]) + (-p0[1]+p2[1])*t + (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2 + (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            out.append((x, z))
    out.append(P[-1] if not closed else P[0])
    return out

def ribbon(center, width, y_off, matl, group, uv_tile=7.0, name='ribbon'):
    """沿中心线建路面带。center: [(x,z)]"""
    verts, faces, uvs = [], [], []
    L = 0.0
    for i, (x, z) in enumerate(center):
        if i == 0:
            dx, dz = center[1][0]-x, center[1][1]-z
        else:
            dx, dz = x-center[i-1][0], z-center[i-1][1]
        l = math.hypot(dx, dz) or 1.0
        nx, nz = -dz/l, dx/l
        hw = width/2
        y0 = terrain_h(x-nx*hw, z-nz*hw)
        y1 = terrain_h(x+nx*hw, z+nz*hw)
        yy = max(y0, y1) + y_off
        if i > 0: L += math.hypot(dx, dz)
        verts.append(C(x-nx*hw, yy, z-nz*hw))
        verts.append(C(x+nx*hw, yy, z+nz*hw))
        uvs += [(0, L/uv_tile), (1, L/uv_tile)]
        if i > 0:
            a = (i-1)*2
            faces.append((a, a+1, a+2)); faces.append((a+1, a+3, a+2))
    return mesh_obj(name, verts, faces, matl, uvs=uvs, group=group, normals=[(0, 1, 0)]*len(verts))

def solid_strip(center, width, h, y_off, matl, group, name='strip'):
    """凸起条带（人行道/路缘）：顶面+侧壁"""
    verts, faces, uvs = [], [], []
    L = 0.0
    for i, (x, z) in enumerate(center):
        if i == 0: dx, dz = center[1][0]-x, center[1][1]-z
        else: dx, dz = x-center[i-1][0], z-center[i-1][1]
        l = math.hypot(dx, dz) or 1.0
        nx, nz = -dz/l, dx/l
        tx, tz = dx/l, dz/l
        hw = width/2
        yb = terrain_h(x, z) + y_off
        yt = yb + h
        if i > 0: L += l
        base = len(verts)
        # 4 顶点: 左下 右下 左上 右上
        verts.append(C(x-nx*hw, yb, z-nz*hw))
        verts.append(C(x+nx*hw, yb, z+nz*hw))
        verts.append(C(x-nx*hw, yt, z-nz*hw))
        verts.append(C(x+nx*hw, yt, z+nz*hw))
        u = L/3.0
        uvs += [(0, u), (1, u), (0, u), (1, u)]
        if i > 0:
            p = base-4
            faces.append((p, p+4, p+1)); faces.append((p+1, p+4, p+5))          # 顶
            faces.append((p, p+2, p+4)); faces.append((p+2, p+6, p+4))          # 左壁
            faces.append((p+1, p+5, p+3)); faces.append((p+3, p+5, p+7))        # 右壁
    # 两端封口
    if len(center) >= 2:
        for e in (0, -1):
            x, z = center[e]
            i = 1 if e == 0 else len(center)-2
            dx, dz = center[i][0]-x, center[i][1]-z
            l = math.hypot(dx, dz) or 1.0
            nx, nz = -dz/l, dx/l
            hw = width/2
            yb = terrain_h(x, z)+y_off; yt = yb+h
            b = len(verts)
            verts.append(C(x-nx*hw, yb, z-nz*hw)); verts.append(C(x+nx*hw, yb, z+nz*hw))
            verts.append(C(x-nx*hw, yt, z-nz*hw)); verts.append(C(x+nx*hw, yt, z+nz*hw))
            if e == 0: faces.append((b, b+1, b+2)); faces.append((b+1, b+3, b+2))
            else: faces.append((b, b+2, b+1)); faces.append((b+1, b+2, b+3))
    return mesh_obj(name, verts, faces, matl, uvs=uvs, group=group)

def line_marks(center, offset_lat, width, dash, gap, y_off, matl, group, name='marks'):
    """沿中心线的虚线标线（offset_lat: 横向偏移，右正）"""
    verts, faces, uvs = [], [], []
    L = 0.0
    segs = []
    on = True; seg_start = 0
    i = 0
    while i < len(center)-1:
        x, z = center[i]
        if i == 0: dx, dz = center[1][0]-x, center[1][1]-z
        else: dx, dz = x-center[i-1][0], z-center[i-1][1]
        l = math.hypot(dx, dz) or 1.0
        L += l
        phase = L % (dash+gap)
        if on and phase > dash:
            on = False; segs.append((seg_start, i)); 
        elif not on and phase <= dash:
            on = True; seg_start = i
        i += 1
    if on: segs.append((seg_start, len(center)-1))
    for (a, b) in segs:
        if b-a < 1: continue
        base = len(verts)
        for i in range(a, b+1):
            x, z = center[i]
            if i == 0: dx, dz = center[1][0]-x, center[1][1]-z
            else: dx, dz = x-center[i-1][0], z-center[i-1][1]
            l = math.hypot(dx, dz) or 1.0
            nx, nz = -dz/l, dx/l
            ox, oz = nx*offset_lat, nz*offset_lat
            hw = width/2
            yy = terrain_h(x+ox, z+oz) + y_off
            verts.append(C(x+ox-nx*hw, yy, z+oz-nz*hw))
            verts.append(C(x+ox+nx*hw, yy, z+oz+nz*hw))
        for i in range((b-a)):
            p = base+i*2
            faces.append((p, p+1, p+2)); faces.append((p+1, p+3, p+2))
    return mesh_obj(name, verts, faces, matl, group=group, normals=[(0, 1, 0)]*len(verts))

def solid_line(center, offset_lat, width, y_off, matl, group, name='sline'):
    return line_marks(center, offset_lat, width, 1e9, 0, y_off, matl, group, name)

# ============================================================
#  1. 地形
# ============================================================
N = 200
EXT = 1300.0
step = 2*EXT/N
tverts, tfaces, tuvs, tcols = [], [], [], []
for j in range(N+1):
    for i in range(N+1):
        x = -EXT + i*step; z = -EXT + j*step
        tverts.append(C(x, terrain_h(x, z), z))
        tuvs.append((x/8.0, z/8.0))
        # 顶点色：坡度大→岩石灰；轻微随机变化
        e = 3.0
        gx = (terrain_h(x+e, z)-terrain_h(x-e, z))/(2*e)
        gz = (terrain_h(x, z+e)-terrain_h(x, z-e))/(2*e)
        slope = math.hypot(gx, gz)
        rk = max(0.0, min(1.0, (slope-0.30)/0.42))
        v = 1.0 + rng.uniform(-0.045, 0.045)
        base = (0.98*v, 1.0*v, 0.95*v)
        rock = (0.56, 0.55, 0.53)
        tcols.append(tuple(bk + (rk*(crg-bk)) for bk, crg in zip(base, rock)))
for j in range(N):
    for i in range(N):
        a = j*(N+1)+i
        tfaces.append((a, a+N+1, a+1)); tfaces.append((a+1, a+N+1, a+N+2))
mesh_obj('Terrain', tverts, tfaces, MT['Terrain'], uvs=tuvs, cols=tcols, group='Terrain')
print('terrain ok', len(tverts), 'verts')

# ============================================================
#  2. 路网
# ============================================================
city_x0, city_x1, city_z0, city_z1 = -600, 600, -620, 640
VERT_XS = [-480, -320, -160, 0, 160, 320, 480]
HORZ_ZS = [-560, -400, -240, -80, 80, 240, 400, 560]
ST_W = 13.0

road_samples = []   # 全部路面点，供植被避让
center_cache = {}

def get_center(road):
    key = road['id']
    if key not in center_cache:
        center_cache[key] = catmull(road['pts'], 3.0)
    return center_cache[key]

for road in SPEC['roads']:
    ctr = get_center(road)
    road_samples += ctr[::2]
    w = road['w']
    if road['type'] == 'hw':
        ribbon(ctr, w, 0.06, MT['Asphalt'], 'RoadHW', name='hw_'+road['id'])
        solid_line(ctr, -0.30, 0.13, 0.115, MT['MarkY'], 'MarkY')
        solid_line(ctr, 0.30, 0.13, 0.115, MT['MarkY'], 'MarkY')
        solid_line(ctr, w/2-0.55, 0.15, 0.115, MT['MarkW'], 'MarkW')
        solid_line(ctr, -(w/2-0.55), 0.15, 0.115, MT['MarkW'], 'MarkW')
    elif road['type'] == 'st':
        ribbon(ctr, w, 0.05, MT['Asphalt'], 'RoadST', name='st_'+road['id'])
        in_city = [(x, z) for (x, z) in ctr if city_x0-40 < x < city_x1+40 and city_z0-40 < z < city_z1+40]
        if len(in_city) > 4:
            line_marks(in_city, 0, 0.22, 3.2, 4.8, 0.10, MT['MarkW'], 'MarkW')
    else:
        ribbon(ctr, w, 0.055, MT['Asphalt'], 'RoadCN', name='cn_'+road['id'])
        line_marks(ctr, 0, 0.2, 2.6, 5.5, 0.105, MT['MarkW'], 'MarkW')

# 人行道 + 路缘（仅城区）
def between_intersections(a, b, crossings, roadhalf, extra):
    """在 a..b 区间按交叉路口切分段"""
    cs = sorted(c for c in crossings if a+roadhalf+extra < c < b-roadhalf-extra)
    spans = []
    cur = a + roadhalf + extra
    for c in cs:
        spans.append((cur, c - roadhalf - extra))
        cur = c + roadhalf + extra
    spans.append((cur, b - roadhalf - extra))
    return spans

for x in VERT_XS:
    for (z0, z1) in between_intersections(-560, 640, HORZ_ZS, ST_W/2, 1.6):
        if z1-z0 < 8: continue
        for sx in (-1, 1):
            cx = x + sx*(ST_W/2 + 1.8)
            seg = [(cx, z0 + (z1-z0)*t/16) for t in range(17)]
            solid_strip(seg, 3.2, 0.14, 0.05, MT['Sidewalk'], 'Sidewalk', 'sw')
            curb = [(x + sx*(ST_W/2+0.14), z0 + (z1-z0)*t/16) for t in range(17)]
            solid_strip(curb, 0.30, 0.16, 0.05, MT['Curb'], 'Curb', 'cb')
for z in HORZ_ZS:
    for (x0, x1) in between_intersections(-560, 560, VERT_XS, ST_W/2, 1.6):
        if x1-x0 < 8: continue
        for sz in (-1, 1):
            cz = z + sz*(ST_W/2 + 1.8)
            seg = [(x0 + (x1-x0)*t/16, cz) for t in range(17)]
            solid_strip(seg, 3.2, 0.14, 0.05, MT['Sidewalk'], 'Sidewalk', 'sw')
            curb = [(x0 + (x1-x0)*t/16, z + sz*(ST_W/2+0.14)) for t in range(17)]
            solid_strip(curb, 0.30, 0.16, 0.05, MT['Curb'], 'Curb', 'cb')

# 斑马线（市区路口）
def zebra(cx, cz, axis, matl, group):
    """axis='h': 南北两侧斑马线(沿x方向排) axis='v': 东西侧(沿z方向排)"""
    hw = ST_W/2 + 0.4
    for side in (-1, 1):
        base = side*(hw+1.5)
        for k in range(6):
            o = -3.0 + k*1.2
            if axis == 'h':
                quad = [(cx+o-0.25, cz+base-1.6), (cx+o+0.25, cz+base-1.6), (cx+o+0.25, cz+base+1.6), (cx+o-0.25, cz+base+1.6)]
            else:
                quad = [(cx+base-1.6, cz+o-0.25), (cx+base+1.6, cz+o-0.25), (cx+base+1.6, cz+o+0.25), (cx+base-1.6, cz+o+0.25)]
            vs = [C(q[0], terrain_h(q[0], q[1])+0.11, q[1]) for q in quad]
            mesh_obj('zebra', vs, [(0, 1, 2), (0, 2, 3)], matl, group=group,
                     normals=[(0, 1, 0)]*4)
for x in VERT_XS:
    for z in HORZ_ZS:
        if city_x0 < x < city_x1 and city_z0 < z < city_z1:
            zebra(x, z, 'h', MT['MarkW'], 'MarkW')
            zebra(x, z, 'v', MT['MarkW'], 'MarkW')

# 灯塔观景台（贴地圆盘网格，随山势起伏）
lh_ctr = get_center([r for r in SPEC['roads'] if r['id'] == 'climb'][0])
lx, lz = lh_ctr[-1]
lh_x, lh_z = lx, lz - 4
disc_v, disc_f = [], []
RINGS, SEG = 6, 40
disc_v.append(C(lh_x, terrain_h(lh_x, lh_z) + 0.09, lh_z))
for ri in range(1, RINGS + 1):
    rr = 15.0 * ri / RINGS
    for k in range(SEG):
        a = k / SEG * math.tau
        px, pz = lh_x + rr * math.sin(a), lh_z + rr * math.cos(a)
        disc_v.append(C(px, terrain_h(px, pz) + 0.09, pz))
for ri in range(RINGS):
    for k in range(SEG):
        a = 1 + ri * SEG + k
        b = 1 + ri * SEG + (k + 1) % SEG
        c2 = 1 + (ri + 1) * SEG + k
        d = 1 + (ri + 1) * SEG + (k + 1) % SEG
        if ri == 0:
            disc_f.append((0, b, a)); disc_f.append((a, b, d))
        else:
            disc_f.append((a, c2, b)); disc_f.append((b, c2, d))
mesh_obj('Plaza', disc_v, disc_f, MT['Asphalt'], group='RoadCN', normals=[(0, 1, 0)] * len(disc_v))

# 海滩沙地（贴地条带）
sand_v, sand_f, sand_uv = [], [], []
NX, NZ = 46, 10
for j in range(NZ + 1):
    for i in range(NX + 1):
        x = -1150 + 2300 * i / NX
        z = 822 + 170 * j / NZ
        # 凸坡上地形网格线性插值会高出解析面约12cm，沙地偏移随入海渐增压住地形
        lift = 0.03 + 0.15 * WS._sstep(min(max((z - 822.0) / 30.0, 0.0), 1.0))
        sand_v.append(C(x, terrain_h(x, z) + lift, z))
        sand_uv.append((x / 6.0, z / 6.0))
for j in range(NZ):
    for i in range(NX):
        a = j * (NX + 1) + i
        sand_f.append((a, a + NX + 1, a + 1)); sand_f.append((a + 1, a + NX + 1, a + NX + 2))
mesh_obj('BeachStrip', sand_v, sand_f, MT['Beach'], uvs=sand_uv, group='Beach', normals=[(0, 1, 0)] * len(sand_v))
print('roads ok')

# ============================================================
#  3. 建筑
# ============================================================
collider_rects = []
collider_circles = []
rail_polys = []

PARK_BLOCKS = {(2, 4), (4, 1)}

def uvbox(name, cx, cz, w, d, h, y0, mat_wall, mat_top, group, tu=12.0, tv=12.0):
    """带真实米制UV的楼体（4墙+顶）"""
    x0, x1, z0, z1, yb, yt = cx-w/2, cx+w/2, cz-d/2, cz+d/2, y0, y0+h
    verts = [
        C(x0, yb, z0), C(x1, yb, z0), C(x1, yb, z1), C(x0, yb, z1),
        C(x0, yt, z0), C(x1, yt, z0), C(x1, yt, z1), C(x0, yt, z1),
    ]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
    uvs = []
    for f in faces:
        if len(f) == 4 and f[0] < 4:   # 墙面
            fw = math.hypot(verts[f[1]][0]-verts[f[0]][0], verts[f[1]][2]-verts[f[0]][2])
            uvs += [(0, 0), (fw/tu, 0), (fw/tu, h/tv), (0, h/tv)]
        else:
            uvs += [(0, 0), (w/tu, 0), (w/tu, d/tu), (0, d/tu)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces); me.update()
    uvl = me.uv_layers.new(name='UVMap')
    for i, uv in enumerate(uvs): uvl.data[i].uv = uv
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat_wall)
    obj.data.materials.append(mat_top)
    for pi, poly in enumerate(me.polygons):
        poly.material_index = 4 if pi == 4 else 0
    put(obj, group)
    return obj

def add_building(cx, cz, w, d, h, style):
    if style == 'glass':
        uvbox('Bld', cx, cz, w, d, h, 0.0, MT['FacGlass'], MT['RoofDk'], 'BldGlass')
    else:
        uvbox('Bld', cx, cz, w, d, h, 0.0, MT['FacRes'], MT['Roof'], 'BldRes')
    # 顶部女儿墙
    for (ox, oz, sw, sd) in ((0, -d/2+0.15, w, 0.3), (0, d/2-0.15, w, 0.3), (-w/2+0.15, 0, 0.3, d), (w/2-0.15, 0, 0.3, d)):
        box('Parapet', (sw, 0.55, sd), (cx+ox, h+0.2, cz+oz), MT['RoofDk'], group='RoofTrim', bevel=0)
    # 屋顶设备
    for k in range(rng.randint(1, 3)):
        box('AC', (rng.uniform(1.5, 3.5), 1.2, rng.uniform(1.5, 3.5)),
            (cx+rng.uniform(-w/3, w/3), h+0.6, cz+rng.uniform(-d/3, d/3)), MT['TrimDk'], group='RoofTrim', bevel=0.02)
    collider_rects.append([cx, cz, w/2, d/2])
    # 底商（中低层）
    if h < 34:
        bw, bd = min(w+0.5, 52), min(d+0.5, 52)
        band = uvbox('Shop', cx, cz, bw, bd, 4.4, 0.0, MT['FacShop'], MT['TrimDk'], 'BldShop', tu=9.0, tv=4.5)

dtown = (0.0, -40.0)
for bi in range(6):
    for bj in range(7):
        x0 = VERT_XS[bi]+ST_W/2+8.5
        x1 = VERT_XS[bi+1]-ST_W/2-8.5
        z0 = HORZ_ZS[bj]+ST_W/2+8.5
        z1 = HORZ_ZS[bj+1]-ST_W/2-8.5
        cx, cz = (x0+x1)/2, (z0+z1)/2
        if (bi, bj) in PARK_BLOCKS:
            # 街心公园
            lw = x1-x0; ld = z1-z0
            box('Lawn', (lw, 0.1, ld), (cx, 0.18, cz), MT['Lawn'], group='Park', bevel=0)
            box('PathH', (lw, 0.06, 3.0), (cx, 0.26, cz), MT['Sidewalk'], group='Park', bevel=0)
            box('PathV', (3.0, 0.06, ld), (cx, 0.26, cz), MT['Sidewalk'], group='Park', bevel=0)
            cyl('FountRim', 5.0, 0.8, (cx, 0.5, cz), MT['Curb'], group='Park', verts=20)
            cyl('FountW', 4.4, 0.7, (cx, 0.52, cz), MT['Fountain'], group='Park', verts=20)
            cone('FountC', 0.8, 2.2, (cx, 1.6, cz), MT['Curb'], group='Park', verts=12)
            for k in range(10):
                a = k/10*math.tau + rng.uniform(-0.2, 0.2)
                tx, tz = cx+math.cos(a)*rng.uniform(14, lw/2-8), cz+math.sin(a)*rng.uniform(14, ld/2-8)
                cyl('Ptrunk', 0.22, 3.0, (tx, 1.8, tz), MT['Bark'], group='Park', verts=8)
                sphere('Pblob', (tx+rng.uniform(-0.5, 0.5), 4.2, tz+rng.uniform(-0.5, 0.5)),
                       (2.2, 2.2, 2.2), MT['TreeBlob'], group='Park', seg=10, ring=6)
            for k in range(6):
                bx = cx+rng.uniform(-lw/3, lw/3); bz = cz+rng.uniform(-ld/3, ld/3)
                box('Bench', (2.0, 0.5, 0.6), (bx, 0.55, bz), MT['Bench'], group='Park', rot=(0, rng.uniform(0, 3.14), 0), bevel=0.02)
            continue
        dcent = math.hypot(cx-dtown[0], cz-dtown[1])
        if dcent < 250:
            n = rng.randint(1, 2)
            for k in range(n):
                w = rng.uniform(42, 62); d = rng.uniform(42, 62)
                h = rng.uniform(48, 88)
                bx = cx + (rng.uniform(-30, 30) if n > 1 else 0)
                bz = cz + (rng.uniform(-30, 30) if n > 1 else 0)
                add_building(bx, bz, w, d, h, 'glass')
        elif dcent < 460:
            for k in range(rng.randint(2, 3)):
                w = rng.uniform(28, 48); d = rng.uniform(28, 48)
                h = rng.uniform(20, 50)
                add_building(cx+rng.uniform(-38, 38), cz+rng.uniform(-38, 38), w, d, h,
                             'glass' if rng.random() < 0.4 else 'res')
        else:
            for k in range(rng.randint(2, 4)):
                w = rng.uniform(20, 40); d = rng.uniform(20, 40)
                h = rng.uniform(10, 26)
                add_building(cx+rng.uniform(-40, 40), cz+rng.uniform(-40, 40), w, d, h, 'res')
print('buildings ok')

# ============================================================
#  4. 路灯 / 信号灯 / 护栏 / 广告牌
# ============================================================
def streetlight(x, z, face_dir, h=7.0, arm=2.2, group='Lights'):
    yb = terrain_h(x, z)
    cyl('Pole', 0.09, h, (x, yb+h/2, z), MT['Pole'], group=group, verts=8)
    box('Arm', (arm, 0.08, 0.08), (x+face_dir[0]*arm/2, yb+h-0.1, z+face_dir[1]*arm/2), MT['Pole'], group=group, bevel=0)
    box('LampHead', (0.55, 0.12, 0.24), (x+face_dir[0]*arm, yb+h-0.18, z+face_dir[1]*arm), MT['Pole'], group=group, bevel=0.02)
    collider_circles.append([x, z, 0.30])

for x in VERT_XS:
    zs = list(range(-500, 641, 88))
    for z in zs:
        if any(abs(z-hz) < 10 for hz in HORZ_ZS): continue
        streetlight(x+9.0, z, (-1, 0))
        streetlight(x-9.0, z, (1, 0))
for z in HORZ_ZS:
    xs = list(range(-500, 541, 88))
    for x in xs:
        if any(abs(x-vx) < 10 for vx in VERT_XS): continue
        streetlight(x, z+9.0, (0, -1))
        streetlight(x, z-9.0, (0, 1))

hwy = SPEC['roads'][0]
hctr = get_center(hwy)
for i in range(0, len(hctr), 26):
    x, z = hctr[i]
    if abs(x) > 1240: continue
    for s in (-1, 1):
        streetlight(x+s*11.0, z, (-s, 0), h=10.0, arm=3.2, group='Lights')

# 高速护栏（两侧，进 colliders.json）
def offset_polyline(ctr, off):
    out = []
    for i, (x, z) in enumerate(ctr):
        if i == 0: dx, dz = ctr[1][0]-x, ctr[1][1]-z
        else: dx, dz = x-ctr[i-1][0], z-ctr[i-1][1]
        l = math.hypot(dx, dz) or 1.0
        out.append((x + (-dz/l)*off, z + (dx/l)*off))
    return out

for s in (-1, 1):
    rp = offset_polyline(hctr, s*(hwy['w']/2+1.0))
    rail_polys.append([c for pt in rp[::4] for c in pt])
    for i in range(0, len(rp)-1, 4):
        x, z = rp[i]
        x2, z2 = rp[min(i+4, len(rp)-1)]
        dx, dz = x2-x, z2-z
        l = math.hypot(dx, dz) or 1.0
        yb = terrain_h(x, z)
        box('RailPost', (0.12, 0.75, 0.12), (x, yb+0.35, z), MT['Rail'], group='Rail', bevel=0)
        mid = ((x+x2)/2, (z+z2)/2)
        ang = math.atan2(dx, dz)
        box('RailBeam', (0.08, 0.3, l), (mid[0], terrain_h(mid[0], mid[1])+0.62, mid[1]),
            MT['Rail'], rot=(0, ang, 0), group='Rail', bevel=0)
climb_ctr = get_center([r for r in SPEC['roads'] if r['id'] == 'climb'][0])
for s in (-1, 1):
    rp = offset_polyline(climb_ctr, s*(4.5+1.0))
    rail_polys.append([c for pt in rp[::4] for c in pt])
    for i in range(0, len(rp)-1, 5):
        x, z = rp[i]
        x2, z2 = rp[min(i+5, len(rp)-1)]
        dx, dz = x2-x, z2-z
        l = math.hypot(dx, dz) or 1.0
        mid = ((x+x2)/2, (z+z2)/2)
        ang = math.atan2(dx, dz)
        box('RailBeam', (0.08, 0.3, l), (mid[0], terrain_h(mid[0], mid[1])+0.62, mid[1]),
            MT['Rail'], rot=(0, ang, 0), group='Rail', bevel=0)
        box('RailPost', (0.12, 0.75, 0.12), (x, terrain_h(x, z)+0.35, z), MT['Rail'], group='Rail', bevel=0)

# 红绿灯（市中心路口）
for x in (-160, 0, 160):
    for z in (-240, -80, 80):
        for sx, sz in ((1, 1), (-1, -1)):
            px, pz = x+sx*9.0, z+sz*9.0
            yb = terrain_h(px, pz)
            cyl('TLPole', 0.08, 4.6, (px, yb+2.3, pz), MT['Pole'], group='Lights', verts=8)
            box('TLArm', (3.0, 0.07, 0.07), (px-sx*1.5, yb+4.5, pz-sz*1.5), MT['Pole'], group='Lights', bevel=0)
            box('TLBox', (0.3, 0.85, 0.3), (px-sx*3.0, yb+4.1, pz-sz*3.0), MT['TrimDk'], group='Lights', bevel=0.02)
            cyl('TLg', 0.09, 0.06, (px-sx*3.0, yb+3.85, pz-sz*3.0), mat('TLg', S(40, 220, 90), emit=S(40, 220, 90), estr=3), axis='z', group='Lights', verts=8)
            collider_circles.append([px, pz, 0.28])

# 高速广告牌
for s_pos in (300, 1150, 2050):
    i = min(int(s_pos/3), len(hctr)-2)
    x, z = hctr[i]
    dx, dz = hctr[i+1][0]-x, hctr[i+1][1]-z
    l = math.hypot(dx, dz) or 1.0
    nx, nz = -dz/l, dx/l
    px, pz = x-nx*16, z-nz*16
    yb = terrain_h(px, pz)
    for sx in (-3, 3):
        cyl('BBleg', 0.18, 12, (px+sx, yb+6, pz), MT['Pole'], group='Billboard', verts=8)
    box('BBpanel', (14, 7, 0.4), (px, yb+13, pz), MT['Billboard'], group='Billboard', rot=(0, math.atan2(dx, dz), 0), bevel=0)
    collider_circles.append([px, pz, 0.5])
print('props ok')

# ============================================================
#  5. 灯塔 / 海滩 / 船
# ============================================================
yb = terrain_h(lh_x, lh_z)
cyl('LhBase', 9.0, 2.0, (lh_x, yb+0.6, lh_z), MT['Rock'], group='Lighthouse', verts=18)
cyl('LhTower', 2.4, 15, (lh_x, yb+2+7.5, lh_z), MT['LhWhite'], group='Lighthouse', verts=16)
cyl('LhBand1', 2.28, 2.2, (lh_x, yb+6.5, lh_z), MT['LhRed'], group='Lighthouse', verts=16)
cyl('LhBand2', 2.12, 2.2, (lh_x, yb+11.5, lh_z), MT['LhRed'], group='Lighthouse', verts=16)
cyl('LhGallery', 2.9, 0.5, (lh_x, yb+17.2, lh_z), MT['TrimDk'], group='Lighthouse', verts=16)
cyl('LhLantern', 1.6, 2.0, (lh_x, yb+18.5, lh_z), MT['Lantern'], group='Lighthouse', verts=12)
cone('LhRoof', 2.0, 1.8, (lh_x, yb+20.4, lh_z), MT['LhRed'], group='Lighthouse', verts=12)
collider_circles.append([lh_x, lh_z, 3.2])

# 海滩棕榈 + 遮阳伞
def palm(x, z, s=1.0, lean=None):
    yb = terrain_h(x, z)
    if lean is None: lean = (rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25))
    px, pz = x, z
    for k in range(4):
        nx, nz = px + lean[0]*1.1, pz + lean[1]*1.1
        cyl('PalmTrunk', 0.14*s*(1-k*0.12), 1.35*s, ((px+nx)/2, yb+0.6*s+k*1.15*s, (pz+nz)/2),
            MT['Bark'], group='Palms', verts=6)
        px, pz = nx, nz
    top_y = yb + 4.6*s
    for k in range(8):
        a = k/8*math.tau + rng.uniform(-0.2, 0.2)
        ca, sa = math.cos(a), math.sin(a)
        # 两段式: 基段微翘 + 末段下垂
        box('Frond', (0.5*s, 0.04, 1.7*s), (px+ca*0.85*s, top_y+0.42, pz+sa*0.85*s),
            MT['Frond'], group='Palms', rot=(0.28, -a, 0.35), bevel=0)
        box('Frond', (0.34*s, 0.035, 1.6*s), (px+ca*1.95*s, top_y+0.18, pz+sa*1.95*s),
            MT['Frond'], group='Palms', rot=(0.75, -a, 0.35), bevel=0)
    sphere('Coco', (px, top_y+0.1, pz), (0.35*s, 0.35*s, 0.35*s), MT['TrunkPalm'], group='Palms', seg=8, ring=5)

for i in range(0, len(hctr), 9):
    x, z = hctr[i]
    if z > 620 and abs(x) < 1050:
        palm(x+11.5, z+2.5, rng.uniform(0.85, 1.2))
for _ in range(46):
    x = rng.uniform(-820, 820)
    z = rng.uniform(826, 848)
    if any((x-rx)**2 + (z-rz)**2 < 36 for rx, rz, _ in collider_circles): continue
    palm(x, z, rng.uniform(0.8, 1.25))

for _ in range(20):
    x = rng.uniform(-780, 780); z = rng.uniform(826, 844)
    m = rng.choice([MT['Umbrella1'], MT['Umbrella2']])
    yb = terrain_h(x, z)
    cyl('UmbPole', 0.045, 2.4, (x, yb+1.2, z), MT['Pole'], group='Beach', verts=6)
    cone('UmbTop', 1.6, 0.7, (x, yb+2.6, z), m, group='Beach', verts=10)
    box('Towel', (1.4, 0.02, 2.2), (x+rng.uniform(-3, 3), yb+0.06, z+rng.uniform(1.5, 3.5)), m, group='Beach', rot=(0, rng.uniform(0, 3.1), 0), bevel=0)

# 帆船
for (bx, bz, s, a) in ((-420, 1080, 1.0, 0.4), (150, 1180, 1.3, 1.2), (620, 1020, 0.8, 2.2)):
    hull_v = []
    secs = [(3.2, 0.5, 0.0, 0.55), (2.0, 0.95, -0.12, 0.75), (0, 1.05, -0.16, 0.85), (-2.2, 0.9, -0.1, 0.75), (-3.4, 0.55, 0.05, 0.55)]
    for (zz, w, yb2, yt2) in secs:
        for k in range(8):
            th = k/8*math.tau
            hull_v.append(C(w*math.cos(th)*s, (yb+0.9)*s + ((yt2+yb2)/2 + (yt2-yb2)/2*math.sin(th))*s, zz*s))
    faces = []
    for i in range(len(secs)-1):
        for k in range(8):
            a1 = i*8+k; b1 = i*8+(k+1) % 8
            c1 = (i+1)*8+k; d1 = (i+1)*8+(k+1) % 8
            faces.append((a1, c1, b1)); faces.append((b1, c1, d1))
    ca, sa = math.cos(a), math.sin(a)
    rot_v = []
    for v in hull_v:
        x, y, z = v
        rot_v.append((bx + x*ca - y*sa, y, bz + x*sa + y*ca))
    mesh_obj('BoatHull', rot_v, faces, MT['Boat'], group='Boats')
    my, mz = yb+0.9, bz
    cyl('Mast', 0.07*s, 11*s, (bx, my+5.5*s, mz), MT['TrimDk'], group='Boats', verts=6)
    sailv = [C(bx, my+1.0*s, mz), C(bx, my+9.5*s, mz), C(bx+3.6*s*ca, my+1.2*s, mz+3.6*s*sa)]
    mesh_obj('Sail', sailv, [(0, 1, 2), (0, 2, 1)], MT['Sail'], group='Boats')

# ============================================================
#  6. 山地植被 / 岩石 / 背景山
# ============================================================
def dist_to_roads(x, z, lim):
    for (rx, rz) in road_samples:
        if (x-rx)**2 + (z-rz)**2 < lim*lim: return False
    return True

pines = []
attempts = 0
while len(pines) < 560 and attempts < 9000:
    attempts += 1
    x = rng.uniform(-1240, 1240); z = rng.uniform(-1240, 1240)
    if city_x0+30 < x < city_x1+30 and city_z0+30 < z < city_z1+30: continue
    if z > 800: continue
    e = 3.0
    slope = math.hypot((terrain_h(x+e, z)-terrain_h(x-e, z))/(2*e), (terrain_h(x, z+e)-terrain_h(x, z-e))/(2*e))
    if slope > 0.5: continue
    if terrain_h(x, z) < -1.0: continue
    if not dist_to_roads(x, z, 10): continue
    if any((x-px)**2+(z-pz)**2 < 100 for px, pz in pines): continue
    pines.append((x, z))
for (x, z) in pines:
    yb = terrain_h(x, z)
    s = rng.uniform(0.8, 1.5)
    cyl('PineTrunk', 0.18*s, 1.6*s, (x, yb+0.8*s, z), MT['Bark'], group='Pines', verts=6)
    for k, (cr, ch, cy) in enumerate(((1.5*s, 2.2*s, 2.2), (1.15*s, 2.0*s, 3.6), (0.75*s, 1.8*s, 4.8))):
        cone('PineC', cr, ch, (x, yb+cy*s, z), MT['Pine'], group='Pines', verts=8)

rocks = []
attempts = 0
while len(rocks) < 70 and attempts < 2500:
    attempts += 1
    x = rng.uniform(-1240, 1240); z = rng.uniform(-1240, 1240)
    if city_x0 < x < city_x1 and city_z0 < z < city_z1: continue
    if not dist_to_roads(x, z, 9): continue
    if terrain_h(x, z) < -1: continue
    rocks.append((x, z))
for (x, z) in rocks:
    yb = terrain_h(x, z)
    s = rng.uniform(0.8, 2.6)
    sphere('Rock', (x, yb+s*0.3, z), (s, s*0.65, s*rng.uniform(0.7, 1.3)), MT['Rock'], group='Rocks', seg=8, ring=5)

# 背景山脉环
for k in range(30):
    a = k/30*math.tau + rng.uniform(-0.05, 0.05)
    r = rng.uniform(1680, 2080)
    x = math.cos(a)*r
    z = math.sin(a)*r - 150
    h = rng.uniform(150, 330)
    if k % 4 == 3:   # 圆丘点缀
        sphere('Mount', (x, h*0.22-24, z), (rng.uniform(260, 430), h, rng.uniform(220, 360)),
               MT['Mount'], group='Mountains', seg=10, ring=6)
    else:            # 尖峰
        mc = cone('Mount', rng.uniform(240, 420), h, (x, h/2 - 30, z), MT['Mount'], group='Mountains', verts=9)
        mc.scale = (rng.uniform(0.8, 1.5), rng.uniform(0.8, 1.5), 1.0)
print('vegetation ok', len(pines), 'pines')

# ============================================================
#  7. 分组合并 + 导出
# ============================================================
def join_group(name):
    objs = GROUPS.get(name)
    if not objs: return None
    # join 目标必须是单用户空网格，否则会写穿共享图元缓存导致几何爆炸
    target = bpy.data.objects.new('J_' + name, bpy.data.meshes.new('J_' + name))
    bpy.context.collection.objects.link(target)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    if len(objs) >= 1:
        bpy.ops.object.join()
    target.name = name
    return target

all_groups = set(GROUPS.keys())
print('groups:', sorted(all_groups))
for g in sorted(all_groups):
    try:
        join_group(g)
    except Exception as ex:
        print('JOIN FAIL', g, repr(ex))
bpy.ops.object.select_all(action='DESELECT')

kw = dict(filepath=os.path.join(OUTDIR, 'world.glb'), export_format='GLB', export_apply=True,
          export_yup=True, export_animations=False, export_skins=False,
          export_morph=False, export_cameras=False, export_lights=False)
try:
    bpy.ops.export_scene.gltf(use_selection=False, **kw)
except TypeError:
    bpy.ops.export_scene.gltf(**kw)
print('EXPORTED world.glb', os.path.getsize(os.path.join(OUTDIR, 'world.glb'))//1024, 'KB')

pois = {'lighthouse': [lh_x, lh_z], 'lake': [SPEC['lake']['x'], SPEC['lake']['z']],
        'plaza': [lx, lz]}
out = {'rects': collider_rects, 'circles': collider_circles,
       'rails': rail_polys, 'pois': pois}
print('@@COLLIDERS@@')
print(json.dumps(out))
print('@@END@@')
print('DONE')
