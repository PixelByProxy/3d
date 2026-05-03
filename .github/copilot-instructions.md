# Copilot Instructions

This repository is a simple 3D model generator rooted in `matrix_pot/create.py`.

## Important details
- `matrix_pot/create.py` is the only main script. It generates `output/matrixpot.3mf` from a procedural glyph pattern.
- The project is not a library or application; it is a one-shot generator.
- Mesh generation uses millimeter units, Pillow for glyph masks, NumPy for array processing, and trimesh for mesh construction.
- No package manifest is present, so use the local Python interpreter and install dependencies manually if needed.

## Recommended agent behavior
- Focus on `matrix_pot/create.py` for bug fixes, improvements, and feature changes.
- Preserve print-safety and watertight mesh behavior when modifying the geometry pipeline.
- Use `AGENTS.md` for additional context and `README.md` for repository-level documentation.

## Run locally
From the repository root:

```powershell
python matrix_pot/create.py
```

If dependencies are missing:

```powershell
python -m pip install Pillow numpy trimesh
```
