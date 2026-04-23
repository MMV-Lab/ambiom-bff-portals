import re
from functools import wraps
from typing import Any, Callable, Union


def clean_up_qname(input_str: str) -> str:
    """Remove XML namespace from qname."""
    return re.sub(r"{[^}]*}*", "", input_str)


def handle_return_decorator(func: Callable) -> Callable:
    """
    Decorator to handle return values from XML metadata search.
    Standardizes the output format for dictionary and string returns.
    """

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


@handle_return_decorator
def find_metadata_in_xml(
    image: Any, text_to_search: str
) -> Union[str, dict, None]:
    """
    Searches for the first occurrence of text_to_search in qnames or fnames.

    Args:
        image: The BioImage object containing OME metadata.
        text_to_search: The text to search for in qnames and fnames.

    Returns:
        Union[str, dict, None]: The value as a string or dict if found, otherwise None.
    """
    try:
        xml_list = [
            xml_annotation
            for xml_annotation in image.ome_metadata.structured_annotations
        ]

        # Search in qnames (first annotation)
        if xml_list:
            for elem in xml_list[0].value.any_elements:
                # Handle elements with children
                if getattr(elem, "children", None):
                    for child in elem.children:
                        if text_to_search in clean_up_qname(
                            getattr(child, "qname", "")
                        ):
                            return child.attributes
                # Handle elements without children
                elif text_to_search in clean_up_qname(
                    getattr(elem, "qname", "")
                ):
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
