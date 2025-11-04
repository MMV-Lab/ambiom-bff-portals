import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")

with app.setup:
    # Initialization code that runs before all other cells

    from pathlib import Path, PureWindowsPath
    import jpype
    import scyjava

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
    import pandas as pd
    import numpy as np
    import polars as pl
    import xarray as xr

    import xml.etree.ElementTree as ET
    import re
    from functools import wraps
    from typing import Callable, Union, Any

    import plotly.express as px

    import marimo as mo
    import uuid
    from datetime import datetime
    import random
    import string

    # ================ CUSTOM CONSTANTS ================


    TMP_PATH = Path("tmp").resolve()
    TMP_PATH.mkdir(parents=True, exist_ok=True)

    PATH_MAPPING = {
        PureWindowsPath(r"\\ambiom-fs1.isas.de\ambiom_storage"): Path(
            "/mnt/eternus/"
        ),
        # PureWindowsPath(r"\\do1-fs-iota.isas.de\bio-img-raw"): # N.A.,
        # PureWindowsPath(r"L:\Research"): None, # AMBIOM GROUP\BioImaging-RO
    }

    DYE_DB = pl.read_parquet("public/dyes.parquet")
    MARKER_DB = pl.read_parquet("public/markers.parquet")


    OUTPUT_DIR = Path("db").resolve()
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

    MAX_THUMBNAIL_SIZE = 512


@app.cell
def _():
    # metadata_stack = mo.hstack(
    #     [
    #         mo.ui.dropdown(
    #             options=DYE_DB["Dye"],
    #             value="Brilliant Violet 480",
    #             searchable=True,
    #             allow_select_none=False,
    #             label="Dye:",
    #         ),
    #         mo.ui.dropdown(
    #             options=MARKER_DB["marker"],
    #             value="CD31",
    #             searchable=True,
    #             allow_select_none=False,
    #             label="Marker:",
    #         ),
    #     ],
    #    justify="space-around"
    # )

    # metadata_stack
    return


@app.cell
def _():
    title = mo.hstack(
        [
            mo.image(src="public/ISAS_Logo.svg", width=70),
            mo.md("# ISAS BFF Uploader ").center(),
        ],
        justify="start",
        align="center",
    )

    body_text = mo.md(""" 
     This Web Portal is created by the [AMBIOM Team](https://mmv-lab.github.io/) at [*ISAS – Leibniz-Institut für Analytische Wissenschaften*](https://www.isas.de/en) in Dortmund (Germany). 

    """).center()

    mo.vstack([title, body_text])
    return


@app.cell
def _():
    input_form = (
        mo.md("""

            **Users needs to input the path to explore** 

            On a *Windows PC*:

            - Open your Windows Explorer

            - Navigate to the folder in which multiple raw acquisition are collected.

            - From the top bar, copy the address of the folder

            - Paste here the **PATH**: 

            {input_path}

            In the next step you will be able to select the folders accordingly 

            /// details | If you need further help follow this tutorial
                type: info

            ![Tutorial Windows Path](public/tutorial_gif.gif)
            ///



        """)
        .batch(
            input_path=mo.ui.text(
                full_width=True, placeholder="Directory to Raw Data"
            ),
        )
        .form(show_clear_button=True, bordered=True)
    )

    mo.vstack([mo.md("# 1) Input Folder Form"), input_form])
    return (input_form,)


@app.cell
def _(input_form):
    input_form_output = mo.md("")
    converted_path = None

    if input_form.value:
        if input_form.value["input_path"] == "":
            input_form_output = mo.md("Empty Path").callout("danger")
        else:
            converted_path = convert_windows_to_linux_path(
                input_form.value["input_path"]
            )
            if converted_path:
                input_form_output = mo.md(f"""Correctly Processed Input Path

                    **PROCEED TO NEXT STEP**

                """).callout("success")

            #             Original Windows Path:

            # `{input_form.value["input_path"]}`

            # Converted Path:

            # `{converted_path}`

            else:
                input_form_output = mo.vstack(
                    [
                        mo.md("""The Windows path provided does not match any specified mapping.

                Here's the list of already implemented mappings:


                """),
                        list(PATH_MAPPING.keys()),
                    ]
                ).callout("danger")

    input_form_output
    return (converted_path,)


