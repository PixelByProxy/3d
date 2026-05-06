import os
from pathlib import Path
import math, random, zipfile, html
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import trimesh

BASE = Path(__file__).resolve().parent
os.chdir(BASE)  # optional: change current working directory to script folder

OUT = Path("./output/matrixpot.3mf")
PREVIEW = Path("./output/matrixpot_preview.png")

# Pot dimensions
R_OUTER = 58.0
R_INNER = 57.0
HEIGHT = 100.0
BOTTOM_THICKNESS = 3.0

# Glyph band: keep stronger rims at top/bottom
Z_GLYPH_MIN = 8.0
Z_GLYPH_MAX = 90.0

# 1 mm pixels keep features printable and reduce tiny artifacts
RES = 0.6
W = int(round(2 * math.pi * R_OUTER * RES))
H = int(round(HEIGHT * RES))

# Uniform, print-safe Matrix-style glyph mask
mask = Image.new("L", (W, H), 0)

font_candidates = [
    "./fonts/matrix-code-nfi.ttf",
#    "./fonts/NotoSansCJK-Regular.ttc",
]
print(Path(font_candidates[0]).resolve())
font_path = next((p for p in font_candidates if Path(p).exists()), None)
try:
    font = ImageFont.truetype(font_path, 11, index=0)
except TypeError:
    font = ImageFont.truetype(font_path, 11)

glyphs = list("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789+-=<>")
glyphs = list("abcdefghijklmnopqrstuvwxyz1234579$+-*=%'&(,.;:{}>[]^~")
random.seed(20260419)

cell_w = 6 # col width
cell_h = 8
zmin_px = int(round((HEIGHT - Z_GLYPH_MAX) * RES))
zmax_px = int(round((HEIGHT - Z_GLYPH_MIN) * RES))

