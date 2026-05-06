"""
Matrix Pot 3D Model Generator - Print-Safe Glyph Pattern Generator

Generates a 3MF model with two components:
  1. Black shell: outer wall with Matrix-style glyph cutouts
  2. Green liner: watertight inner structure ensuring print safety

Pipeline:
  - Rasterize random glyphs to 2D mask using Pillow and fonts
  - Convert mask to 3D geometry using numpy arrays
  - Build cylindrical mesh segments using trimesh
  - Export to 3MF (3D Manufacturing Format) ZIP archive
"""

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

# ============================================================================
# POT GEOMETRY PARAMETERS (all dimensions in millimeters)
# ============================================================================
R_OUTER = 58.0   # Outer radius of pot wall
R_INNER = 57.0   # Inner radius of pot wall (1mm thickness)
HEIGHT = 100.0   # Total height of pot
BOTTOM_THICKNESS = 3.0  # Thickness of bottom disk

# Glyph band: keep stronger rims at top/bottom for structural integrity
Z_GLYPH_MIN = 8.0   # Minimum height where glyphs appear
Z_GLYPH_MAX = 90.0  # Maximum height where glyphs appear

# ============================================================================
# RASTERIZATION PARAMETERS
# ============================================================================
# Resolution: 0.6 mm per pixel balances printability and feature clarity
RES = 0.6
W = int(round(2 * math.pi * R_OUTER * RES))  # Canvas width (circumference)
H = int(round(HEIGHT * RES))  # Canvas height

# ============================================================================
# GLYPH MASK GENERATION
# ============================================================================
# Create a 2D raster image where white pixels = material, black = holes

mask = Image.new("L", (W, H), 0)

# Load font for rendering glyphs
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

# Character set for Matrix-style pattern
glyphs = list("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789+-=<>")
glyphs = list("abcdefghijklmnopqrstuvwxyz1234579$+-*=%'&(,.;:{}>[]^~")
random.seed(20260419)  # Fixed seed for reproducible layout

# Glyph cell dimensions (in pixels at RES resolution)
cell_w = 6  # Column width
cell_h = 8  # Row height
zmin_px = int(round((HEIGHT - Z_GLYPH_MAX) * RES))  # Top of glyph band (pixels)
zmax_px = int(round((HEIGHT - Z_GLYPH_MIN) * RES))  # Bottom of glyph band (pixels)