@app.cell
def _(converted_path):
    mo.stop(converted_path == None)


    folder_explorer = mo.ui.file_browser(
        initial_path=converted_path,
        multiple=True,
        selection_mode="directory",
        restrict_navigation=True,
    )

    folder_submit = mo.ui.run_button(kind="warn", label="**Process**")

    ome_tiff_multichannel_switch = mo.ui.switch(label="OME-TIFF (Single File)")
    ome_tiff_singlechannels_switch = mo.ui.switch(
        label="OME-TIFFs (Separate Channels)"
    )
    ome_zarr_switch = mo.ui.switch(label="OME-ZARR")


    mo.vstack(
        [
            mo.md("""# 2) Select Folders to process 
            """),
            folder_explorer,
            # mo.vstack(
            #     [
            #         mo.md(""" Convert image acquisitions to:
            # (Leave both turned off for no conversion - only extract metadata)"""),
            #         ome_tiff_multichannel_switch,
            #         ome_tiff_singlechannels_switch,
            #         ome_zarr_switch,
            #     ]
            # ).callout("info"),
            folder_submit,
        ]
    )
    return folder_explorer, folder_submit


@app.cell
def _(folder_explorer, folder_submit):
    mo.stop(folder_submit.value == False)
    metadata_collection_done = False

    complete_list_metadata = []
    bioimage_list = []

    with mo.status.progress_bar(
        total=len(folder_explorer.value),
        title="Gathering Metadata...",
        completion_title="🎉Done",
        completion_subtitle="All Set!",
    ) as bar:
        for folder_explorer_element in folder_explorer.value:
            input_dir = Path(folder_explorer_element.path)
            if any(item.is_dir() for item in input_dir.iterdir()):
                mo.output.append(mo.md(f"`{input_dir.name}` has subdirectories!"))
                bar.update(subtitle=f"{input_dir.name}")
                continue

            if sorted(input_dir.glob("*.ome.tif")) == []:
                mo.output.append(mo.md(f"`{input_dir.name}` no file found!"))
                bar.update(subtitle=f"{input_dir.name}")
                continue

            first_file = sorted(input_dir.glob("*.ome.tif"))[0]
            input_image = BioImage(first_file, use_plugin_cache=True)

            thumbnail = generate_thumbnail(input_image)
            metadata = blaze_extract_metadata(first_file)

            bioimage_list.append(thumbnail)
            complete_list_metadata.append(metadata)

            # output_ome = blaze_single_image_ome(input_image, str(input_dir.name))

            # mo.output.append(input_image.ome_metadata.model_copy())
            bar.update(subtitle=f"{input_dir.stem}")

    metadata_collection_done = True

    metadata_df = pd.DataFrame.from_dict(complete_list_metadata)
    metadata_df["Internal File Path"] = metadata_df["File Path"]
    metadata_df["File Path"] = metadata_df["File Path"].map(
        convert_linux_to_windows_path
    )
    return bioimage_list, metadata_collection_done, metadata_df