x = 0
while x < W:
    # More space between columns; fewer glyphs
    # if random.random() < 0.26:
    #     x += cell_w + random.randint(4, 10)
    #     continue

    col_height_cells = random.randint(3, 10)  # varied column heights, no extra-large row
    col_start = random.randint(zmin_px, max(zmin_px, zmax_px - col_height_cells * cell_h))

    y = col_start
    for _ in range(col_height_cells):
        if y + cell_h > zmax_px:
            break
        if random.random() < 0.25:
            y += cell_h + random.randint(0, cell_h)  # some vertical spacing variation
            continue

        ch = random.choice(glyphs)
        tile = Image.new("L", (cell_w, cell_h), 0)
        td = ImageDraw.Draw(tile)
        bbox = td.textbbox((0, 0), ch, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (cell_w - tw) / 2 - bbox[0]
        ty = (cell_h - th) / 2 - bbox[1]
        td.text((tx, ty), ch, font=font, fill=255)

        # Moderate dilation only; avoids the earlier oversized/merged glyph problem.
        # tile = tile.filter(ImageFilter.MaxFilter(1))

        # Constrain the actual opening to avoid long bridges/overhangs.
        # Any horizontal run longer than 5 mm is split by adding black separators.
        # arr_tile = np.array(tile) > 80
        # max_run = 5
        # for yy in range(arr_tile.shape[0]):
        #     xx = 0
        #     while xx < arr_tile.shape[1]:
        #         while xx < arr_tile.shape[1] and not arr_tile[yy, xx]:
        #             xx += 1
        #         start = xx
        #         while xx < arr_tile.shape[1] and arr_tile[yy, xx]:
        #             xx += 1
        #         if xx - start > max_run:
        #             # Add a 1px black separator every max_run pixels.
        #             for cut in range(start + max_run, xx, max_run + 1):
        #                 arr_tile[yy, cut:cut+1] = False

        # # Remove isolated 1-pixel noise that can create bad tiny overhangs.
        # cleaned = arr_tile.copy()
        # for yy in range(1, arr_tile.shape[0] - 1):
        #     for xx in range(1, arr_tile.shape[1] - 1):
        #         if arr_tile[yy, xx]:
        #             neighborhood = arr_tile[yy-1:yy+2, xx-1:xx+2].sum()
        #             if neighborhood <= 2:
        #                 cleaned[yy, xx] = False
        # tile = Image.fromarray((cleaned * 255).astype(np.uint8), "L")

        # if x + cell_w <= W:
        mask.paste(tile, (x, y), tile)
        # else:
        #     part = W - x
        #     mask.paste(tile.crop((0, 0, part, cell_h)), (x, y), tile.crop((0, 0, part, cell_h)))
        #     mask.paste(tile.crop((part, 0, cell_w, cell_h)), (0, y), tile.crop((part, 0, cell_w, cell_h)))

        y += cell_h

    x += cell_w + random.randint(2, 2)

arr = np.array(mask) > 80
mask.save(PREVIEW)

def add_curved_prism(verts, faces, r0, r1, theta0, theta1, z0, z1, max_seg_mm=3.0):
    arc = abs(theta1 - theta0) * r1
    n = max(1, int(math.ceil(arc / max_seg_mm)))
    start = len(verts)
    for i in range(n + 1):
        t = theta0 + (theta1 - theta0) * i / n
        c, s = math.cos(t), math.sin(t)
        verts.extend([
            (r1*c, r1*s, z0), (r1*c, r1*s, z1),
            (r0*c, r0*s, z0), (r0*c, r0*s, z1),
        ])
    for i in range(n):
        a = start + 4*i
        b = start + 4*(i+1)
        faces.extend([
            (a, b, b+1), (a, b+1, a+1),          # outer
            (a+2, a+3, b+3), (a+2, b+3, b+2),    # inner
            (a, a+2, b+2), (a, b+2, b),          # bottom
            (a+1, b+1, b+3), (a+1, b+3, a+3),    # top
        ])
    s = start
    e = start + 4*n
    faces.extend([(s, s+1, s+3), (s, s+3, s+2)])
    faces.extend([(e, e+2, e+3), (e, e+3, e+1)])

def runs(row_bool):
    out = []
    x = 0
    N = len(row_bool)
    while x < N:
        while x < N and not row_bool[x]:
            x += 1
        a = x
        while x < N and row_bool[x]:
            x += 1
        if x > a:
            out.append((a, x))
    return out

# Black shell: all wall except through-cut glyph holes
black_v, black_f = [], []
for y in range(H):
    z0 = HEIGHT - (y + 1) / RES
    z1 = HEIGHT - y / RES
    if z0 >= Z_GLYPH_MIN and z1 <= Z_GLYPH_MAX:
        black_row = ~arr[y]
    else:
        black_row = np.ones(W, dtype=bool)

    for a, b in runs(black_row):
        theta0 = (a / RES) / R_OUTER
        theta1 = (b / RES) / R_OUTER
        add_curved_prism(black_v, black_f, R_INNER, R_OUTER, theta0, theta1, z0, z1)

# Solid bottom disk
for i in range(240):
    t0 = 2 * math.pi * i / 240
    t1 = 2 * math.pi * (i + 1) / 240
    add_curved_prism(black_v, black_f, 0.001, R_OUTER, t0, t1, 0, BOTTOM_THICKNESS, max_seg_mm=3.0)

black_mesh = trimesh.Trimesh(vertices=np.array(black_v, dtype=float), faces=np.array(black_f, dtype=np.int64), process=False)

# Green watertight liner
def make_liner(r_outer=56.55, wall=2.50, z0=3.25, height=92.0, bottom=1.5, seg=240):
    r_inner = r_outer - wall
    ztop = z0 + height
    zfloor = z0 + bottom
    verts, faces = [], []
    for i in range(seg):
        t = 2 * math.pi * i / seg
        c, s = math.cos(t), math.sin(t)
        verts.extend([
            (r_outer*c, r_outer*s, z0),
            (r_outer*c, r_outer*s, ztop),
            (r_inner*c, r_inner*s, zfloor),
            (r_inner*c, r_inner*s, ztop),
            (0, 0, z0),
            (0, 0, zfloor),
        ])
    for i in range(seg):
        a = 6*i
        b = 6*((i+1) % seg)
        faces.extend([
            (a, b, b+1), (a, b+1, a+1),
            (a+2, a+3, b+3), (a+2, b+3, b+2),
            (a+1, b+1, b+3), (a+1, b+3, a+3),
            (a+4, b, a),
            (a+5, a+2, b+2),
            (a, b, b+2), (a, b+2, a+2),
        ])
    return trimesh.Trimesh(vertices=np.array(verts, dtype=float), faces=np.array(faces, dtype=np.int64), process=False)

green_mesh = make_liner()

def mesh_xml(mesh, obj_id, name, pindex):
    out = [f'<object id="{obj_id}" type="model" name="{html.escape(name)}" pid="1" pindex="{pindex}"><mesh><vertices>']
    for x, y, z in mesh.vertices:
        out.append(f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>')
    out.append('</vertices><triangles>')
    for a, b, c in mesh.faces:
        out.append(f'<triangle v1="{int(a)}" v2="{int(b)}" v3="{int(c)}"/>')
    out.append('</triangles></mesh></object>')
    return "".join(out)

model = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <metadata name="Application">ChatGPT Matrix Pot Print-Safe Glyphs for Bambu Studio</metadata>
  <resources>
    <basematerials id="1">
      <base name="Black shell" displaycolor="#000000FF"/>
      <base name="Green watertight liner" displaycolor="#00FF00FF"/>
    </basematerials>
    {mesh_xml(black_mesh, 2, "Black shell", 0)}
    {mesh_xml(green_mesh, 3, "Green watertight liner", 1)}
  </resources>
  <build>
    <item objectid="2"/>
    <item objectid="3"/>
  </build>
</model>'''

content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>'''

rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>'''

with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", rels)
    z.writestr("3D/3dmodel.model", model)

print(f"Created: {OUT}")
print(f"Preview: {PREVIEW}")
print(f"3MF size: {OUT.stat().st_size/1024:.1f} KB")
print(f"Black shell faces: {len(black_mesh.faces)}")
print(f"Green liner faces: {len(green_mesh.faces)}")
