import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium", app_title="ISAS BFF Uploader")

with app.setup:
    from pathlib import Path

    import pandas as pd
    import numpy as np
    import polars as pl

    import plotly.express as px

    import marimo as mo
    import uuid
    from datetime import datetime
    import random
    import string
    import time

    import anywidget
    import traitlets
    from user_agents import parse

    from src.config import (
        PATH_MAPPING,
        OUTPUT_DIR,
        MAX_THUMBNAIL_SIZE,
        CSV_DIR,
        TIME_STAMP_FORMAT,
    )
    from src.path_utils import (
        convert_windows_to_linux_path,
        convert_linux_to_windows_path,
    )
    from src.image_utils import generate_quick_preview
    from src.metadata_adapters import ADAPTER_REGISTRY
    from src.metadata_config import CHANNEL_LIST_SEP, EXPERIMENT_METADATA_OPTIONS

    DYE_DB = pl.read_parquet("public/dyes.parquet")
    MARKER_DB = pl.read_parquet("public/markers.parquet")


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
    This project originated as a companion tool to support the use of the open-source project [BioFileFinder](https://bff.allencell.org), enabling seamless metadata extraction and standardization for microscopy image datasets.
    """)

    mo.vstack([title, body_text], align="center")
    return


@app.cell
def _():
    input_form = (
        mo.md(r"""

            **Users needs to input the path to explore** 

            On a *Windows PC*:

            - Open your Windows Explorer

            - Navigate to the folder in which multiple raw acquisition are collected.

            - From the top bar, copy the address of the folder

            - Paste here the **PATH**: 

            {input_path}

            Select your **Microscope Type**:

            {microscope_type}

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
            microscope_type=mo.ui.dropdown(
                options=list(ADAPTER_REGISTRY.keys()),
                label="Microscope Type:",
            ),
        )
        .form(show_clear_button=True, bordered=True)
    )

    mo.vstack([mo.md("# 1) Input Folder Form"), input_form])
    return (input_form,)


@app.cell
def _():
    class ClientDetector(anywidget.AnyWidget):
        # Properly formatted ESM module for AnyWidget
        _esm = """
        export default {
            render({ model }) {
                model.set('ua', navigator.userAgent);
                model.save_changes();
            }
        }
        """
        ua = traitlets.Unicode("").tag(sync=True)


    detector = ClientDetector()
    detector
    return (detector,)


@app.cell
def _(detector):
    if detector:
        time.sleep(2)
        user = parse(detector.ua)
        mo.output.append(
            mo.md(
                f"You are using **{user.browser.family}** on **{user.os.family}**."
            )
        )
    return


@app.cell
def _(input_form):
    input_form_output = mo.md("")
    converted_path = None
    adapter = None

    if input_form.value:
        if input_form.value["input_path"] == "":
            input_form_output = mo.md("Empty Path").callout("danger")
        elif input_form.value["microscope_type"] is None:
            input_form_output = mo.md("Please select a Microscope Type").callout(
                "danger"
            )
        else:
            converted_path = convert_windows_to_linux_path(
                input_form.value["input_path"]
            )
            if converted_path:
                adapter = ADAPTER_REGISTRY[input_form.value["microscope_type"]]()
                input_form_output = mo.md(f"""Correctly Processed Input Path

                    **PROCEED TO NEXT STEP**

                """).callout("success")

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
    return adapter, converted_path