@app.cell
def _(bioimage_list, metadata_collection_done):
    mo.stop(metadata_collection_done == False)

    _plotly_fig = px.imshow(
        bioimage_list[0],
        facet_col="C",
        binary_string=True,
        aspect="equal",
        contrast_rescaling="minmax",
        color_continuous_scale="magma",
        height=400,
    )

    _C = bioimage_list[0].coords["C"].size

    dye_marker_dict = mo.ui.dictionary(
        {
            "dye": mo.ui.array(
                [
                    mo.ui.dropdown(
                        options=DYE_DB["Dye"],
                        value="Brilliant Violet 480",
                        searchable=True,
                        allow_select_none=False,
                        label="Dye:",
                    )
                    for _ in range(_C)
                ]
            ),
            "marker": mo.ui.array(
                [
                    mo.ui.dropdown(
                        options=MARKER_DB["marker"],
                        value=None,
                        searchable=True,
                        allow_select_none=True,
                        label="Marker:",
                    )
                    for _ in range(_C)
                ]
            ),
        }
    )


    channels = mo.ui.array(
        [mo.ui.text(label="Channel " + str(i)) for i in range(_C)]
    )


    # metadata_array = mo.ui.array(
    #     [
    #         mo.ui.dropdown(
    #             options=DYE_DB["Dye"],
    #             value="Brilliant Violet 480",
    #             searchable=True,
    #             allow_select_none=False,
    #             label="Dye:",
    #         ),
    #         mo.ui.dropdown(
    #             options=MARKER_DB["marker"],
    #             value="CD31",
    #             searchable=True,
    #             allow_select_none=False,
    #             label="Marker:",
    #         ),
    #     ],
    # )

    # allow_select_none=True
    manual_metadata_dict = mo.ui.dictionary(
        {
            "Host": mo.ui.dropdown(options=["Human", "Mouse"], label="Host:"),
            "Cell Line": mo.ui.dropdown(
                options=["hMSCs", "HUVEC", "E. Coli", "Biopsy"], label="Cell Line:"
            ),
            "Location": mo.ui.dropdown(
                options=[
                    "Liver",
                    "Knee Joint",
                    "Heart",
                    "Lung",
                    "Bladder",
                    "Peritoneum",
                    "Colon",
                ],
                label="Location:",
            ),
            "Treatment": mo.ui.dropdown(
                options=["CTRL", "WT", "Disease"],
                label="Treatment or Disease Model:",
            ),
            "Timepoint (@ Treatment)": mo.ui.dropdown(
                options=["0 days", "2 days", "7 days"],
                allow_select_none=True,
                label="Timepoint (@ Treatment):",
            ),
            "Additional Comments": mo.ui.text(label="Additional Comments:"),
        }
    )

    manual_metadata_submit = mo.ui.run_button(kind="warn", label="**Submit**")

    dye_marker_stack = mo.md(
        f"### Fill in the required metadata for each of the {_C} Channels:\n\n"
        + "\n\n".join(
            # Iterate over the elements and embed them in markdown
            [
                f" **{i}.** {dye} {marker}"
                for i, (dye, marker) in enumerate(
                    zip(dye_marker_dict["dye"], dye_marker_dict["marker"])
                )
            ]
        )
        + ""
    )

    final = mo.vstack(
        [
            mo.md("""# 3) Fill In Manual Metadata  """),
            mo.ui.plotly(_plotly_fig),
            dye_marker_stack,
            mo.md("-------------"),
            mo.md("### Please insert the Experiment Metadata:"),
            manual_metadata_dict.vstack(),
            manual_metadata_submit,
        ]
    )

    final
    return dye_marker_dict, manual_metadata_dict, manual_metadata_submit


@app.cell
def _(
    dye_marker_dict,
    manual_metadata_dict,
    manual_metadata_submit,
    metadata_df,
):
    mo.stop(manual_metadata_submit.value == False)

    channel_dict = {
        f"Channel {i}": f"{m} - {d}" if m else d
        for i, (m, d) in enumerate(
            zip(dye_marker_dict.value["marker"], dye_marker_dict.value["dye"])
        )
    }

    final_df = metadata_df.assign(**manual_metadata_dict.value)
    final_df = final_df.assign(**channel_dict)

    final_df["uuid"] = [uuid.uuid4() for _ in range(len(final_df))]

    # metadata_csv_string = final_df.to_csv(None, index=False)

    # csv_download = mo.download(
    #     data=metadata_csv_string,
    #     filename="data.csv",
    #     mimetype="text/csv",
    #     label="Download CSV",
    # )

    #         mo.md("""

    #         You can now download the final CSV file containing all the metadata.

    #         The requested output files will also be placed in the `output` directory.

    #         🎉 You can now open the [BioFileFinder app](https://bff.allencell.org/app) and upload your CSV file!

    #         <p style="text-align: center;"> {download_button} </p>


    # """).batch(download_button=csv_download).center().callout("success"),


    final_submit = mo.ui.run_button(kind="warn", label="**Submit**")

    mo.vstack(
        [
            mo.md("""# 4) Submit to Metadata Storage"""),
            mo.md("Preview your final metadata here:"),
            final_df.drop(columns="File Path"),
            final_submit,
        ],
    )
    return final_df, final_submit


