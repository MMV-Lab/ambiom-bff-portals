import traceback
from pathlib import Path

from bioio_ome_tiff.writers import OmeTiffWriter
from bioio_ome_zarr.writers import OMEZarrWriter

from .config import XML_DIR, THUMBNAIL_DIR, TIFF_DIR, ZARR_DIR
from .image_utils import generate_quick_preview, generate_rgb_thumbnail


def process_images(input_path_str: str, uuid: str, adapter) -> tuple[bool, Exception | None]:
    try:
        input_path = Path(input_path_str).resolve()
        if not input_path.exists() or not input_path.is_file():
            raise ValueError(f"{input_path} doesn't exists")

        img = adapter.load(input_path)

        img_xr = img.xarray_dask_data

        # Drop useless dims
        img_xr = img_xr.squeeze(drop=True)
        img_xr_dims = "".join(img_xr.dims)
        img_physical_pixel_sizes = img.physical_pixel_sizes

        # ------------------ FIX OME-XML ------------------

        _out_xml_path = XML_DIR / f"{uuid}.xml"

        if hasattr(adapter, 'build_ome'):
            out_ome = adapter.build_ome(img, img_xr)
        else:
            out_ome = img.ome_metadata

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
            OmeTiffWriter.save(
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
        traceback.print_exc()
        return False, e
