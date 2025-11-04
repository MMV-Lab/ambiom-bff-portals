import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")

with app.setup:
    import polars as pl
    from pathlib import Path
    import marimo as mo

    from PIL import Image
    import numpy as np
    import jpype
    import scyjava
    from datetime import datetime

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

    from ambiom_bff_uploader import (
        convert_windows_to_linux_path,
        convert_linux_to_windows_path,
        generate_thumbnail,
    )

    from ambiom_bff_uploader import (
        PATH_MAPPING,
        TMP_PATH,
        OUTPUT_DIR,
        MAX_THUMBNAIL_SIZE,
        CSV_DIR,
        THUMBNAIL_DIR,
        ZARR_DIR,
        TIFF_DIR,
        XML_DIR,
    )


@app.cell
def _():
    folder_explorer = mo.ui.file_browser(
        initial_path=CSV_DIR,
        multiple=True,
        restrict_navigation=False,
    ).form()

    folder_explorer
    return (folder_explorer,)


@app.cell
def _(folder_explorer):
    mo.stop(
        folder_explorer.value is None,
        mo.md("Submit the previous form to continue").callout("warn"),
    )

    # Get all paths from folder_explorer
    csv_paths = [
        item.path
        for item in folder_explorer.value
        if not Path(item.path).name.startswith("BFF_")
    ]

    csv_paths
    return (csv_paths,)


@app.cell
def _(csv_paths):
    df = pl.concat([pl.read_csv(path) for path in csv_paths])

    df
    return (df,)


@app.function
def process_images(input_path_str: str, uuid: str):
    try:
        input_path = Path(input_path_str).resolve()
        if not input_path.exists() or not input_path.is_file():
            raise ValueError(f"{input_path} doesn't exists")

        img = BioImage(input_path_str, use_plugin_cache=True)

        # ------------------ FIX OME-XML ------------------

        single_image_ome = OmeTiffWriter.build_ome(
            data_shapes=[img.shape],
            data_types=[img.dtype],
            dimension_order=[img.dims.order],
            # [img.channel_names],
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
        out_ome.images[0].description = img.ome_metadata.images[0].description

        # ------------------ OME-XML SAVE ------------------

        _out_xml_path = XML_DIR / f"{uuid}.xml"

        with open(_out_xml_path, "w") as f:
            f.write(out_ome.to_xml())

        # ------------------ THUMBNAIL ------------------

        tn = generate_thumbnail(img)

        num_channels = tn.shape[0] if len(tn.shape) == 3 else 1

        if num_channels > 3:
            # Keep only first 3 channels as RGB
            tn = tn[:3, :, :]
        elif num_channels == 2:
            # Keep first 2 channels, add black channel as third
            black_channel = np.zeros_like(tn[0:1, :, :])
            tn = np.vstack([tn, black_channel])
        elif num_channels == 1:
            # Keep as single channel (grayscale)
            tn = tn[0, :, :]

        # Convert to PIL Image and save
        if len(tn.shape) == 2:
            # Grayscale
            pil_image = Image.fromarray(tn, mode="L")
        else:
            # RGB
            tn_rgb = np.transpose(tn, (1, 2, 0)).astype(np.uint8)
            pil_image = Image.fromarray(tn_rgb, mode="RGB")

        # Save thumbnail
        _img_tn_path = THUMBNAIL_DIR / f"{uuid}.jpg"
        pil_image.save(_img_tn_path)

        # ------------------ ZARR ------------------

        _img_ome_zarr = ZARR_DIR / f"{uuid}.ome.zarr"

        img_da = img.dask_data
        img_da_shape = img_da.shape

        factors = [1, 4, 16, 32]
        level_shapes = [
            img_da_shape[:2] + tuple(max(x // f, 1) for x in img_da_shape[2:])
            for f in factors
        ]

        ZARR_writer = OMEZarrWriter(
            store=_img_ome_zarr, level_shapes=level_shapes, dtype=img_da.dtype
        )
        ZARR_writer.write_full_volume(img_da)

        # ------------------ TIFF ------------------

        _img_ome_tiff_path = TIFF_DIR / f"{uuid}.ome.tiff"

        TIFF_writer = OmeTiffWriter.save(
            data=img.dask_data,
            uri=_img_ome_tiff_path,
            dim_order=img.dims.order,
            ome_xml=out_ome,
            physical_pixel_sizes=img.physical_pixel_sizes,
        )

        return True
    except Exception as e:
        print(f"Error processing {input_path_str}, {uuid}: {e}")
        return False


@app.cell
def _(df):
    from tqdm import tqdm

    results = []

    for row in tqdm(
        df.iter_rows(named=True), total=len(df), desc="Processing images"
    ):
        result = process_images(row["Internal File Path"], row["uuid"])
        results.append(result)

    df_new_test = df.with_columns(
        pl.Series("processing_status", results, dtype=pl.Boolean)
    )
    return


@app.cell
def _():
    # img = BioImage(
    #     image="/mnt/eternus/users/Davide/mmv-bff/data/AG29/221031_AG-029_A1_zoom4-1_z5_16-47-53/16-47-53_AG-029_A1_zoom4-1_z5_Blaze_C00_xyz-Table Z0000.ome.tif"
    # )


    # single_image_ome = OmeTiffWriter.build_ome(
    #     data_shapes=[img.shape],
    #     data_types=[img.dtype],
    #     dimension_order=[img.dims.order],
    #     # [img.channel_names],
    #     physical_pixel_sizes=[img.physical_pixel_sizes],
    # )

    # out_ome = img.ome_metadata.model_copy()
    # out_ome.images = single_image_ome.images

    # # reconstreuct manufacturer ??
    # out_ome.images[0].annotation_refs = img.ome_metadata.images[0].annotation_refs
    # out_ome.images[0].acquisition_date = img.ome_metadata.images[
    #     0
    # ].acquisition_date
    # out_ome.images[0].description = img.ome_metadata.images[0].description
    return


if __name__ == "__main__":
    app.run()