@app.cell
def _(final_df, final_submit):
    mo.stop(final_submit.value == False)

    csv_name: str = (
        "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
        + "-"
        + str(datetime.now().isoformat())
        + ".csv"
    )

    final_df.to_csv(CSV_DIR / csv_name, index=False)

    mo.md("""
            🎉 Congratulations! Your files have been correctly stored 🥰

    """).center().callout("success")
    return


@app.cell
def _():
    # TEST PATH

    # r"\\ambiom-fs1.isas.de\ambiom_storage\users\Davide\mmv-bff\data\AG29"

    # r"L:\Research\Christiane"
    return


@app.cell
def _():
    # graphical_elements = mo.ui.dictionary(
    #     {
    #         "file_selection_form": mo.ui.file_browser(initial_path=tmp_path,restrict_navigation=True).form(loading=True),
    #         #"file_selection_form_output": mo.md("").form(),
    #     }
    # )


    # accordion_layout = mo.accordion(
    #     {
    #         "1) Where is your Raw data?": mo.vstack(
    #             [input_form, input_form_output]
    #         ),
    #         "2) Select Folders to analyze": mo.ui.file_browser(initial_path=tmp_path,restrict_navigation=True).form(loading=True),
    #         "3) Set Microscope Settings": mo.md("Nothing!"),
    #         "4) Export Data to Disk & BFF": mo.md("Nothing!"),
    #     },
    #     multiple=True
    # )
    return


@app.function
def convert_windows_to_linux_path(windows_path_str: str) -> Path | None:
    """
    Converts a Windows path string to a Linux path string based on the global PATH_MAPPING.

    Args:
        windows_path_str: The input Windows path string.

    Returns:
        The converted Linux path string (with forward slashes) if a mapping is found,
        otherwise None.
    """
    input_windows_path = PureWindowsPath(windows_path_str)
    converted_path = None

    # Iterate through the mappings in the global PATH_MAPPING dictionary
    for win_root, linux_root in PATH_MAPPING.items():
        # Check if the input path is a subpath of the current mapping's Windows root
        if input_windows_path.is_relative_to(win_root):
            # Get the portion of the path relative to the Windows root
            relative_path = input_windows_path.relative_to(win_root)

            if linux_root:
                # Join the Linux mount point with the relative path to get the final converted path
                converted_path = linux_root / relative_path
                break  # Exit the loop once a match is found

    if converted_path:
        return converted_path.absolute()
    else:
        return None


@app.function
def convert_linux_to_windows_path(linux_path: Union[str, Path]) -> str | None:
    """
    Converts a Linux path (string or Path object) to a Windows path string
    based on the global PATH_MAPPING.

    Args:
        linux_path: The input Linux path (as a string or pathlib.Path object).

    Returns:
        The converted Windows path string (with backslashes) if a mapping is found,
        otherwise None.
    """
    try:
        # Ensure we are working with a pathlib.Path object
        input_linux_path = Path(linux_path).resolve()
    except (TypeError, RuntimeError):
        return (
            None  # Handle potential invalid path inputs or resolution errors
        )

    converted_path = None

    # Iterate through the mappings in the global PATH_MAPPING dictionary
    for win_root, linux_root in PATH_MAPPING.items():
        # Check if the input path is a subpath of the current mapping's Linux root
        if input_linux_path.is_relative_to(linux_root):
            # Get the portion of the path relative to the Linux root
            relative_path = input_linux_path.relative_to(linux_root)

            # Join the Windows root with the relative path to get the final converted path
            converted_path = win_root / relative_path
            break  # Exit the loop once a match is found

    if converted_path:
        # Convert the PureWindowsPath object to a string for the final output
        return str(converted_path)
    else:
        return None


