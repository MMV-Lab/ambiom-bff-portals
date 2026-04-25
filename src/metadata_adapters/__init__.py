from pathlib import Path
from typing import Literal, Protocol

from src.metadata_adapters.blaze import BlazeAdapter
from src.metadata_adapters.leica_sp8 import LeicaSP8Adapter


class MetadataAdapter(Protocol):
    """
    Structural protocol for microscope metadata adapters.
    Any class with an ``extract`` method matching this signature qualifies —
    no subclassing required.

    Class-level attributes
    ----------------------
    selection_mode : "directory" | "file"
        Tells the file browser whether the user should pick whole directories
        (e.g. Blaze, where each acquisition is a folder of tiles) or individual
        files (e.g. a single .czi or .lif).
    accepted_suffixes : list[str]
        File extensions the adapter can handle (e.g. [".ome.tif", ".tif"]).
        Shown as a hint in the UI.  Ignored when selection_mode is
        "directory".  An empty list means "any file".
    """

    selection_mode: Literal["directory", "file"]
    accepted_suffixes: list[str]

    def extract(self, path: Path) -> dict:
        """Extract canonical metadata from a single image file or directory."""
        ...

    def resolve_file(self, selection: Path) -> Path:
        """
        Given the path handed back by the file browser, return the single
        file that should be passed to ``extract``.

        For directory-mode adapters this typically means finding the first
        matching tile/file inside the folder.  For file-mode adapters it
        usually returns ``selection`` unchanged.

        Raises ``FileNotFoundError`` if no suitable file can be found, and
        ``ValueError`` if the selection structure is unexpected (e.g. nested
        sub-directories where none are expected).
        """
        ...

    def load(self, path: Path) -> "BioImage":
        """
        Open *path* and return a ``BioImage`` instance using the reader and
        options appropriate for this microscope type.
        """
        ...

    # Optional — adapters may define ``build_ome(self, img, img_xr) -> OME``
    # when they need custom OME metadata construction (e.g. multi-image
    # acquisitions like Blaze where annotation refs must be preserved).
    # If absent, ``process_images`` falls back to ``img.ome_metadata``.

    # Optional multi-scene interface (e.g. Leica .lif files):
    # ``list_scenes(path) -> list[str]``
    #     Returns all scene names embedded in the file.
    # ``load(path, scene_index=0)`` / ``extract(path, scene_index=0)``
    #     Accept an optional zero-based scene index.  When present, the
    #     uploader shows a scene-picker UI after file selection and the
    #     processor passes the stored ``Scene Index`` column value.


# Maps the UI label shown in the dropdown to the corresponding adapter class.
# Add new adapters here as they are implemented.
ADAPTER_REGISTRY: dict = {
    "Miltenyi UltraMicroscope Blaze (LSFM) [1st floor]": BlazeAdapter,
    "LEICA SP8 (confocal) [2nd floor]": LeicaSP8Adapter,
}
