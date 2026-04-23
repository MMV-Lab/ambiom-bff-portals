import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium", app_title="ISAS BFF Re-export")

with app.setup:
    from pathlib import Path

    import polars as pl
    import marimo as mo
    from datetime import datetime
    import random
    import string

    from src.config import (
        CSV_DIR,
        TIME_STAMP_FORMAT,
        BASE_URL,
        ZARR_DIR,
        THUMBNAIL_DIR,
    )


@app.cell
def _():
    title = mo.hstack(
        [
            mo.image(src="public/ISAS_Logo.svg", width=70),
            mo.md("# ISAS BFF Re-export").center(),
        ],
        justify="start",
        align="center",
    )

    body_text = mo.md(f"""
    Rebuilds **File Path** and **Thumbnail** columns in existing `BFF_` CSVs using
    the current `BASE_URL` from `config.py`.

    Use this when switching from **localhost → public deployment** (or vice versa)
    without reprocessing images.

    Current base URL: `{BASE_URL}`
    """)

    mo.vstack([title, body_text], align="center")
    return


@app.cell
def _():
    _text = mo.md("# Select BFF_ CSV files to re-export")

    folder_explorer = mo.ui.file_browser(
        initial_path=CSV_DIR,
        multiple=True,
        restrict_navigation=False,
    ).form()

    mo.vstack([_text, folder_explorer])
    return (folder_explorer,)


@app.cell
def _(folder_explorer):
    mo.stop(
        folder_explorer.value is None,
        mo.md("Submit the previous form to continue").callout("danger"),
    )

    bff_csv_paths = [
        Path(item.path)
        for item in folder_explorer.value
        if Path(item.path).name.startswith("BFF_")
    ]

    if not bff_csv_paths:
        mo.stop(True, mo.md("No `BFF_` files selected.").callout("danger"))
    return (bff_csv_paths,)


@app.cell
def _(bff_csv_paths):
    df_list = [pl.read_csv(p) for p in bff_csv_paths]
    df = pl.concat(df_list, how="diagonal_relaxed")

    # Rebuild URL columns from File Path Relative / Thumbnail Relative + current BASE_URL.
    df = df.with_columns(
        [
            (pl.lit(f"{BASE_URL}/{ZARR_DIR.name}/") + pl.col("File Path Relative")).alias("File Path"),
            (pl.lit(f"{BASE_URL}/{THUMBNAIL_DIR.name}/") + pl.col("Thumbnail Relative")).alias("Thumbnail"),
        ]
    )

    mo.vstack(
        [
            mo.md(f"**{len(df)} rows** loaded from {len(bff_csv_paths)} file(s)."),
            mo.md(f"New `File Path`: `{BASE_URL}/{ZARR_DIR.name}/<uuid>.ome.zarr`"),
            mo.md(f"New `Thumbnail`: `{BASE_URL}/{THUMBNAIL_DIR.name}/<uuid>.jpg`"),
            mo.ui.table(df.head(5), show_download=False),
        ]
    )
    return (df,)


@app.cell
def _():
    submit = mo.ui.run_button(kind="warn", label="**Save re-exported CSV**")
    submit
    return (submit,)


@app.cell
def _(df, submit):
    mo.stop(submit.value == False)

    csv_name: str = (
        "BFF_"
        + datetime.now().strftime(TIME_STAMP_FORMAT)
        + "-"
        + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
        + ".csv"
    )

    df.write_csv(CSV_DIR / csv_name)

    mo.md(f"Saved as `{csv_name}`").callout("success")
    return


if __name__ == "__main__":
    app.run()
