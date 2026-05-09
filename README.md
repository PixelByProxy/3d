# 3D Model Generators

This repository stores code used to generate 3D models. Instead of keeping
only exported mesh files, each model should have a repeatable script that can
rebuild the final output from source code and local assets.

The current project generates a Matrix-style planter/pot as a 3MF file.

## Repository Layout

```text
.
+-- matrix_pot/
|   +-- create.py          # Generates the Matrix-style pot model
|   +-- fonts/             # Font assets used by the glyph renderer
|   +-- output/            # Generated model and preview files
+-- AGENTS.md              # Notes for AI coding agents working in this repo
+-- LICENSE
+-- README.md
```

## Current Models

### Matrix Pot

The Matrix pot generator creates:

- `matrix_pot/output/matrixpot.3mf` - printable 3D model
- `matrix_pot/output/matrixpot_preview.png` - preview image

Run it from the repository root:

```powershell
python matrix_pot/create.py
```

The script uses millimeter units and builds a 3MF archive containing the model
parts needed for printing.

## Requirements

This repo is intentionally lightweight and does not currently declare a package
environment. The model generator expects these Python dependencies:

- `Pillow`
- `numpy`
- `trimesh`

Install them with:

```powershell
python -m pip install Pillow numpy trimesh
```

## Adding New Model Generators

When adding a new model, prefer a self-contained folder with this shape:

```text
model_name/
+-- create.py       # Main generation script
+-- assets/         # Optional source assets, fonts, references, textures, etc.
+-- output/         # Generated files
```

Good generator scripts should:

- Use clear physical units, preferably millimeters.
- Keep important dimensions easy to find near the top of the file.
- Write generated files into that model's `output/` directory.
- Avoid depending on absolute local paths.
- Include enough comments to explain geometry decisions that affect print
  safety, wall thickness, tolerances, or assembly.

Generated output files may be committed when they are useful for printing,
previewing, or sharing the model without rerunning the script.

## Working Notes

This is a code-first 3D modeling repo. Changes are usually about geometry,
printability, mesh quality, export behavior, or reusable generation patterns.
For agent-specific guidance, see `AGENTS.md`.
