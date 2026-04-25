import marimo

__generated_with = "0.23.2"
app = marimo.App(width="full", app_title="ISAS BFF Uploader")

with app.setup:
    from pathlib import Path

    import numpy as np
    import polars as pl

    import holoviews as hv
    import hvplot
    import hvplot.xarray

    hvplot.extension("bokeh")

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
    # class ClientDetector(anywidget.AnyWidget):
    #     # Properly formatted ESM module for AnyWidget
    #     _esm = """
    #     export default {
    #         render({ model }) {
    #             model.set('ua', navigator.userAgent);
    #             model.save_changes();
    #         }
    #     }
    #     """
    #     ua = traitlets.Unicode("").tag(sync=True)


    # detector = ClientDetector()
    # detector
    return


@app.cell
def _():
    # if detector:
    #     time.sleep(2)
    #     user = parse(detector.ua)
    #     mo.output.append(
    #         mo.md(
    #             f"You are using **{user.browser.family}** on **{user.os.family}**."
    #         )
    #     )
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

    scene_picker = None
    scene_confirm_button = None
    scene_options_by_file: dict = {}
    non_scene_selections = None
    _cell_output = mo.md("")

    if hasattr(adapter, "list_scenes"):
        for _item in folder_explorer.value:
            _file_path = Path(_item.path)
            try:
                _scenes = adapter.list_scenes(_file_path)
                scene_options_by_file[str(_file_path)] = _scenes
            except Exception as _e:
                mo.output.append(
                    mo.md(
                        f"⚠️ Could not list scenes for `{_file_path.name}`: {_e}"
                    ).callout("warn")
                )

        scene_picker = mo.ui.dictionary(
            {
                fp: mo.ui.multiselect(
                    options=scenes,
                    value=scenes,
                    label=f"Scenes in **{Path(fp).name}**:",
                )
                for fp, scenes in scene_options_by_file.items()
                if scenes
            }
        )
        scene_confirm_button = mo.ui.run_button(
            kind="warn", label="**Confirm Scene Selection**"
        )
        _cell_output = mo.vstack(
            [
                mo.md("# 2b) Select Scenes to Process"),
                mo.md(
                    "All scenes are pre-selected. Deselect any you want to skip, then confirm."
                ),
                *[
                    scene_picker[fp]
                    for fp in scene_options_by_file
                    if scene_options_by_file[fp]
                ],
                scene_confirm_button,
            ]
        )
    else:
        non_scene_selections = [
            (Path(item.path), None) for item in folder_explorer.value
        ]

    _cell_output
    return (
        non_scene_selections,
        scene_confirm_button,
        scene_options_by_file,
        scene_picker,
    )


@app.cell
def _(
    non_scene_selections,
    scene_confirm_button,
    scene_options_by_file: dict,
    scene_picker,
):
    if non_scene_selections is not None:
        # Non-scene adapter: selections were already resolved in the previous cell.
        scene_selections = non_scene_selections
    else:
        # Scene adapter: wait for the user to confirm the scene picker.
        mo.stop(
            scene_confirm_button is None or not scene_confirm_button.value,
        )
        scene_selections = []
        for _fp_str, _selected_names in scene_picker.value.items():
            _fp = Path(_fp_str)
            _all_scenes = scene_options_by_file.get(_fp_str, [])
            for _scene_name in _selected_names:
                try:
                    _scene_idx = _all_scenes.index(_scene_name)
                except ValueError:
                    continue
                scene_selections.append((_fp, _scene_idx))
    return (scene_selections,)


