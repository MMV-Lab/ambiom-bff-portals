import re
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Union

from bioio import BioImage
import bioio_bioformats
from bioio_ome_tiff.writers import OmeTiffWriter

from src.metadata_config import CHANNEL_LIST_SEP

# Maps canonical field name → XML search key used by find_metadata_in_xml
# to locate the value in the OME structured annotations.
BLAZE_XML_KEYS: dict[str, str] = {
    "Obj. Magnification": "Blaze ObjectiveMagnification",
    "Obj. NA": "ObjectiveNA",
    "Digital Zoom": "Blaze CurrentZoom",
    "Measurement TimeStamp": "MeasTime",
}

# Prefix used to build per-channel XML search keys (e.g. "Filter0", "Filter1", …).
BLAZE_CHANNEL_XML_KEY_PREFIX = "Filter"


def _clean_up_qname(input_str: str) -> str:
    """Remove XML namespace from qname."""
    return re.sub(r"{[^}]*}*", "", input_str)


def _handle_return_decorator(func: Callable) -> Callable:
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


@_handle_return_decorator
def find_metadata_in_xml(image: Any, text_to_search: str) -> Union[str, dict, None]:
    """Search for text_to_search in Blaze OME structured annotations."""
    try:
        xml_list = list(image.ome_metadata.structured_annotations)

        # Search in qnames (first annotation)
        if xml_list:
            for elem in xml_list[0].value.any_elements:
                if getattr(elem, "children", None):
                    for child in elem.children:
                        if text_to_search in _clean_up_qname(getattr(child, "qname", "")):
                            return child.attributes
                elif text_to_search in _clean_up_qname(getattr(elem, "qname", "")):
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


class BlazeAdapter:
    """Metadata adapter for Blaze light-sheet microscope acquisitions.

    Blaze stores each acquisition as a *directory* of tiled .ome.tif files;
    the file browser must therefore operate in directory-selection mode.
    """

    selection_mode = "directory"
    accepted_suffixes: list[str] = [".ome.tif"]

    def resolve_file(self, selection: Path) -> Path:
        """Return the first .ome.tif inside *selection* (a Blaze acquisition directory)."""
        if any(item.is_dir() for item in selection.iterdir()):
            raise ValueError(f"`{selection.name}` contains sub-directories")
        files = sorted(selection.glob("*.ome.tif"))
        if not files:
            raise FileNotFoundError(f"`{selection.name}` contains no .ome.tif files")
        return files[0]

    def load(self, path: Path) -> BioImage:
        """Open a Blaze .ome.tif using the bioformats reader."""
        return BioImage(path, reader=bioio_bioformats.Reader)

    def build_ome(self, img: BioImage, img_xr):
        """Build a single-image OME metadata object for a Blaze acquisition."""
        img_xr_dims = "".join(img_xr.dims)
        single_image_ome = OmeTiffWriter.build_ome(
            data_shapes=[img_xr.shape],
            data_types=[img_xr.dtype],
            dimension_order=[img_xr_dims],
            physical_pixel_sizes=[img.physical_pixel_sizes],
        )
        out_ome = img.ome_metadata.model_copy()
        out_ome.images = single_image_ome.images
        out_ome.images[0].annotation_refs = img.ome_metadata.images[0].annotation_refs
        out_ome.images[0].acquisition_date = img.ome_metadata.images[0].acquisition_date
        out_ome.images[0].description = img.ome_metadata.images[0].description
        return out_ome

    def extract(self, path: Path) -> dict:
        """
        Extract canonical metadata from a single Blaze .ome.tif file.

        Args:
            path: Path to the .ome.tif file.

        Returns:
            dict with all canonical fields plus per-channel EXC/EM/Exposure entries.
        """
        image = self.load(path)

        # Start from the XML key strings, then resolve each one to its value.
        metadata_dict: dict = dict(BLAZE_XML_KEYS)
        for key in metadata_dict:
            metadata_dict[key] = find_metadata_in_xml(image, metadata_dict[key])

        exc_list, em_list, exp_list = [], [], []
        for i in range(len(image.channel_names)):
            filter_data = find_metadata_in_xml(
                image, f"{BLAZE_CHANNEL_XML_KEY_PREFIX}{i}"
            )
            if isinstance(filter_data, dict) and "EmissionWL" in filter_data:
                exc_list.append(filter_data["ExcitationWL"])
                em_list.append(filter_data["EmissionWL"])
                exp_list.append(filter_data["ExposureTime"])
            else:
                exc_list.append("")
                em_list.append("")
                exp_list.append("")

        metadata_dict["Channel EXC [nm]"] = CHANNEL_LIST_SEP.join(str(v) for v in exc_list)
        metadata_dict["Channel EM [nm]"] = CHANNEL_LIST_SEP.join(str(v) for v in em_list)
        metadata_dict["Channel Exposure Time [ms]"] = CHANNEL_LIST_SEP.join(str(v) for v in exp_list)

        return {
            "File Name": path.name,
            "File Path": str(path.resolve()),
            "Image Size (X,Y,Z) [pixels]": f"{image.dims.X},{image.dims.Y},{image.dims.Z}",
            "Pixel Size X [um]": image.physical_pixel_sizes.X,
            "Pixel Size Y [um]": image.physical_pixel_sizes.Y,
            "Pixel Size Z [um]": image.physical_pixel_sizes.Z,
            "Number of Channels": len(image.channel_names),
            **metadata_dict,
        }


#  OLD IMPLEMENTATION
# def blaze_single_image_ome(img: BioImage, output_file_name):
#     """Build a single-image OME metadata object from a multi-image BioImage."""
#     single_image_ome = OmeTiffWriter.build_ome(
#         [(img.shape[1], img.shape[0], *img.shape[2:])],
#         [img.dtype],
#         ["CTZYX"],
#         [img.channel_names],
#         [str(output_file_name)],
#         [img.physical_pixel_sizes],
#     )
#     out_ome = img.ome_metadata.model_copy()
#     out_ome.images = single_image_ome.images

#     out_ome.images[0].annotation_refs = img.ome_metadata.images[0].annotation_refs
#     out_ome.images[0].acquisition_date = img.ome_metadata.images[0].acquisition_date
#     out_ome.images[0].description = img.ome_metadata.images[0].description

#     return out_ome