# Generate random column layout
x = 0
while x < W:
    # Varied column heights create natural irregularity
    col_height_cells = random.randint(3, 10)  # Columns with 3-10 character cells
    col_start = random.randint(zmin_px, max(zmin_px, zmax_px - col_height_cells * cell_h))

    y = col_start
    for _ in range(col_height_cells):
        if y + cell_h > zmax_px:
            break
        # Skip some cells randomly to create gaps
        if random.random() < 0.25:
            y += cell_h + random.randint(0, cell_h)  # Some vertical spacing variation
            continue

        # Render glyph character into cell tile
        ch = random.choice(glyphs)
        tile = Image.new("L", (cell_w, cell_h), 0)
        td = ImageDraw.Draw(tile)
        bbox = td.textbbox((0, 0), ch, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (cell_w - tw) / 2 - bbox[0]  # Center horizontally
        ty = (cell_h - th) / 2 - bbox[1]  # Center vertically
        td.text((tx, ty), ch, font=font, fill=255)

        # Paste tile into the main mask at (x, y)
        mask.paste(tile, (x, y), tile)

        y += cell_h

    x += cell_w + random.randint(2, 2)

# Convert mask to boolean array (1=glyph, 0=hole)
arr = np.array(mask) > 80
mask.save(PREVIEW)



# ============================================================================
# MESH GEOMETRY FUNCTIONS
# ============================================================================

def add_curved_prism(verts, faces, r0, r1, theta0, theta1, z0, z1, max_seg_mm=3.0):
    """
    Create a curved wedge segment of an annular (ring) wall.
    
    Generates vertices and triangular faces for a 3D section between two radii
    (r0=inner, r1=outer) and two angles (theta0, theta1), from height z0 to z1.
    Used to build cylindrical shells with glyph cutouts.
    
    Args:
        verts: vertex list to append to
        faces: face index list to append to
        r0: inner radius
        r1: outer radius
        theta0, theta1: start and end angles (radians)
        z0, z1: bottom and top heights
        max_seg_mm: max edge length for segmentation
    """
    arc = abs(theta1 - theta0) * r1
    n = max(1, int(math.ceil(arc / max_seg_mm)))
    start = len(verts)
    
    # Create vertices along the arc (outer and inner rings at each angle)
    for i in range(n + 1):
        t = theta0 + (theta1 - theta0) * i / n
        c, s = math.cos(t), math.sin(t)
        verts.extend([
            (r1*c, r1*s, z0), (r1*c, r1*s, z1),  # Outer ring
            (r0*c, r0*s, z0), (r0*c, r0*s, z1),  # Inner ring
        ])
    
    # Create faces connecting the vertices
    for i in range(n):
        a = start + 4*i
        b = start + 4*(i+1)
        faces.extend([
            (a, b, b+1), (a, b+1, a+1),          # Outer wall (radial strips)
            (a+2, a+3, b+3), (a+2, b+3, b+2),    # Inner wall
            (a, a+2, b+2), (a, b+2, b),          # Bottom ring
            (a+1, b+1, b+3), (a+1, b+3, a+3),    # Top ring
        ])
    
    # Cap the wedge ends
    s = start
    e = start + 4*n
    faces.extend([(s, s+1, s+3), (s, s+3, s+2)])  # Start cap
    faces.extend([(e, e+2, e+3), (e, e+3, e+1)])  # End cap


def runs(row_bool):
    """
    Find continuous runs of True values in a 1D boolean array.
    
    Returns list of (start, end) tuples marking where material exists.
    Used to identify glyph positions along each height row.
    """
    out = []
    x = 0
    N = len(row_bool)
    while x < N:
        # Skip false regions
        while x < N and not row_bool[x]:
            x += 1
        a = x
        # Find end of true region
        while x < N and row_bool[x]:
            x += 1
        if x > a:
            out.append((a, x))
    return out


# ============================================================================
# BLACK SHELL MESH: cylindrical wall with glyph cutouts
# ============================================================================
# Iterate through height levels and build wall segments where glyphs don't cut

black_v, black_f = [], []
for y in range(H):
    # Convert pixel row index to Z-coordinates
    z0 = HEIGHT - (y + 1) / RES
    z1 = HEIGHT - y / RES
    
    # Within glyph band: invert glyph array to get holes
    # Outside glyph band: solid wall (all ones)
    if z0 >= Z_GLYPH_MIN and z1 <= Z_GLYPH_MAX:
        black_row = ~arr[y]  # Invert: glyphs become holes
    else:
        black_row = np.ones(W, dtype=bool)  # Solid wall

    # Add wall segments where black_row is True
    for a, b in runs(black_row):
        # Convert pixel indices to angles (circumference wraps at 2π)
        theta0 = (a / RES) / R_OUTER
        theta1 = (b / RES) / R_OUTER
        add_curved_prism(black_v, black_f, R_INNER, R_OUTER, theta0, theta1, z0, z1)

# Build solid bottom disk (fills the base)
for i in range(240):
    t0 = 2 * math.pi * i / 240
    t1 = 2 * math.pi * (i + 1) / 240
    add_curved_prism(black_v, black_f, 0.001, R_OUTER, t0, t1, 0, BOTTOM_THICKNESS, max_seg_mm=3.0)

black_mesh = trimesh.Trimesh(vertices=np.array(black_v, dtype=float), faces=np.array(black_f, dtype=np.int64), process=False)


# ============================================================================
# GREEN LINER MESH: watertight inner structure
# ============================================================================
# The liner is a sealed container inside the pot that ensures print safety
# and prevents internal overhangs or unsupported geometry

def make_liner(r_outer=56.55, wall=2.50, z0=3.25, height=92.0, bottom=1.5, seg=240):
    """
    Create a watertight cylindrical liner with solid bottom.
    
    Args:
        r_outer: outer radius of liner
        wall: wall thickness (inner = outer - wall)
        z0: base height (Z coordinate)
        height: height of cylindrical section
        bottom: thickness of bottom floor
        seg: number of segments for circular approximation
    """
    r_inner = r_outer - wall
    ztop = z0 + height
    zfloor = z0 + bottom
    verts, faces = [], []
    
    # Create vertices at each angular segment
    for i in range(seg):
        t = 2 * math.pi * i / seg
        c, s = math.cos(t), math.sin(t)
        verts.extend([
            (r_outer*c, r_outer*s, z0),      # Outer ring at base
            (r_outer*c, r_outer*s, ztop),    # Outer ring at top
            (r_inner*c, r_inner*s, zfloor),  # Inner ring at floor
            (r_inner*c, r_inner*s, ztop),    # Inner ring at top
            (0, 0, z0),                      # Center point at base
            (0, 0, zfloor),                  # Center point at floor
        ])
    
    # Create faces connecting vertices
    for i in range(seg):
        a = 6*i
        b = 6*((i+1) % seg)
        faces.extend([
            (a, b, b+1), (a, b+1, a+1),      # Outer wall
            (a+2, a+3, b+3), (a+2, b+3, b+2), # Inner wall
            (a+1, b+1, b+3), (a+1, b+3, a+3), # Top seal
            (a+4, b, a),                      # Bottom radial (outer to center)
            (a+5, a+2, b+2),                  # Floor radial (inner to center)
            (a, b, b+2), (a, b+2, a+2),       # Side walls
        ])
    
    return trimesh.Trimesh(vertices=np.array(verts, dtype=float), faces=np.array(faces, dtype=np.int64), process=False)

green_mesh = make_liner()


# ============================================================================
# 3MF EXPORT: Convert meshes to 3D Manufacturing Format
# ============================================================================
# 3MF is a ZIP archive containing XML model data and metadata

def mesh_xml(mesh, obj_id, name, pindex):
    """
    Convert a trimesh object to 3MF XML format.
    
    Args:
        mesh: trimesh.Trimesh object to serialize
        obj_id: unique object ID
        name: display name in slicer software
        pindex: material index (0=black shell, 1=green liner)
        
    Returns:
        XML string with vertices and triangles
    """
    out = [f'<object id="{obj_id}" type="model" name="{html.escape(name)}" pid="1" pindex="{pindex}"><mesh><vertices>']
    
    # Add vertex coordinates
    for x, y, z in mesh.vertices:
        out.append(f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>')
    
    out.append('</vertices><triangles>')
    
    # Add triangular faces (referencing vertex indices)
    for a, b, c in mesh.faces:
        out.append(f'<triangle v1="{int(a)}" v2="{int(b)}" v3="{int(c)}"/>')
    
    out.append('</triangles></mesh></object>')
    return "".join(out)


# Build complete 3MF model XML with both shell and liner
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

# XML metadata required by 3MF specification
content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>'''

rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>'''

# Write 3MF as ZIP archive
with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", rels)
    z.writestr("3D/3dmodel.model", model)

# Print summary statistics
print(f"Created: {OUT}")
print(f"Preview: {PREVIEW}")
print(f"3MF size: {OUT.stat().st_size/1024:.1f} KB")
print(f"Black shell faces: {len(black_mesh.faces)}")
print(f"Green liner faces: {len(green_mesh.faces)}")

