# AMBIOM tools for BFF

A tool for processing and uploading raw microscopy files to use with [BioFileFinder (BFF)](https://bff.allencell.org/) by the Allen Institute for Cell Science.

## Overview

This project provides utilities to extract metadata from raw microscopy files and prepare them for use with BioFileFinder. Everything is managed through [marimo](https://marimo.io/) notebooks and [uv](https://github.com/astral-sh/uv) for dependency management.

## Main Components

### `bff_uploader`

An interactive uploader that allows users to:
- Upload files from a Windows path
- Extract relevant metadata from raw microscopy files
- Add experimental data and annotations

**Development mode** (with editing capabilities):
```bash
uv run marimo edit src/bff_uploader.py
```

**User mode** (front-end only):
```bash
uv run marimo run src/bff_uploader.py
```

### `bff_processor`

Handles the conversion and storage of processed data. Can be launched as a standalone script:

```bash
uv run src/bff_processor.py
```

### Additional Tools

The project includes marimo notebooks for generating databases of:
- Cell markers
- Fluorophores/dyes

These can be found in the `src/` directory.

## Getting Started

1. Ensure you have [uv](https://github.com/astral-sh/uv) installed
2. Clone this repository
3. Run the desired component using the commands above

## Project Structure

- `src/` - Source code and marimo notebooks
- `data/` - Raw microscopy data
- `db/` - Generated databases and CSV files
- `public/` - Public assets

## Requirements

All dependencies are managed through `uv` and defined in `pyproject.toml`.
