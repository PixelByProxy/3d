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
import argparse
import math, random, zipfile, html
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import trimesh

BASE = Path(__file__).resolve().parent
os.chdir(BASE)  # optional: change current working directory to script folder

OUT = Path("./output/matrixpot.3mf")
PREVIEW = Path("./output/matrixpot_preview.png")

OUT.parent.mkdir(parents=True, exist_ok=True)

DEFAULT_RANDOM_SEED = 20260419

def parse_args():
    """Parse command-line options for the model generator."""
    parser = argparse.ArgumentParser(
        description="Generate a Matrix-style 3MF pot model."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=f"Random seed for reproducible glyph layout. Defaults to {DEFAULT_RANDOM_SEED}.",
    )
    return parser.parse_args()

args = parse_args()

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
glyphs = list("abcdefghijklmnopqrstuvwxyz1234579$+-*=%'&(,.;:{}>[]^~")
random.seed(args.seed)  # Fixed seed for reproducible layout

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
    Create a manifold cylindrical liner with a solid bottom.

    The previous version created a separate center-bottom and center-floor
    vertex for every segment. Those points occupied the same coordinates, but
    they were not topologically connected, so slicers saw open/non-manifold
    seams in the bottom and floor fans. It also added an extra sloped face band
    that made three faces meet along the outer-bottom and inner-floor ring
    edges. This version uses shared ring vertices plus one shared center vertex
    per disk, and only emits true boundary faces of the solid liner.
    
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

    # Four shared rings:
    #   0: outer base, 1: outer top, 2: inner floor, 3: inner top
    for ring_r, ring_z in (
        (r_outer, z0),
        (r_outer, ztop),
        (r_inner, zfloor),
        (r_inner, ztop),
    ):
        for i in range(seg):
            t = 2 * math.pi * i / seg
            c, s = math.cos(t), math.sin(t)
            verts.append((ring_r*c, ring_r*s, ring_z))

    center_bottom = len(verts)
    verts.append((0, 0, z0))
    center_floor = len(verts)
    verts.append((0, 0, zfloor))

    outer_base = 0
    outer_top = seg
    inner_floor = 2 * seg
    inner_top = 3 * seg

    # Create faces. Winding is consistent and every edge is used exactly twice.
    for i in range(seg):
        j = (i + 1) % seg

        ob_i, ob_j = outer_base + i, outer_base + j
        ot_i, ot_j = outer_top + i, outer_top + j
        if_i, if_j = inner_floor + i, inner_floor + j
        it_i, it_j = inner_top + i, inner_top + j

        faces.extend([
            (ob_i, ob_j, ot_j), (ob_i, ot_j, ot_i),          # Outer wall
            (if_i, it_i, it_j), (if_i, it_j, if_j),          # Inner wall
            (ot_i, ot_j, it_j), (ot_i, it_j, it_i),          # Top rim annulus
            (center_bottom, ob_j, ob_i),                     # Bottom disk
            (center_floor, if_i, if_j),                      # Inner floor disk
        ])

    mesh = trimesh.Trimesh(
        vertices=np.array(verts, dtype=float),
        faces=np.array(faces, dtype=np.int64),
        process=False,
    )

    # Fail early if a future edit reintroduces non-manifold liner geometry.
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError("Green liner mesh is not watertight/manifold")

    return mesh

green_mesh = make_liner()


# ============================================================================
# 3MF EXPORT: Bambu Studio project-style 3MF with two real plates
# ============================================================================
# This version keeps both meshes directly in 3D/3dmodel.model. The previous
# external-object experiment made Bambu create two plates, but it could resolve
# both plate entries to the first external component. Keeping top-level objects
# inline avoids that ambiguity.

BAMBU_PLATE_SPACING_MM = 307.2  # Bambu/Orca plate-grid spacing for 256 mm beds.
BED_SIZE_MM = 256.0
PLATE_CENTER_X_MM = BED_SIZE_MM / 2
PLATE_CENTER_Y_MM = BED_SIZE_MM / 2

