from bioio import BioImage
import bioio_bioformats
from bioio_ome_zarr.writers import OMEZarrWriter, get_default_config_for_viz

# img = BioImage("/mnt/eternus/users/Davide/ambiom-bff-portals/data/DH-LW-004 LSFM RAW Data/250310_1_bladder_detail_1_4x25_z3_14-21-43/14-21-43_1_bladder_detail_1_4x25_z3_Blaze_C00_xyz-Table Z0000.ome.tif", reader=bioio_bioformats.Reader)

img = BioImage("/mnt/eternus/users/Davide/ambiom-bff-portals/db/OME-TIFF/0ac0e218-d4f0-432f-8acc-7b20cf54bccb.ome.tiff")
print("img:", img)

axes_names = [dim.lower() for dim in img.dims.order]
print("axes_names:", axes_names)

# 2. Extract Axis Types & Units from BioIO's default base properties
axes_types =[]
axes_units =[]

for dim in img.dims.order:
    # Fetch the DimensionProperty (e.g., img.dimension_properties.X)
    dim_prop = getattr(img.dimension_properties, dim)
    
    # Populate type (e.g., "space", "time", "channel")
    axes_types.append(dim_prop.type)
    
    # Populate units (BioIO uses pint.Unit objects, we cast to string for NGFF)
    axes_units.append(str(dim_prop.unit) if dim_prop.unit else None)

print("axes_types:", axes_types)
print("axes_units:", axes_units)

# 3. Extract Physical Pixel Sizes
# img.scale handles spatial (Z,Y,X) + temporal (T) + channel (C) scaling
physical_pixel_sizes =[
    getattr(img.scale, dim) or 1.0 
    for dim in img.dims.order
]
print("physical_pixel_sizes:", physical_pixel_sizes)

# 4. Use OME-Zarr writer utilities to automatically generate pyramid & chunking config
# This automatically builds level_shapes, chunk_shape, and dtype
config = get_default_config_for_viz(img.dask_data, downsample_z=True)
print("config:", config)

# 5. Create OMEZarrWriter and preview metadata
writer = OMEZarrWriter(
                store="tmp.ome.zarr",
                zarr_format=3,
                level_shapes=config["level_shapes"],
                chunk_shape=config["chunk_shape"],
                dtype=config["dtype"],
                physical_pixel_size=physical_pixel_sizes,
            )
metadata = writer.preview_metadata()
print("preview_metadata:", metadata)

