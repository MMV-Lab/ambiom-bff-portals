# AMBIOM tools for BFF

A tool for processing and uploading raw microscopy files to use with [BioFileFinder (BFF)](https://bff.allencell.org/) by the Allen Institute for Cell Science.

## Overview

This project provides utilities to extract metadata from raw microscopy files and prepare them for use with BioFileFinder. Everything is managed through [marimo](https://marimo.io/) notebooks and [uv](https://github.com/astral-sh/uv) for dependency management.

## Main Components

### 📃 `bff_uploader`

An interactive uploader that allows users to:
- Select raw microscopy files (or directories for tiled acquisitions) via a file browser
- Extract relevant metadata from raw microscopy files using the appropriate microscope adapter
- Add experimental annotations (host, cell line, location, treatment, …)
- Write entries to the intermediate CSV database

**Development mode** (with editing capabilities):
```bash
uv run marimo edit notebooks/bff_uploader.py
```

**User mode** (front-end only):
```bash
uv run marimo run notebooks/bff_uploader.py
```

### ⚙ `bff_processor`

Converts uploaded entries into OME-TIFF / OME-Zarr files and generates thumbnails. Can be launched as a standalone script:

```bash
uv run notebooks/bff_processor.py
```

### 🗄 Database helpers

Marimo notebooks for generating the reference databases used by the uploader:

```bash
uv run marimo run notebooks/dye_db.py       # Fluorophore / dye database
uv run marimo run notebooks/markers_db.py   # Cell marker database
```

### 🛠 Scripts

Utility scripts in `scripts/`:

| Script | Purpose |
|---|---|
| `simple_serve.py` | Serve the `db/` output directory over HTTP (local BFF testing) |

```bash
uv run scripts/simple_serve.py
```

## Getting Started

### Installation

Choose one of the following setup methods:

#### With `uv` (recommended)
```bash
git clone https://github.com/MMV-Lab/ambiom-bff-portals
uv sync
```

#### With `venv`
```bash
git clone https://github.com/MMV-Lab/ambiom-bff-portals
python -m venv .venv
# activate env (os dependent)
source .venv/bin/activate  # on Linux/macOS
# .venv\Scripts\activate  # on Windows
pip install -r requirements.txt
```

#### With `conda`
```bash
git clone https://github.com/MMV-Lab/ambiom-bff-portals
conda create -n ambiom-bff python=3.12
conda activate ambiom-bff
pip install -r requirements.txt
```

### Running the application

1. Configure path mappings and output URL (see **Customization** below)
2. Run the desired component using the commands in **Main Components** above

## Project Structure

```
notebooks/      Marimo notebooks (uploader, processor, reexport, DB helpers)
src/            Core library (adapters, config, metadata parsing, image utils)
  metadata_adapters/  One module per microscope type
scripts/        Standalone utility scripts
data/           Raw microscopy data (not committed)
db/             Generated output (CSV, OME-TIFF, OME-Zarr, thumbnails)
resources/      Reference data (dye/marker download lists)
```

## Customization

### Path mapping — `src/config.py`

The uploader accepts Windows UNC paths (as copied from the file server) and converts them to local Linux mount points using `PATH_MAPPING`:

```python
PATH_MAPPING = {
    PureWindowsPath(r"\\ambiom-fs1.isas.de\ambiom_storage"): Path("/mnt/eternus/"),
}
```

Add or update entries to match your own file-server layout.

### Output URL — `src/config.py`

`BASE_URL` controls the root URL embedded in the BFF CSV for served files:

```python
BASE_URL = "http://localhost:8000"   # local testing with simple_serve.py
# BASE_URL = "https://your-server.example.com"  # production deployment
```

After changing `BASE_URL`, run `bff_reexport` to regenerate the CSV with updated paths (no reprocessing needed).

### Experiment metadata dropdowns — `src/metadata_config.py`

`EXPERIMENT_METADATA_OPTIONS` controls the choices shown in the uploader for fields such as **Host**, **Cell Line**, **Location**, and **Treatment**. Extend any list or add new keys to match your experimental vocabulary:

```python
EXPERIMENT_METADATA_OPTIONS: dict[str, list[str]] = {
    "Host": ["Human", "Mouse", ...],
    "Cell Line": ["hMSCs", "HeLa", ...],
    ...
}
```

### Adding a new microscope adapter — `src/metadata_adapters/`

Each microscope type is handled by an adapter class that implements the `MetadataAdapter` protocol (see `src/metadata_adapters/__init__.py` for the full specification).

1. Create `src/metadata_adapters/my_scope.py` and implement the required methods:
   - `selection_mode` (`"file"` or `"directory"`)
   - `accepted_suffixes`
   - `resolve_file(selection)` → the concrete file to open
   - `load(path)` → `BioImage`
   - `extract(path)` → dict with all canonical fields

2. Register the adapter in `ADAPTER_REGISTRY` inside `src/metadata_adapters/__init__.py`:

```python
from src.metadata_adapters.my_scope import MyScopeAdapter

ADAPTER_REGISTRY = {
    ...,
    "My Scope Model [location]": MyScopeAdapter,
}
```

The new entry will appear automatically in the uploader's microscope dropdown.

## Requirements

All dependencies are managed through `uv` and defined in `pyproject.toml`.