def mesh_object_xml(mesh, obj_id, name, pid):
    """
    Serialize one mesh as a top-level 3MF <object> element.

    v6 color fix:
    Bambu Studio is more reliable when color comes from the Bambu filament
    slot metadata than when it comes only from the 3MF mesh/material color.
    The mesh still carries standard 3MF color properties as a fallback, but
    Metadata/project_settings.config and Metadata/model_settings.config now
    explicitly define slot 1 as black and slot 2 as green and assign the liner
    to extruder/slot 2.
    """
    out = [f'<object id="{obj_id}" type="model" name="{html.escape(name)}" pid="{pid}"><mesh><vertices>']

    # Add vertex coordinates
    for x, y, z in mesh.vertices:
        out.append(f'<vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>')

    out.append('</vertices><triangles>')

    # Add triangular faces
    for a, b, c in mesh.faces:
        out.append(
            f'<triangle v1="{int(a)}" v2="{int(b)}" v3="{int(c)}" '
            f'pid="{pid}" p1="0" p2="0" p3="0"/>'
        )

    out.append('</triangles></mesh></object>')
    return ''.join(out)


# Main model: two real top-level objects.
#
# Bambu Studio plates use the printer bed coordinate system, where a 256 mm
# plate center is at X=128, Y=128. The meshes themselves are modeled around
# X=0, Y=0, so translating each build item to the plate center keeps the pot
# centered. Plate 2 is one Bambu plate-grid step above plate 1.
model = f"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US"
       xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
       xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
       xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
       requiredextensions="p">
  <metadata name="Application">BambuStudio-02.04.00.70</metadata>
  <metadata name="BambuStudio:3mfVersion">1</metadata>
  <metadata name="CreationDate">2026-05-06</metadata>
  <metadata name="Title">Matrix Pot - shell and liner on separate plates</metadata>
  <resources>
    <m:colorgroup id="2">
      <m:color color="#000000FF"/>
    </m:colorgroup>
    <m:colorgroup id="3">
      <m:color color="#00FF00FF"/>
    </m:colorgroup>
    {mesh_object_xml(black_mesh, 1, "Black shell", 2)}
    {mesh_object_xml(green_mesh, 2, "Green watertight liner", 3)}
  </resources>
  <build>
    <item objectid="1" transform="1 0 0 0 1 0 0 0 1 {PLATE_CENTER_X_MM:.5f} {PLATE_CENTER_Y_MM:.5f} 0" p:buildplate="0"/>
    <item objectid="2" transform="1 0 0 0 1 0 0 0 1 {PLATE_CENTER_X_MM + BAMBU_PLATE_SPACING_MM:.5f} {PLATE_CENTER_Y_MM:.5f} 0" p:buildplate="1"/>
  </build>
</model>"""

# Bambu Studio object/plate metadata.
# Important fix in v4: each build item gets a unique instance_id. In v3 both
# plate entries used instance_id=0, so Bambu could bind both plates to the first
# instance, duplicating the black shell and dropping the liner.
model_settings = """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="1">
    <metadata key="name" value="Black shell"/>
    <metadata key="extruder" value="1"/>
    <metadata key="seam_position" value="random"/>
    <metadata key="outer_wall_speed" value="50"/>
    <metadata key="enable_support" value="1"/>
    <metadata key="support_type" value="normal(auto)"/>
    <metadata key="support_on_build_plate_only" value="1"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="Black shell"/>
      <metadata key="extruder" value="1"/>
      <metadata key="source_object_id" value="0"/>
      <metadata key="source_volume_id" value="0"/>
      <metadata key="seam_position" value="random"/>
      <metadata key="outer_wall_speed" value="50"/>
      <metadata key="enable_support" value="1"/>
      <metadata key="support_type" value="normal(auto)"/>
      <metadata key="support_on_build_plate_only" value="1"/>
    </part>
  </object>
  <object id="2">
    <metadata key="name" value="Green watertight liner"/>
    <metadata key="extruder" value="2"/>
    <part id="1" subtype="normal_part">
      <metadata key="name" value="Green watertight liner"/>
      <metadata key="extruder" value="2"/>
      <metadata key="source_object_id" value="1"/>
      <metadata key="source_volume_id" value="0"/>
    </part>
  </object>
  <plate>
    <metadata key="plater_id" value="1"/>
    <metadata key="plater_name" value="Black shell"/>
    <metadata key="filament_map_mode" value="Auto For Flush"/>
    <metadata key="filament_maps" value="1 2"/>
    <metadata key="filament_volume_maps" value="1 1"/>
    <model_instance>
      <metadata key="object_id" value="1"/>
      <metadata key="instance_id" value="0"/>
    </model_instance>
  </plate>
  <plate>
    <metadata key="plater_id" value="2"/>
    <metadata key="plater_name" value="Green liner"/>
    <metadata key="filament_map_mode" value="Auto For Flush"/>
    <metadata key="filament_maps" value="1 2"/>
    <metadata key="filament_volume_maps" value="1 1"/>
    <model_instance>
      <metadata key="object_id" value="2"/>
      <metadata key="instance_id" value="1"/>
    </model_instance>
  </plate>