@app.function
def blaze_single_image_ome(img: BioImage, output_file_name):
    single_image_ome = OmeTiffWriter.build_ome(
        [(img.shape[1], img.shape[0], *img.shape[2:])],
        [img.dtype],
        ["CTZYX"],
        [img.channel_names],
        [str(output_file_name)],
        [img.physical_pixel_sizes],
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

    return out_ome


@app.function
def blaze_extract_metadata(image_path: Path) -> dict:
    image = BioImage(image_path, reader=bioio_bioformats.Reader)

    metadata_dict = {
        "Obj Magnification": "Blaze ObjectiveMagnification",
        "Obj NA": "ObjectiveNA",
        "Digital Zoom": "Blaze CurrentZoom",
        "Measurament TimeStamp": "MeasTime",
    }

    for key in metadata_dict.keys():
        if isinstance(metadata_dict[key], str):
            metadata_dict[key] = find_metadata_in_xml(
                image, metadata_dict[key]
            )

    for i in range(len(image.channel_names)):
        tmp_filter_dict = find_metadata_in_xml(image, f"Filter{i}")
        if (
            isinstance(tmp_filter_dict, dict)
            and "EmissionWL" in tmp_filter_dict
        ):
            metadata_dict[f"Channel {i} EXC [nm]"] = tmp_filter_dict[
                "ExcitationWL"
            ]
            metadata_dict[f"Channel {i} EM [nm]"] = tmp_filter_dict[
                "EmissionWL"
            ]
            metadata_dict[f"Channel {i} Exposure Time [ms]"] = tmp_filter_dict[
                "ExposureTime"
            ]
        else:
            metadata_dict[f"Channel {i} EXC [nm]"] = None
            metadata_dict[f"Channel {i} EM [nm]"] = None
            metadata_dict[f"Channel {i} Exposure Time [ms]"] = None

    metadata_dict = {
        "File Name": image_path.name,
        # 'File Name': image_path.parent.name,
        "File Path": str(image_path.resolve()),
        "Image Size (X,Y,Z) [pixels]": f"{image.dims.X},{image.dims.Y},{image.dims.Z}",
        "Pixel Size X": image.physical_pixel_sizes.X,
        "Pixel Size Y": image.physical_pixel_sizes.Y,
        "Pixel Size Z": image.physical_pixel_sizes.Z,
        "Number of Channels": len(image.channel_names),
        **metadata_dict,
    }

    return metadata_dict


@app.function
def clean_up_qname(input_str: str) -> str:
    """Remove XML namespace from qname."""
    return re.sub(r"{[^}]*}*", "", input_str)


@app.function
def handle_return_decorator(func: Callable) -> Callable:
    """
    Decorator to handle return values from XML metadata search.
    Standardizes the output format for dictionary and string returns.
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> Union[dict, str, None]:
        result = func(*args, **kwargs)
        if isinstance(result, dict):
            if len(result) == 1:
                return list(result.values())[0]
            else:
                return result
        if isinstance(result, str):
            return result
        return None

    return wrapper


@app.function
@handle_return_decorator
def find_metadata_in_xml(
    image: Any, text_to_search: str
) -> Union[str, dict, None]:
    """
    Searches for the first occurrence of text_to_search in qnames or fnames.

    Args:
        image: The BioImage object containing OME metadata.
        text_to_search: The text to search for in qnames and fnames.

    Returns:
        Union[str, dict, None]: The value as a string or dict if found, otherwise None.
    """
    try:
        xml_list = [
            xml_annotation
            for xml_annotation in image.ome_metadata.structured_annotations
        ]

        # Search in qnames (first annotation)
        if xml_list:
            for elem in xml_list[0].value.any_elements:
                # Handle elements with children
                if getattr(elem, "children", None):
                    for child in elem.children:
                        if text_to_search in clean_up_qname(
                            getattr(child, "qname", "")
                        ):
                            return child.attributes
                # Handle elements without children
                elif text_to_search in clean_up_qname(
                    getattr(elem, "qname", "")
                ):
                    return elem.attributes

        # Search in fnames (second annotation)
        if len(xml_list) > 1:
            for elem in xml_list[1].value.any_elements:
                if getattr(elem, "children", None):
                    for child in elem.children:
                        if text_to_search in child.attributes.get("fname", ""):
                            return child.attributes.get("Value", "")

    except Exception as e:
        print(f"Error during XML annotation search: {e}")

    return None


@app.cell
def _():
    # _input_dir = folder_explorer.value[0].path
    # _first_file = sorted(_input_dir.glob("*.ome.tif"))[0]


    # _input_image = BioImage(_first_file, use_plugin_cache=True)
    # # _output_ome = blaze_single_image_ome(_input_image, str(_input_dir.name))

    # ome = _input_image.ome_metadata

    # with open("ome_metadata_single.xml", "w") as f:
    #     f.write(blaze_single_image_ome(_input_image, "test.ome.tif").to_xml())

    # # result = find_metadata_in_xml(_input_image, "Filter0")
    # # print(f'{result} ({type(result)})')

    # # result = find_metadata_in_xml(_input_image, "FilterAxis")
    # # print(f'{result} ({type(result)})')

    # # result = find_metadata_in_xml(_input_image, "DataAxis3")
    # # print(f'{result} ({type(result)})')

    # # result = find_metadata_in_xml(_input_image, "Blaze NA")
    # # print(f'{result} ({type(result)})')

    # # result = find_metadata_in_xml(_input_image, "InstrumentMode")
    # # print(f'{result} ({type(result)})')

    # # result = find_metadata_in_xml(_input_image, "blah")
    # # print(f'{result} ({type(result)})')

    # # result = find_metadata_in_xml(_input_image, "Blaze ObjectiveMagnification")
    # # print(f'{result} ({type(result)})')

    # print(_input_image.channel_names)

    # result = find_metadata_in_xml(_input_image, "Filter0")
    # print(f'{result} ({type(result)})')

    # print(blaze_extract_metadata(_first_file))

    # with open("ome_metadata.xml", "w") as f:
    #     f.write(_input_image.ome_metadata.to_xml())
    return


@app.cell
def _():
    # ome.structured_annotations[0].to_xml()
    return


@app.cell
def _():
    # import neuroglancer


    # viewer = neuroglancer.Viewer()

    # with viewer.txn() as state:
    #     # x_path = "/mnt/eternus/users/Davide/mmv-bff/data/AG29/221031_AG-029_A1_zoom4-1_z5_16-21-00/16-21-00_AG-029_A1_zoom4-1_z5_Blaze_C00_xyz-Table Z0000.ome.tif"

    #     # x = BioImage(x_path, use_plugin_cache=True)

    #     # tmp = x.get_xarray_dask_stack()

    #     state.layers["dask"] = neuroglancer.ImageLayer(source=neuroglancer.LocalVolume(x_dask))

    # print(viewer)
    return


@app.cell
def _():
    # _x_path = "/mnt/eternus/users/Davide/mmv-bff/data/AG29/221031_AG-029_A1_zoom4-1_z5_16-21-00/16-21-00_AG-029_A1_zoom4-1_z5_Blaze_C00_xyz-Table Z0000.ome.tif"

    # x_bioio = BioImage(_x_path, use_plugin_cache=True)

    # test = x_bioio.dask_data

    # test_shape = test.shape

    # factors = [1, 4, 8, 16]

    # level_shapes = [
    #     test_shape[:2] + tuple(max(x // f, 1) for x in test_shape[2:])
    #     for f in factors
    # ]

    # print(level_shapes)

    # writer = OMEZarrWriter(store="temp.ome.zarr", level_shapes=level_shapes, dtype=test.dtype)
    # writer.write_full_volume(test)
    return


@app.function
def generate_thumbnail(input_image: BioImage):
    # Downsampling
    thumbnail = (
        input_image.get_xarray_dask_stack()
        .isel(Z=input_image.dims.Z // 2)
        .squeeze(drop=True)
    )

    # Progressively coarsen by 2 until X dimension is less than 512
    while thumbnail.sizes["X"] >= MAX_THUMBNAIL_SIZE:
        thumbnail = thumbnail.coarsen(X=2, Y=2).median()

    # Contrast enhancement
    vmin, vmax = thumbnail.quantile([0.01, 0.999], dim=["X", "Y"], skipna=True)
    thumbnail = thumbnail.clip(min=vmin, max=vmax)

    # Prevent division by zero using xarray.where
    denominator = vmax - vmin
    thumbnail = xr.where(
        denominator > 0,
        (thumbnail - vmin) / denominator * 255.0,
        128.0,  # default value when denominator is 0
    )

    thumbnail = thumbnail.fillna(0).astype(np.uint8)

    thumbnail_np = thumbnail.transpose("C", "Y", "X").compute().values

    return thumbnail_np


if __name__ == "__main__":
    app.run()
