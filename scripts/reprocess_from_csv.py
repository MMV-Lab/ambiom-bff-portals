"""
Standalone reprocessing script.

Reads an existing metadata CSV (produced by bff_uploader) and re-runs the
processing pipeline (OME-TIFF, OME-ZARR, thumbnail, XML) for every row.

Usage
-----
    uv run python notebooks/reprocess_from_csv.py path/to/metadata.csv
    uv run python notebooks/reprocess_from_csv.py path/to/metadata.csv --workers 4

The script uses ``old_Server Path`` as the source file and ``uuid`` as the
output identifier.  The Blaze adapter is assumed for all rows.

Rows whose outputs already exist on disk are skipped (idempotent).
"""

import argparse
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import polars as pl
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.processing import process_images


def _worker(input_path: str, uuid: str) -> tuple[str, str, bool, Exception | None]:
    """Top-level function so it can be pickled by ProcessPoolExecutor."""
    # Each worker creates its own adapter to avoid cross-process sharing issues.
    from src.metadata_adapters.blaze import BlazeAdapter
    adapter = BlazeAdapter()
    success, error = process_images(input_path, uuid, adapter, overwrite=False)
    return input_path, uuid, success, error


def main(csv_path: Path, max_workers: int) -> None:
    df = pl.read_csv(csv_path)

    required_cols = {"uuid", "old_Server Path"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"ERROR: CSV is missing required columns: {missing}", file=sys.stderr)
        sys.exit(1)

    rows = df.select(["uuid", "old_Server Path"]).iter_rows(named=True)
    total = len(df)

    failed: list[str] = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_worker, row["old_Server Path"], row["uuid"]): row["uuid"]
            for row in rows
        }

        with tqdm(total=total, desc="Reprocessing") as pbar:
            for future in as_completed(futures):
                input_path, uuid, success, error = future.result()
                if not success:
                    failed.append(input_path)
                    tqdm.write(f"\nFailed: {input_path}")
                    if error is not None:
                        tqdm.write("".join(
                            traceback.format_exception(type(error), error, error.__traceback__)
                        ))
                pbar.set_postfix(failed=len(failed))
                pbar.update(1)

    print(f"\nDone. {total - len(failed)}/{total} succeeded.")
    if failed:
        print(f"Failed ({len(failed)}):")
        for f in failed:
            print(f"  {f}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reprocess images from a metadata CSV.")
    parser.add_argument("csv", type=Path, help="Path to the metadata CSV file.")
    parser.add_argument(
        "--workers",
        type=int,
        default=16,
        help="Number of parallel worker processes (default: 4). "
             "Reduce if you run out of memory.",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    main(args.csv, args.workers)
