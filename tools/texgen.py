# -*- coding: utf-8 -*-
"""PIL 程序化贴图生成 → assets/textures/*.png（确定性随机，可重复）"""
import math, os, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'assets', 'textures')
os.makedirs(OUT, exist_ok=True)
rng = random.Random(42)

def noise_rgb(size, base, amp, fn_low=None):
    """两尺度噪点底图"""
    im = Image.new('RGB', (size, size))
    px = im.load()
    for y in range(size):
        for x in range(size):
            n = rng.uniform(-1, 1)
            if fn_low:
                n = 0.65 * n + 0.35 * fn_low(x, y)
            k = 1.0 + amp * n
            px[x, y] = tuple(max(0, min(255, int(c * k))) for c in base)
    return im

def save(im, name):
    im.save(os.path.join(OUT, name))
    print(' ', name, im.size)

# ---------------- 草地 512 (tile 8m) ----------------
low_pts = [(rng.uniform(0, 512), rng.uniform(0, 512), rng.uniform(60, 150)) for _ in range(24)]
def grass_low(x, y):
    v = 0.0
    for (px, py, pr) in low_pts:
        d = math.hypot(x - px, y - py)
        if d < pr:
            v += (1 - d / pr)
    return min(1.0, v)
im = noise_rgb(512, (104, 156, 74), 0.13, grass_low)
px = im.load()
for _ in range(9000):  # 草叶碎光
    x, y = rng.randrange(512), rng.randrange(512)
    l = rng.randint(-18, 26)
    c = px[x, y]
    px[x, y] = tuple(max(0, min(255, v + l)) for v in c)
im = im.filter(ImageFilter.GaussianBlur(0.6))
save(im, 'grass.png')

# ---------------- 沙地 512 (tile 6m) ----------------
im = noise_rgb(512, (216, 198, 152), 0.09)
px = im.load()
for y in range(512):  # 风纹波线
    for k in range(5):
        yy = (y + k * 102 + int(18 * math.sin(y * 0.05 + k))) % 512
        for x in range(0, 512, 2):
            c = px[x, yy]
            px[x, yy] = tuple(max(0, min(255, v - 8)) for v in c)
im = im.filter(ImageFilter.GaussianBlur(0.8))
save(im, 'sand.png')

# ---------------- 沥青 512 (tile 7m; u=横跨路宽) ----------------
im = noise_rgb(512, (76, 78, 82), 0.10)
px = im.load()
for _ in range(4200):  # 骨料亮斑
    x, y = rng.randrange(512), rng.randrange(512)
    r = rng.randint(0, 26)
    c = px[x, y]
    px[x, y] = (min(255, c[0] + r + 18), min(255, c[1] + r + 18), min(255, c[2] + r + 20))
for y in range(512):  # 车辙磨损带（双车道位置 u≈0.32/0.68）
    for u0 in (0.32, 0.68):
        cx = u0 * 512
        for dx in range(-46, 47):
            x = int(cx + dx) % 512
            w = max(0.0, 1 - abs(dx) / 46.0)
            dk = 1 - 0.16 * w
            c = px[x, y]
            px[x, y] = tuple(int(v * dk) for v in c)
im = im.filter(ImageFilter.GaussianBlur(0.5))
save(im, 'asphalt.png')

# ---------------- 人行道 256 (tile 3m, 砖缝) ----------------
im = noise_rgb(256, (202, 204, 207), 0.05)
d = ImageDraw.Draw(im)
for i in range(0, 257, 64):
    d.line([(i, 0), (i, 256)], fill=(160, 162, 166), width=2)
    d.line([(0, i), (256, i)], fill=(160, 162, 166), width=2)
save(im, 'sidewalk.png')

# ---------------- 楼面·玻璃幕墙 512 (12m×12m, 4×4 窗) ----------------
CELL = 128
im = Image.new('RGB', (512, 512), (186, 190, 196))
d = ImageDraw.Draw(im)
for gy in range(4):
    for gx in range(4):
        x0, y0 = gx * CELL, gy * CELL
        tone = rng.randint(-14, 16)
        win = (108 + tone, 142 + tone, 168 + tone)  # 蓝灰玻璃
        d.rectangle([x0 + 8, y0 + 20, x0 + CELL - 8, y0 + CELL - 10], fill=win)
        # 玻璃斜向反光
        for k in range(3):
            ox = rng.randint(-30, 60)
            d.line([(x0 + 10 + ox, y0 + CELL - 12), (x0 + 50 + ox, y0 + 22)],
                   fill=(168 + tone, 196 + tone, 214 + tone), width=7)
        d.rectangle([x0 + 8, y0 + 20, x0 + CELL - 8, y0 + 26], fill=(205, 208, 212))  # 窗楣
