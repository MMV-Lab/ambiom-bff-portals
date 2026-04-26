import marimo

__generated_with = "0.23.2"
app = marimo.App(width="medium")

with app.setup:
    import polars as pl
    from pathlib import Path
    import marimo as mo


@app.cell
def _():
    input_path = Path("../resources")

    input_files = input_path.glob("Dye*.xlsx")

    all_df = []

    for file in input_files:
        #print(file)
        _tmp_df = pl.read_excel(file, has_header=True, read_options={"header_row": 1})
        #print(_tmp_df)
        all_df.append(_tmp_df)

    df = pl.concat(all_df)

    new_row = pl.DataFrame({
        "Dye": ["AutoFluorescence"],
        "Excitation Peak (nm)": 0,
        "Emission Peak (nm)": 0,
    }, )
    new_row = new_row.cast(df.schema)

    df = pl.concat([df, new_row], how="vertical")



    df = df.with_columns(
        hits = pl.lit(0, pl.UInt16)
    )
    df = df.with_columns(
        pl.col("Excitation Peak (nm)").cast(pl.UInt16),
        pl.col("Emission Peak (nm)").cast(pl.UInt16)
    )



    print(df)
    return df, input_path


@app.cell
def _(df, input_path):
    df.write_parquet(input_path/"dyes.parquet")
    return


if __name__ == "__main__":
    app.run()
