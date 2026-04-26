from pathlib import Path, PureWindowsPath

# Resolve project root relative to this file so paths are CWD-independent
_PROJECT_ROOT = Path(__file__).parent.parent

PATH_MAPPING = {
    PureWindowsPath(r"\\ambiom-fs1.isas.de\ambiom_storage"): Path("/mnt/eternus/"),
    # PureWindowsPath(r"\\do1-fs-iota.isas.de\bio-img-raw"): # N.A.,
    # PureWindowsPath(r"L:\Research"): None, # AMBIOM GROUP\BioImaging-RO
}

OUTPUT_DIR = _PROJECT_ROOT / "db"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CSV_DIR = OUTPUT_DIR / "CSV"
CSV_DIR.mkdir(parents=True, exist_ok=True)

THUMBNAIL_DIR = OUTPUT_DIR / "THUMBNAIL"
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

ZARR_DIR = OUTPUT_DIR / "OME-ZARR"
ZARR_DIR.mkdir(parents=True, exist_ok=True)

TIFF_DIR = OUTPUT_DIR / "OME-TIFF"
TIFF_DIR.mkdir(parents=True, exist_ok=True)

XML_DIR = OUTPUT_DIR / "XML"
XML_DIR.mkdir(parents=True, exist_ok=True)

MAX_THUMBNAIL_SIZE = 1024

TIME_STAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"

# Base URL for serving processed data.
# Change this to the public URL when moving from local to deployed environment.
# Re-run bff_reexport.py afterwards to rebuild File Path / Thumbnail columns.
BASE_URL = "http://localhost:8000"

# TMP_PATH = _PROJECT_ROOT / "tmp"
# TMP_PATH.mkdir(parents=True, exist_ok=True)

