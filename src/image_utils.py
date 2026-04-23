import numpy as np
import xarray as xr
from PIL import Image
from bioio import BioImage

from .config import MAX_THUMBNAIL_SIZE


def generate_quick_preview(input_image: BioImage) -> xr.DataArray:
    preview = input_image.xarray_dask_data
    preview = preview.squeeze(drop=True)

    selection = {}

    # Handle dimensions that should keep middle slice
    for dim in ["T", "M", "S", "Z"]:
        if dim in preview.dims:
            middle_idx = preview.sizes[dim] // 2
            selection[dim] = middle_idx

    # Downsample X and Y to fit within MAX_THUMBNAIL_SIZE
    step = 1
    if "X" in preview.dims and "Y" in preview.dims:
        max_dim = max(preview.sizes["X"], preview.sizes["Y"])
        while max_dim // step > MAX_THUMBNAIL_SIZE:
            step *= 2
        if step > 1:
            selection["X"] = slice(None, None, step)
            selection["Y"] = slice(None, None, step)

    # Apply all selections at once
    preview = preview.isel(selection) if selection else preview

    # Contrast enhancement per channel
    vmin, vmax = preview.quantile([0.01, 0.99], dim=["X", "Y"], skipna=True)
    preview = preview.clip(min=vmin, max=vmax)

    # Prevent division by zero using xarray.where
    denominator = vmax - vmin
    preview = xr.where(
        denominator > 0,
        (preview - vmin) / denominator * 255.0,
        128.0,  # default value when denominator is 0
    )
    preview = preview.fillna(0)

    return preview


def generate_rgb_thumbnail(thumbnail: xr.DataArray) -> tuple:
    selection = {}

    n_channels = thumbnail.sizes["C"]

    if "C" in thumbnail.dims:
        if n_channels > 3:
            selection["C"] = slice(0, 3)

    thumbnail = thumbnail.isel(selection)

    if "C" in thumbnail.dims and thumbnail.sizes["C"] == 2:
        zero_channel = xr.zeros_like(thumbnail.isel(C=0))
        thumbnail = xr.concat(
            [thumbnail, zero_channel.expand_dims("C")], dim="C"
        )

    thumbnail = thumbnail.transpose("X", "Y", "C")
    thumbnail_np = thumbnail.to_numpy().astype(np.uint8)
    thumbnail_np = np.squeeze(thumbnail_np)

    if n_channels == 1:
        pil_thumbnail = Image.fromarray(thumbnail_np, mode="L")
    else:
        pil_thumbnail = Image.fromarray(thumbnail_np, mode="RGB")

    return pil_thumbnail, thumbnail_np