</config>"""

# Minimal project settings with two visible filament colors. Bambu Studio can
# replace these with your selected printer/material presets when you open it.
project_settings = """{
  "from": "project",
  "name": "project_settings",
  "version": "02.04.00.70",
  "printer_model": "Bambu Lab P2S",
  "curr_bed_type": "Textured PEI Plate",
  "nozzle_diameter": ["0.4"],
  "print_settings_id": "0.20mm Standard @BBL P2S",
  "printer_settings_id": "Bambu Lab P2S 0.4 nozzle",
  "default_print_profile": "0.20mm Standard @BBL P2S",
  "default_filament_profile": ["Bambu PLA Basic @BBL P2S"],
  "filament_colour": ["#000000", "#00FF00"],
  "filament_colour_type": ["1", "1"],
  "filament_settings_id": ["Bambu PLA Basic @BBL P2S", "Bambu PLA Basic @BBL P2S"],
  "filament_type": ["PLA", "PLA"],
  "filament_vendor": ["Bambu", "Bambu"],
  "filament_ids": ["10101", "10501"],
  "filament_diameter": ["1.75", "1.75"],
  "filament_density": ["1.24", "1.24"],
  "filament_map": ["1", "2"],
  "different_settings_to_system": [
    "filament_colour;filament_colour_type;filament_density;filament_diameter;filament_ids;filament_settings_id;filament_type;filament_vendor",
    "filament_colour;filament_colour_type;filament_density;filament_diameter;filament_ids;filament_settings_id;filament_type;filament_vendor",
    ""
  ]
}"""

slice_info = """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <header>
    <metadata key="X-BambuStudio-Version" value="02.04.00.70"/>
    <metadata key="X-BambuStudio-PlateCount" value="2"/>
  </header>
  <plate>
    <metadata key="index" value="1"/>
    <metadata key="plater_name" value="Black shell"/>
  </plate>
  <plate>
    <metadata key="index" value="2"/>
    <metadata key="plater_name" value="Green liner"/>
  </plate>
</config>"""

# XML metadata required by 3MF specification and Bambu project files.
content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
  <Default Extension="config" ContentType="application/vnd.ms-package.3dmanufacturing.config+xml"/>
  <Default Extension="png" ContentType="image/png"/>
</Types>"""

rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>"""

# Tiny placeholder thumbnails. Real Bambu projects include these; including them
# helps Bambu Studio recognize two saved plates even before slicing.
thumb = Image.new("RGB", (16, 16), "white")
thumb_path = OUT.parent / "_blank_plate_thumbnail.png"
thumb.save(thumb_path)
thumb_bytes = thumb_path.read_bytes()
try:
    thumb_path.unlink()
except OSError:
    pass

# Write 3MF as ZIP archive
with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", rels)
    z.writestr("3D/3dmodel.model", model)
    z.writestr("Metadata/model_settings.config", model_settings)
    z.writestr("Metadata/project_settings.config", project_settings)
    z.writestr("Metadata/slice_info.config", slice_info)
    for plate_id in (1, 2):
        z.writestr(f"Metadata/plate_{plate_id}.png", thumb_bytes)
        z.writestr(f"Metadata/plate_{plate_id}_small.png", thumb_bytes)
        z.writestr(f"Metadata/plate_no_light_{plate_id}.png", thumb_bytes)
        z.writestr(f"Metadata/top_{plate_id}.png", thumb_bytes)
        z.writestr(f"Metadata/pick_{plate_id}.png", thumb_bytes)

# Print summary statistics
print(f"Created: {OUT}")
print(f"Preview: {PREVIEW}")
print(f"3MF size: {OUT.stat().st_size/1024:.1f} KB")
print(f"Black shell faces: {len(black_mesh.faces)}")
print(f"Green liner faces: {len(green_mesh.faces)}")