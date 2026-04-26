#!/usr/bin/env python3
"""Download and extract sample data."""

import urllib.request
import zipfile
from pathlib import Path

# Configuration
url = "https://ambiomcloud.isas.de/index.php/s/PDfGrE8YNe9NkYY/download"
zip_path = Path("sample_data.zip")
extract_dir = Path("data")

try:
    # Create extract directory if it doesn't exist
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    # Download
    print("Downloading sample_data.zip...")
    urllib.request.urlretrieve(url, zip_path)
    print(f"Downloaded: {zip_path}")
    
    # Unzip
    print(f"Extracting to {extract_dir}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    print("Extraction complete")
    
    # Remove zip
    zip_path.unlink()
    print(f"Removed: {zip_path}")
    
except Exception as e:
    print(f"Error: {e}")
