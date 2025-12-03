import marimo

__generated_with = "0.18.1"
app = marimo.App(width="medium", app_title="ISAS BFF Processor")

with app.setup:
    import polars as pl
    from pathlib import Path
    import marimo as mo
    import traceback

    from PIL import Image
    import numpy as np
    import jpype
    import scyjava
    from datetime import datetime
    import random
    import string

    try:
        scyjava.config.endpoints.append("ome:formats-gpl:latest")
        scyjava.start_jvm()
        loci = jpype.JPackage("loci")
        loci.common.DebugTools.setRootLevel("WARN")
        print("Bio-Formats logging level set to WARN.")

    except ImportError:
        print("Could not import jpype or scyjava. Make sure they are installed.")
    except jpype.JException as e:
        print(f"An error occurred while trying to configure Java logging: {e}")


    from bioio import BioImage
    import bioio_bioformats
    from bioio_ome_tiff.writers import OmeTiffWriter
    from bioio_ome_zarr.writers import OMEZarrWriter

    from bff_uploader import (
        convert_windows_to_linux_path,
        convert_linux_to_windows_path,
        generate_rgb_thumbnail,
        generate_quick_preview,
    )

    from bff_uploader import (
        PATH_MAPPING,
        TMP_PATH,
        OUTPUT_DIR,
        MAX_THUMBNAIL_SIZE,
        CSV_DIR,
        THUMBNAIL_DIR,
        ZARR_DIR,
        TIFF_DIR,
        XML_DIR,
        TIME_STAMP_FORMAT,
    )

    from tqdm import tqdm



@app.cell
def _():
    title = mo.hstack(
        [
            mo.image(src="public/ISAS_Logo.svg", width=70),
            mo.md("# ISAS BFF Processor").center(),
        ],
        justify="start",
        align="center",
    )

    body_text = mo.md(""" 

    """)

    mo.vstack([title, body_text], align="center")
    
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

    df = pl.concat(df_list)

    df = df.rename({"File Name": "old_File Name", "File Path": "old_File Path"})

    # Add new columns based on ZARR directory and uuid for BFF
    df = df.with_columns(
        [
            pl.col("uuid").alias("File Name"),
            (
                pl.lit("http://localhost:8000/OME-ZARR/")
                + pl.col("uuid")
                + pl.lit(".ome.zarr")
            ).alias("File Path"),
            (
                pl.lit("http://localhost:8000/THUMBNAIL/")
                + pl.col("uuid")
                + pl.lit(".jpg")
            ).alias("Thumbnail"),
        ]
    )

    other_cols = [
        col
        for col in df.columns
        if col
        not in [
            "File Name",
            "Thumbnail",
            "old_File Name",
            "old_File Path",
            "Internal File Path",
        ]
    ]
    df = df.select(
        ["File Name"]
        + other_cols
        + ["Thumbnail", "Internal File Path", "old_File Name", "old_File Path"]
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


@app.function
def process_images(input_path_str: str, uuid: str):
    try:
        input_path = Path(input_path_str).resolve()
        if not input_path.exists() or not input_path.is_file():
            raise ValueError(f"{input_path} doesn't exists")

        img = BioImage(
            input_path_str,
            use_plugin_cache=True,
            reader=bioio_bioformats.Reader,
        )

        img_xr = img.xarray_dask_data

        # Drop useless dims
        img_xr = img_xr.squeeze(drop=True)
        img_xr_dims = "".join(img_xr.dims)
        img_physical_pixel_sizes = img.physical_pixel_sizes

        # ------------------ FIX OME-XML ------------------

        _out_xml_path = XML_DIR / f"{uuid}.xml"


        single_image_ome = OmeTiffWriter.build_ome(
            data_shapes=[img_xr.shape],
            data_types=[img_xr.dtype],
            dimension_order=[img_xr_dims],
            physical_pixel_sizes=[img.physical_pixel_sizes],
        )

        out_ome = img.ome_metadata.model_copy()
        out_ome.images = single_image_ome.images

        # reconstreuct manufacturer ??
        out_ome.images[0].annotation_refs = img.ome_metadata.images[
            0
        ].annotation_refs
        out_ome.images[0].acquisition_date = img.ome_metadata.images[
            0
        ].acquisition_date
        out_ome.images[0].description = img.ome_metadata.images[
            0
        ].description

        with open(_out_xml_path, "w") as f:
            f.write(out_ome.to_xml())

        # ------------------ THUMBNAIL ------------------

        _img_tn_path = THUMBNAIL_DIR / f"{uuid}.jpg"

        if not _img_tn_path.exists():
            thumbnail_xr = generate_quick_preview(img)
            pil_thumbnail, _ = generate_rgb_thumbnail(thumbnail_xr)
            pil_thumbnail.save(_img_tn_path)

        # ------------------ TIFF ------------------

        _img_ome_tiff_path = TIFF_DIR / f"{uuid}.ome.tiff"

        if not _img_ome_tiff_path.exists():
            TIFF_writer = OmeTiffWriter.save(
                data=img_xr.data,
                uri=_img_ome_tiff_path,
                dim_order=img_xr_dims,
                ome_xml=out_ome,
                physical_pixel_sizes=img_physical_pixel_sizes,
            )

        # ------------------ ZARR ------------------

        _img_ome_zarr = ZARR_DIR / f"{uuid}.ome.zarr"

        if not _img_ome_zarr.exists():
            level_shapes = [img_xr.shape]
            current_shape = img_xr.shape

            for level in range(1, 4):
                next_shape = tuple(
                    s // 2 if img_xr.dims[i] != "C" else s
                    for i, s in enumerate(current_shape)
                )
                level_shapes.append(next_shape)
                current_shape = next_shape

            ZARR_writer = OMEZarrWriter(
                store=_img_ome_zarr,
                level_shapes=level_shapes,
                dtype=img_xr.dtype,
                axes_names=list(img_xr.dims),
                physical_pixel_size=[1] + list(img.physical_pixel_sizes),
                axes_units=[None, "micrometer", "micrometer", "micrometer"],
            )
            ZARR_writer.write_full_volume(img_xr)

        return True, None
    except Exception as e:
        print(f"Error processing {input_path_str}, {uuid}:")
        traceback.print_exc()  # Prints full traceback immediately
        return False, e


@app.cell
def _(df, start_processing_button):
    # PROCESS EVERYTHING
    if mo.app_meta().mode in ("script",):

        with tqdm(total=len(_df), desc="Processing") as pbar:
            for row in _df.iter_rows(named=True):
                input_path = row["Internal File Path"]
                uuid = row["uuid"]

                pbar.set_description(f"Processing: {uuid}")

                success, error = process_images(input_path, uuid)

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
                input_path = row["Internal File Path"]
                uuid = row["uuid"]

                progres_bar.update(0, subtitle=f"Processing: {uuid}")

                success, error = process_images(input_path, uuid)

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


@app.cell
def _():
    # MOCKUP PROGRESS
    # import asyncio

    # mo.stop(start_processing_button.value == False)

    # for _ in mo.status.progress_bar(
    #     range(len(df)),
    #     title="Processing Images...",
    #     subtitle="Please wait",
    #     completion_title="🎉 Done",
    #     completion_subtitle="All Set!",
    #     show_eta=False,
    #     show_rate=False,
    # ):
    #     await asyncio.sleep(1)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
