# AGENTS

## Purpose
This repository generates a single 3D model file (`output/matrixpot.3mf`) using `matrix_pot/create.py`.

## Key files
- `matrix_pot/create.py` — primary script that builds a print-safe Matrix-style pot using Pillow, NumPy, and trimesh.
- `matrix_pot/fonts/` — font assets used by the glyph renderer.
- `matrix_pot/output/` — generated output files.
- `README.md` — minimal repository description.

## What an AI agent should know
- The project is a one-shot generator, not a package or web app.
- The main logic lives in `matrix_pot/create.py`; changes are usually about geometry, print safety, glyph layout, and 3MF export.
- The script uses millimeter units and builds a 3MF ZIP archive with a shell and a liner.
- Dependencies are not declared in code, so assume a Python environment with: `Pillow`, `numpy`, and `trimesh`.

## Typical tasks
- Improve or refactor the 3D mesh generation logic.
- Make the glyph-pattern generation more print-safe or more aesthetically balanced.
- Add command-line parameters for dimensions, output paths, or font choices.
- Clean up legacy comments and remove unused code while preserving intended print safety behavior.

## Running locally
From the repository root:

```powershell
python matrix_pot/create.py
```

If dependencies are missing, install them with:

```powershell
python -m pip install Pillow numpy trimesh
```
