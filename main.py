import marimo

__generated_with = "0.16.0"
app = marimo.App(width="medium")

with app.setup:
    # Initialization code that runs before all other cells
    import marimo as mo
    from bioio import BioImage
    from bioio_ome_tiff.writers import OmeTiffWriter
    from bioio_ome_zarr.writers import OMEZarrWriter
    from pathlib import Path, PureWindowsPath


    PATH_MAPPING = {
        PureWindowsPath(r"\\ambiom-fs1.isas.de\ambiom_storage"): Path(
            "/mnt/eternus/"
        ),
        # PureWindowsPath(r"\\do1-fs-iota.isas.de\bio-img-raw"): # N.A.,
        # PureWindowsPath(r"L:\Research"): None, # AMBIOM GROUP\BioImaging-RO
    }

    tmp_path = Path("./tmp").resolve()
    tmp_path.mkdir(parents=True, exist_ok=True)


@app.cell
def _():
    array = mo.ui.array(
        [mo.ui.button(on_change=lambda value, i=i: print(i)) for i in range(10)]
    )
    array
    return


@app.cell
def _():
    # TEST PATH

    r"\\ambiom-fs1.isas.de\ambiom_storage\users\Davide\mmv-bff\data\AG29"

    r"L:\Research\Christiane"
    return


@app.cell
def _(input_form, input_form_output):
    graphical_elements = mo.ui.dictionary(
        {
            "file_selection_form": mo.ui.file_browser(initial_path=tmp_path,restrict_navigation=True).form(loading=True),
            #"file_selection_form_output": mo.md("").form(),
        }
    )

    title = mo.hstack(
        [
            mo.image(src="public/ISAS_Logo.svg", width=70),
            mo.md("# MMV - BFF Interface ").center(),
        ],
        justify="start",
        align="center",
    )

    body_text = mo.md("sakjfbaskfbasksfb")

    accordion_layout = mo.accordion(
        {
            "1) Where is your Raw data?": mo.vstack(
                [input_form, input_form_output]
            ),
            "2) Select Folders to analyze": mo.ui.file_browser(initial_path=tmp_path,restrict_navigation=True).form(loading=True),
            "3) Set Microscope Settings": mo.md("Nothing!"),
            "4) Export Data to Disk & BFF": mo.md("Nothing!"),
        },
        multiple=True
    )

    #file_selection_form = mo.md("Run Step Before!")

    mo.vstack([title, body_text, accordion_layout])
    return


@app.cell
def _():
    path_added, set_path_added = mo.state(False)
    return


@app.cell
def _():
    input_form = (
        mo.md("""
            ## Input Folder Form
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

    return (input_form,)


@app.cell
def _(input_form):
    converted_path = None

    input_form_output = mo.md("")

    get_counter, set_counter = mo.state(0)

    if input_form.value:
        if input_form.value["input_path"] == "":
            input_form_output = mo.md("Empty Path").callout("danger")
        else:
            converted_path = convert_windows_to_linux_path(
                input_form.value["input_path"]
            )
            if converted_path:
                input_form_output = mo.md(f"""Correctly Processed Input Path

                    Original Windows Path: {input_form.value["input_path"]}
                    Converted Path: {converted_path}

                    **PROCEED TO NEXT STEP**
            
                """).callout("success")

                set_counter(1)
            
            else:
                input_form_output = mo.vstack(
                    [
                        mo.md("""The Windows path provided does not match any specified mapping.
            
                Here's the list of already implemented mappings:
            
            
                """),
                        list(PATH_MAPPING.keys()),
                    ]
                ).callout("danger")
    return converted_path, input_form_output


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


@app.cell
def _(converted_path):
    mo.stop(converted_path is None)
    test  = mo.ui.file_browser(
        initial_path=converted_path, multiple=True, selection_mode="directory"
    )

    test
    return (test,)


@app.cell
def _(test):
    dir(test)
    return


@app.cell
def _(test):
    test.from_args()
    return


if __name__ == "__main__":
    app.run()