im = im.filter(ImageFilter.GaussianBlur(0.4))
save(im, 'fac_glass.png')

# ---------------- 楼面·住宅 512 (12m×12m, 3×3 窗) ----------------
im = Image.new('RGB', (512, 512), (226, 214, 192))
px = im.load()
for y in range(512):
    for x in range(512):
        k = 1 + rng.uniform(-0.045, 0.045)
        px[x, y] = tuple(min(255, int(v * k)) for v in px[x, y])
d = ImageDraw.Draw(im)
for gy in range(3):
    for gx in range(3):
        x0, y0 = gx * 170 + 24, gy * 170 + 26
        w, h = 122, 118
        d.rectangle([x0 - 4, y0 - 4, x0 + w + 4, y0 + h + 4], fill=(186, 178, 160))   # 窗套
        d.rectangle([x0, y0, x0 + w, y0 + h], fill=(96, 118, 138))                    # 玻璃
        cur = rng.choice([(180, 172, 156), (150, 156, 162), None])
        if cur: d.rectangle([x0 + 6, y0 + 8, x0 + w - rng.randint(20, 60), y0 + h - 6], fill=cur)  # 窗帘
        d.line([(x0 + w // 2, y0), (x0 + w // 2, y0 + h)], fill=(210, 204, 190), width=5)
        d.rectangle([x0 - 10, y0 + h + 4, x0 + w + 10, y0 + h + 12], fill=(198, 192, 178))         # 窗台
        if rng.random() < 0.5:                                                                       # 空调外机
            d.rectangle([x0 + w - 34, y0 + h + 14, x0 + w - 4, y0 + h + 40], fill=(148, 150, 154))
save(im, 'fac_res.png')

# ---------------- 店面 512×256 (9m×4.5m) ----------------
im = Image.new('RGB', (512, 256), (238, 236, 230))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, 512, 64], fill=(52, 58, 70))                      # 招牌底
sx = 0
sig = [(226, 88, 58), (240, 170, 40), (70, 160, 120), (58, 120, 200), (170, 80, 170), (226, 88, 58)]
i = 0
while sx < 512:
    w = rng.randint(60, 120)
    c = sig[i % len(sig)]
    d.rounded_rectangle([sx + 6, 10, min(sx + w, 500), 56], 8, fill=c)
    d.rectangle([sx + 16, 24, min(sx + w - 16, 490), 42], fill=(250, 246, 238))
    sx += w + 8; i += 1
d.rectangle([0, 64, 512, 70], fill=(210, 208, 202))
for gx in range(4):                                                   # 落地玻璃
    x0 = gx * 128 + 12
    d.rectangle([x0, 86, x0 + 104, 236], fill=(88, 112, 132))
    d.line([(x0 + 10, 232), (x0 + 70, 92)], fill=(150, 176, 194), width=9)
    d.rectangle([x0, 86, x0 + 104, 96], fill=(200, 200, 205))
save(im, 'fac_shop.png')

# ---------------- 云 256 RGBA ----------------
im = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
for _ in range(26):
    cx, cy = rng.uniform(60, 196), rng.uniform(100, 190)
    r = rng.uniform(18, 52)
    a = rng.randint(28, 60)
    d.ellipse([cx - r, cy - r * 0.62, cx + r, cy + r * 0.62], fill=(255, 255, 255, a))
im = im.filter(ImageFilter.GaussianBlur(9))
save(im, 'cloud.png')

# ---------------- 烟 128 RGBA ----------------
im = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
for _ in range(40):
    cx, cy = rng.uniform(38, 90), rng.uniform(38, 90)
    r = rng.uniform(8, 26)
    a = rng.randint(10, 26)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, a))
im = im.filter(ImageFilter.GaussianBlur(7))
save(im, 'smoke.png')

