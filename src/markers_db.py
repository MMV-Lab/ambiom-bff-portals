import marimo

__generated_with = "0.17.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    from pathlib import Path

    input_path = Path("public")

    input_files = input_path.glob("Cell_*.xlsx")

    all_markers = []

    for file in input_files:
        print(file)
        _tmp_df = pl.read_excel(file, has_header=True)
        # print(_tmp_df)
        print(_tmp_df['species'].unique())
        all_markers.append(_tmp_df['marker'].unique())

    print(all_markers)

    final = pl.concat(all_markers) 
    print(final.unique())  
    return final, input_path, pl


@app.cell
def _(final, pl):
    df = final.to_frame()

    df = (
        df.with_columns(
            pl.col("marker")
            .str.strip_chars()        # remove leading/trailing whitespace
            .str.to_uppercase()       # convert to uppercase
            .alias("marker")
        )
        .unique(subset=["marker"])    # drop duplicates by marker
    )


    df = df.with_columns(
        hits = pl.lit(0, pl.UInt16)
    )

    print(df)
    return (df,)


@app.cell
def _(df, input_path):
    df.write_parquet(input_path/"markers.parquet")
    return


if __name__ == "__main__":
    app.run()
