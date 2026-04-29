import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium", app_title="ISAS BFF Processor")

with app.setup:

    from pathlib import Path

    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    import polars as pl
    import marimo as mo
    import traceback
    from datetime import datetime
    import random
    import string

    from tqdm import tqdm

    from src.config import (
        CSV_DIR,
        TIME_STAMP_FORMAT,
        BASE_URL,
        ZARR_DIR,
        THUMBNAIL_DIR,
    )
    from src.processing import process_images
    from src.metadata_config import CHANNEL_LIST_SEP, CHANNEL_LIST_TO_FLAT
    from src.metadata_adapters import ADAPTER_REGISTRY


@app.cell
def _():
    title = mo.hstack(
        [
            mo.image(src="resources/ISAS_Logo.svg", width=70),
            mo.md("# ISAS BFF Processor").center(),
        ],
        justify="start",
        align="center",
    )

    body_text = mo.md(""" 

    """)

    mo.output.append(mo.vstack([title, body_text], align="center"))

    print(f"-- Running as {mo.app_meta().mode}")
    return


@app.cell
def _():
    _text = mo.md("""
    # Select CSV for processing \n This will automatically generate the following:
    - OME-TIFF with OME-compliant metadata
    - OME-ZARR (v0.5)
    - Thumbnails (jpeg format) for BFF visualization
    - XML files with all the OME metadata extracted
    """)


    folder_explorer = mo.ui.file_browser(
        initial_path=CSV_DIR,
        multiple=True,
        restrict_navigation=False,
    ).form()

    mo.vstack(
        [_text, folder_explorer],
        align="start",
        justify="space-around",
        gap=1,
        heights=[0.1, 1],
    )
    return (folder_explorer,)


@app.cell
def _(folder_explorer):
    if mo.app_meta().mode in ("script",):
        csv_paths = [
            f for f in CSV_DIR.glob("*.csv") if not f.name.startswith("BFF_")
        ]
        print("Analysing the following CSVs:")
        print(csv_paths)
    else:
        mo.stop(
            folder_explorer.value is None,
            mo.md("Submit the previous form to continue").callout("danger"),
        )

        # Get all paths from folder_explorer
        csv_paths = [
            item.path
            for item in folder_explorer.value
            if not Path(item.path).name.startswith("BFF_")
        ]
    return (csv_paths,)


@app.cell
def _():
    _text = mo.md("""
    # Preview of the files that will be processed:
    """)

    _text
    return


@app.cell
def _(csv_paths):
    df_list = [pl.read_csv(path) for path in csv_paths]

    # Merge CSVs from different microscope types with potentially different schemas.
    # E.g. Blaze includes "Channel Exposure Time [ms]" but Confocal may not.
    # diagonal_relaxed fills missing columns with null automatically.
    df = pl.concat(df_list, how="diagonal_relaxed")

    # Expand pipe-separated list columns into flat "Channel N X" columns.
    _list_cols = [c for c in CHANNEL_LIST_TO_FLAT if c in df.columns]
    if _list_cols:
        _max_ch = max(
            df.select(
                pl.col(c).str.split(CHANNEL_LIST_SEP).list.len().max()
            ).item()
            for c in _list_cols
        )
        df = df.with_columns(
            [
                pl.col(c)
                .str.split(CHANNEL_LIST_SEP)
                .list.get(i, null_on_oob=True)
                .alias(CHANNEL_LIST_TO_FLAT[c].format(i=i))
                for c in _list_cols
                for i in range(_max_ch)
            ]
        ).drop(_list_cols)

    df = df.rename(
        {
            "File Name": "old_File Name",
            "User Source Path": "old_User Source Path",
            "Server Path": "old_Server Path",
        }
    )

    # Build BFF-required URL columns from config.
    # To switch from localhost → public: update BASE_URL in config.py and re-run bff_reexport.
    df = df.with_columns(
        [
            pl.col("uuid").alias("File Name"),
            (
                pl.lit(f"{BASE_URL}/{ZARR_DIR.name}/")
                + pl.col("uuid")
                + pl.lit(".ome.zarr")
            ).alias("File Path"),
            (pl.col("uuid") + pl.lit(".ome.zarr")).alias("File Path Relative"),
            (
                pl.lit(f"{BASE_URL}/{THUMBNAIL_DIR.name}/")
                + pl.col("uuid")
                + pl.lit(".jpg")
            ).alias("Thumbnail"),
            (pl.col("uuid") + pl.lit(".jpg")).alias("Thumbnail Relative"),
        ]
    )

    other_cols = [
        col
        for col in df.columns
        if col
        not in [
            "File Name",
            "File Path",
            "File Path Relative",
            "Thumbnail",
            "Thumbnail Relative",
            "old_File Name",
            "old_User Source Path",
            "old_Server Path",
        ]
    ]
    df = df.select(
        ["File Name", "File Path", "File Path Relative"]
        + other_cols
        + [
            "Thumbnail",
            "Thumbnail Relative",
            "old_File Name",
            "old_User Source Path",
            "old_Server Path",
        ]
    )
    return (df,)


@app.cell
def _(df):
    mo.ui.table(df, show_download=False)
    return


@app.cell
def _():
    _text = mo.md(""" ### Press the following button to start the processing:

    """)

    start_processing_button = mo.ui.run_button(
        kind="warn", label="**Start Processing**"
    )

    mo.vstack(
        [_text, start_processing_button],
        align="center",
        justify="space-around",
        gap=1,
        heights=[0.1, 1],
    ).callout("warn")
    return (start_processing_button,)


@app.cell
def _(df, start_processing_button):
    # PROCESS EVERYTHING
    if mo.app_meta().mode in ("script",):
        with tqdm(total=len(df), desc="Processing") as pbar:
            for row in df.iter_rows(named=True):
                input_path = row["old_Server Path"]
                uuid = row["uuid"]
                adapter = ADAPTER_REGISTRY[row["Microscope Type"]]()
                scene_index = row.get("Scene Index")

                pbar.set_description(f"Processing: {uuid}")

                success, error = process_images(
                    input_path, uuid, adapter, scene_index=scene_index
                )

                if not success:
                    print(f"Failed to process {input_path}:")
                    traceback.print_exception(
                        type(error), error, error.__traceback__
                    )
                    pbar.update(1)
                    continue

                pbar.update(1)
            done_processing = True

    else:
        mo.stop(start_processing_button.value == False)

        _df = df

        with mo.status.progress_bar(
            total=len(_df), show_eta=False, show_rate=False
        ) as progres_bar:
            for row in _df.iter_rows(named=True):
                input_path = row["old_Server Path"]
                uuid = row["uuid"]
                adapter = ADAPTER_REGISTRY[row["Microscope Type"]]()
                scene_index = row.get("Scene Index")

                progres_bar.update(0, subtitle=f"Processing: {uuid}")

                success, error = process_images(
                    input_path, uuid, adapter, scene_index=scene_index
                )

                if not success:
                    mo.output.append(f"Failed to process {input_path}:")
                    traceback.print_exception(
                        type(error), error, error.__traceback__
                    )
                    continue

                progres_bar.update(1)

        done_processing = True
    return (done_processing,)


@app.cell
def _(df, done_processing):
    # SAVE CSV
    mo.stop(done_processing == False)

    csv_name: str = (
        "BFF_"
        + datetime.now().strftime(TIME_STAMP_FORMAT)
        + "-"
        + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
        + ".csv"
    )

    df.write_csv(CSV_DIR / csv_name)
    return


if __name__ == "__main__":
    app.run()