@app.cell
def _(adapter, scene_selections):
    mo.stop(
        not scene_selections,
        mo.md("No scenes selected — go back and confirm your selection.").callout(
            "warn"
        ),
    )
    metadata_collection_done = False

    complete_list_metadata = []
    preview_list = []
    file_name_list = []

    with mo.status.progress_bar(
        total=len(scene_selections),
        title="Gathering Metadata...",
        completion_title="🎉Done",
        completion_subtitle="All Set!",
    ) as bar:
        for _file_path, _scene_index in scene_selections:
            try:
                input_file = adapter.resolve_file(_file_path)
                if _scene_index is not None:
                    metadata = adapter.extract(input_file, _scene_index)
                    input_image = adapter.load(input_file, _scene_index)
                    _label = f"{input_file.name} > {metadata.get('Scene Name', str(_scene_index))}"
                else:
                    metadata = adapter.extract(input_file)
                    input_image = adapter.load(input_file)
                    _label = input_file.name

                _xr = input_image.xarray_dask_data.squeeze(drop=True)
                if "C" in _xr.dims:
                    _xr = _xr.assign_coords(C=list(range(_xr.sizes["C"])))
                preview = generate_quick_preview(_xr)

                file_name_list.append(_label)
                preview_list.append(preview)
                complete_list_metadata.append(metadata)

                bar.update(subtitle=_label)

            except Exception as e:
                mo.output.append(
                    mo.md(
                        f"❌ **Error processing `{_file_path.name}`**: {type(e).__name__}: {str(e)}"
                    ).callout("danger")
                )
                bar.update(subtitle=f"Error: {_file_path.name}")
                continue

    _channel_counts = [m["Number of Channels"] for m in complete_list_metadata]
    if len(set(_channel_counts)) > 1:
        mo.output.append(
            mo.md(
                "❌ **Currently the input images need to have the same number of channels**"
            ).callout("danger")
        )
    else:
        metadata_collection_done = True

    metadata_df = pl.DataFrame(complete_list_metadata)
    metadata_df = metadata_df.with_columns(
        pl.col("File Path").alias("Server Path"),
        pl.col("File Path")
        .map_elements(convert_linux_to_windows_path, return_dtype=pl.String)
        .alias("User Source Path"),
    ).drop("File Path")
    return (
        complete_list_metadata,
        file_name_list,
        metadata_collection_done,
        metadata_df,
        preview_list,
    )


@app.cell
def _(metadata_df):
    metadata_df
    return


@app.cell
def _(file_name_list, metadata_collection_done):
    mo.stop(metadata_collection_done == False)

    file_selector = mo.ui.dropdown(
        options=file_name_list,
        value=file_name_list[0] if file_name_list else None,
        label="Select file to preview:",
    )

    mo.vstack(
        [
            mo.md("""# 3) Fill In Manual Metadata  """),
            file_selector,
        ]
    )
    return (file_selector,)


@app.cell
def _(complete_list_metadata, file_name_list, file_selector, preview_list):
    mo.stop(file_selector.value is None)

    _idx = file_name_list.index(file_selector.value)
    _preview = preview_list[_idx]
    _meta = complete_list_metadata[_idx]
    _exc_list = _meta.get("Channel EXC [nm]", "").split(CHANNEL_LIST_SEP)
    _em_list = _meta.get("Channel EM [nm]", "").split(CHANNEL_LIST_SEP)

    preview_fig = _preview.hvplot.image(
        x="X",
        y="Y",
        responsive=True,
        min_height=100,
        max_height=400,
        aspect="equal",
        colorbar=False,
        use_dask=True,
        flip_yaxis=True,
        colormap="magma",
        hover=False,
    ).groupby("C", container_type=hv.NdLayout).opts(merge_tools=True, toolbar=None)

    _C = len(_preview.C)

    dye_marker_dict = mo.ui.dictionary(
        {
            "dye": mo.ui.array(
                [
                    mo.ui.dropdown(
                        options=DYE_DB["Dye"],
                        value=None,
                        searchable=True,
                        allow_select_none=True,
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
                f" **Channel {i}.** {marker} {dye}"
                + (f" *(EXC: {exc} nm, EM: {em} nm)*" if exc or em else "")
                for i, (dye, marker, exc, em) in enumerate(
                    zip(
                        dye_marker_dict["dye"],
                        dye_marker_dict["marker"],
                        _exc_list,
                        _em_list,
                    )
                )
            ]
        )
    )

    final = mo.vstack(
        [
            preview_fig,
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
        (f"{m} - {d}" if d else m) if m else (d or "")
        for m, d in zip(
            dye_marker_dict.value["marker"], dye_marker_dict.value["dye"]
        )
    )

    final_df = metadata_df.with_columns(
        [pl.lit(v).alias(k) for k, v in manual_metadata_dict.value.items()]
    ).with_columns(
        pl.lit(channel_names_str).alias("Channel Names"),
        pl.lit(input_form.value["microscope_type"]).alias("Microscope Type"),
        pl.Series("uuid", [str(uuid.uuid4()) for _ in range(len(metadata_df))]),
    )

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

    final_df.write_csv(CSV_DIR / csv_name)

    mo.md("""
            🎉 Congratulations! Your files have been correctly stored 🥰

    """).center().callout("success")
    return


if __name__ == "__main__":
    app.run()
