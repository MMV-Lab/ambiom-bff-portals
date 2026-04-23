from pathlib import Path, PureWindowsPath
from typing import Union

from .config import PATH_MAPPING


def convert_windows_to_linux_path(windows_path_str: str) -> Path | None:
    """
    Converts a Windows path string to a Linux path string based on PATH_MAPPING.

    Args:
        windows_path_str: The input Windows path string.

    Returns:
        The converted Linux Path if a mapping is found, otherwise None.
    """
    input_windows_path = PureWindowsPath(windows_path_str)
    converted_path = None

    for win_root, linux_root in PATH_MAPPING.items():
        if input_windows_path.is_relative_to(win_root):
            relative_path = input_windows_path.relative_to(win_root)
            if linux_root:
                converted_path = linux_root / relative_path
                break

    if converted_path:
        return converted_path.absolute()
    else:
        return None


def convert_linux_to_windows_path(linux_path: Union[str, Path]) -> str | None:
    """
    Converts a Linux path (string or Path object) to a Windows path string
    based on PATH_MAPPING.

    Args:
        linux_path: The input Linux path (as a string or pathlib.Path object).

    Returns:
        The converted Windows path string (with backslashes) if a mapping is found,
        otherwise None.
    """
    try:
        input_linux_path = Path(linux_path).resolve()
    except (TypeError, RuntimeError):
        return None

    converted_path = None

    for win_root, linux_root in PATH_MAPPING.items():
        if input_linux_path.is_relative_to(linux_root):
            relative_path = input_linux_path.relative_to(linux_root)
            converted_path = win_root / relative_path
            break

    if converted_path:
        return str(converted_path)
    else:
        return None