@app.cell
def _(adapter, converted_path):
    mo.stop(converted_path == None)

    _mode = adapter.selection_mode
    _suffixes = adapter.accepted_suffixes
    _heading = (
        "# 2) Select Folders to process"
        if _mode == "directory"
        else f"# 2) Select Files to process ({', '.join(_suffixes) if _suffixes else 'any'})"
    )

    folder_explorer = mo.ui.file_browser(
        initial_path=converted_path,
        multiple=True,
        selection_mode=_mode,
        restrict_navigation=False,
    )

    folder_submit = mo.ui.run_button(kind="warn", label="**Process**")


    mo.vstack(
        [
            mo.md(_heading),
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
def _(adapter, folder_explorer, folder_submit):
    mo.stop(folder_submit.value == False)
    metadata_collection_done = False

    complete_list_metadata = []
    bioimage_list = []
    _adapter = adapter

    with mo.status.progress_bar(
        total=len(folder_explorer.value),
        title="Gathering Metadata...",
        completion_title="🎉Done",
        completion_subtitle="All Set!",
    ) as bar:
        for folder_explorer_element in folder_explorer.value:
            try:
                selection = Path(folder_explorer_element.path)
                input_file = _adapter.resolve_file(selection)
                metadata = _adapter.extract(input_file)

                input_image = _adapter.load(input_file)
                thumbnail = generate_quick_preview(input_image)

                bioimage_list.append(thumbnail.to_numpy().astype(np.uint8))
                complete_list_metadata.append(metadata)

                bar.update(subtitle=f"{selection.stem}")

            except Exception as e:
                mo.output.append(
                    mo.md(
                        f"❌ **Error processing `{Path(folder_explorer_element.path).name}`**: {type(e).__name__}: {str(e)}"
                    ).callout("danger")
                )
                bar.update(
                    subtitle=f"Error: {Path(folder_explorer_element.path).name}"
                )
                continue

    metadata_collection_done = True

    metadata_df = pd.DataFrame.from_dict(complete_list_metadata)
    metadata_df["Server Path"] = metadata_df["File Path"]
    metadata_df["User Source Path"] = metadata_df["File Path"].map(
        convert_linux_to_windows_path
    )
    metadata_df = metadata_df.drop(columns=["File Path"])
    return bioimage_list, metadata_collection_done, metadata_df


@app.cell
def _(metadata_df):
    metadata_df
    return


@app.cell
def _(bioimage_list, metadata_collection_done):
    mo.stop(metadata_collection_done == False)

    _plotly_fig = px.imshow(
        bioimage_list[0],
        facet_col=0,
        binary_string=True,
        aspect="equal",
        contrast_rescaling="minmax",
        color_continuous_scale="magma",
    )

    _plotly_fig.for_each_annotation(
        lambda a: a.update(text="Channel " + a.text.split("=")[1])
    )

    _C = bioimage_list[0].shape[0]

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

    manual_metadata_dict = mo.ui.dictionary(
        {
            "Host": mo.ui.dropdown(
                options=EXPERIMENT_METADATA_OPTIONS["Host"], label="Host:"
            ),
            "Cell Line": mo.ui.dropdown(
                options=EXPERIMENT_METADATA_OPTIONS["Cell Line"],
                label="Cell Line:",
            ),
            "Location": mo.ui.dropdown(
                options=EXPERIMENT_METADATA_OPTIONS["Location"],
                label="Location:",
            ),
            "Treatment": mo.ui.dropdown(
                options=EXPERIMENT_METADATA_OPTIONS["Treatment"],
                label="Treatment or Disease Model:",
            ),
            "Timepoint": mo.ui.number(
                value=None, start=0, step=1, label="Timepoint (@ Treatment):"
            ),
            "Timepoint unit": mo.ui.dropdown(
                options=EXPERIMENT_METADATA_OPTIONS["Timepoint unit"],
                allow_select_none=True,
            ),
            "Additional Comments": mo.ui.text(label="Additional Comments:"),
        }
    )

    manual_metadata_submit = mo.ui.run_button(kind="warn", label="**Submit**")

    dye_marker_stack = mo.md(
        f"### Fill in the required metadata for each of the {_C} Channels:\n\n"
        + "\n\n".join(
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
            manual_metadata_dict["Host"],
            manual_metadata_dict["Cell Line"],
            manual_metadata_dict["Location"],
            manual_metadata_dict["Treatment"],
            mo.hstack(
                [
                    manual_metadata_dict["Timepoint"],
                    manual_metadata_dict["Timepoint unit"],
                ],
                justify="start",
            ),
            manual_metadata_dict["Additional Comments"],
            manual_metadata_submit,
        ],
        justify="start",
    )

    final
    return dye_marker_dict, manual_metadata_dict, manual_metadata_submit


@app.cell
def _(
    dye_marker_dict,
    input_form,
    manual_metadata_dict,
    manual_metadata_submit,
    metadata_df,
):
    mo.stop(manual_metadata_submit.value == False)

    channel_names_str = CHANNEL_LIST_SEP.join(
        f"{m} - {d}" if m else d
        for m, d in zip(
            dye_marker_dict.value["marker"], dye_marker_dict.value["dye"]
        )
    )

    final_df = metadata_df.assign(**manual_metadata_dict.value)
    final_df["Channel Names"] = channel_names_str
    final_df["Microscope Type"] = input_form.value["microscope_type"]

    final_df["uuid"] = [uuid.uuid4() for _ in range(len(final_df))]

    final_submit = mo.ui.run_button(kind="warn", label="**Submit**")

    mo.vstack(
        [
            mo.md("""# 4) Submit to Metadata Storage"""),
            mo.md("Preview your final metadata here:"),
            final_df,
            final_submit,
        ],
    )
    return final_df, final_submit


@app.cell
def _(final_df, final_submit):
    mo.stop(final_submit.value == False)

    csv_name: str = (
        datetime.now().strftime(TIME_STAMP_FORMAT)
        + "-"
        + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
        + ".csv"
    )

    final_df.to_csv(CSV_DIR / csv_name, index=False)

    mo.md("""
            🎉 Congratulations! Your files have been correctly stored 🥰

    """).center().callout("success")
    return


if __name__ == "__main__":
    app.run()