# ---------------- 水面法线 256 ----------------
h = [[rng.uniform(-1, 1) for _ in range(256)] for _ in range(256)]
# 简单平滑
for p in range(2):
    nh = [[0.0] * 256 for _ in range(256)]
    for y in range(256):
        for x in range(256):
            s = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    s += h[(y + dy) % 256][(x + dx) % 256]
            nh[y][x] = s / 9
    h = nh
im = Image.new('RGB', (256, 256))
px = im.load()
for y in range(256):
    for x in range(256):
        dx = (h[y][(x + 1) % 256] - h[y][(x - 1) % 256]) * 1.6
        dy = (h[(y + 1) % 256][x] - h[(y - 1) % 256][x]) * 1.6
        nx, ny, nz = dx, dy, 1.0
        l = math.sqrt(nx * nx + ny * ny + nz * nz)
        px[x, y] = (int((nx / l * 0.5 + 0.5) * 255), int((ny / l * 0.5 + 0.5) * 255), int((nz / l * 0.5 + 0.5) * 255))
save(im, 'water_n.png')

# ---------------- 车牌 256×64 ----------------
im = Image.new('RGB', (256, 64), (240, 242, 246))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, 256, 14], fill=(24, 92, 200))
d.rectangle([0, 14, 256, 16], fill=(200, 204, 212))
try:
    f = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 30)
except Exception:
    f = ImageFont.load_default()
d.text((16, 16), '极速海岸·A·2026', font=f, fill=(30, 32, 38))
save(im, 'plate.png')

# ---------------- 广告牌 512×256 ----------------
im = Image.new('RGB', (512, 256), (120, 190, 235))
d = ImageDraw.Draw(im)
d.rectangle([0, 170, 512, 256], fill=(90, 150, 90))
d.ellipse([380, 24, 470, 114], fill=(255, 214, 92))
try:
    f1 = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 64)
    f2 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 30)
except Exception:
    f1 = f2 = ImageFont.load_default()
d.text((36, 60), '极速海岸', font=f1, fill=(255, 255, 255))
d.text((40, 140), 'COAST RUSH · 自由驾驶', font=f2, fill=(240, 248, 255))
save(im, 'billboard.png')

# ---------------- 树皮 128 ----------------
im = Image.new('RGB', (128, 128), (98, 74, 56))
px = im.load()
for y in range(128):
    for x in range(128):
        k = 1 + rng.uniform(-0.14, 0.14) + 0.08 * math.sin(x * 0.9 + rng.uniform(-0.3, 0.3))
        px[x, y] = tuple(max(0, min(255, int(v * k))) for v in px[x, y])
save(im, 'bark.png')

print('贴图生成完成 →', OUT)

# ---------------- 测速板 512×256 ----------------
im = Image.new('RGB', (512, 256), (16, 34, 66))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, 511, 255], outline=(90, 200, 250), width=8)
try:
    f1 = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 84)
    f2 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 44)
except Exception:
    f1 = f2 = ImageFont.load_default()
d.text((36, 30), '测速点', font=f1, fill=(120, 220, 255))
d.text((40, 140), 'SPEED CHECK', font=f2, fill=(235, 245, 255))
for i in range(3):  # 雷达镜头
    cx = 330 + i * 62
    d.ellipse([cx, 128, cx + 52, 180], fill=(10, 16, 26))
    d.ellipse([cx + 10, 140, cx + 42, 172], outline=(120, 220, 255), width=4)
    d.ellipse([cx + 20, 148, cx + 32, 160], fill=(255, 90, 70))
save(im, 'radar.png')

# ---------------- 冲刺横幅 1024×160 ----------------
im = Image.new('RGB', (1024, 160), (14, 60, 120))
d = ImageDraw.Draw(im)
for x in range(0, 1024, 46):  # 斜纹
    d.line([(x, 160), (x + 60, 0)], fill=(18, 74, 142), width=14)
try:
    f1 = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 86)
    f2 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 40)
except Exception:
    f1 = f2 = ImageFont.load_default()
d.text((200, 16), '海岸冲刺', font=f1, fill=(255, 255, 255))
d.text((640, 52), 'COAST SPRINT', font=f2, fill=(140, 220, 255))
d.text((40, 52), '>>> ', font=f1, fill=(255, 210, 60))
save(im, 'sprint.png')

print('测速/冲刺贴图生成完成')
