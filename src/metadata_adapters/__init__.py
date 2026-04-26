from pathlib import Path
from typing import Literal, Protocol

from src.metadata_adapters.blaze import BlazeAdapter
from src.metadata_adapters.leica_sp8 import LeicaSP8Adapter

# Maps the UI label shown in the dropdown to the corresponding adapter class.
# Add new adapters here as they are implemented.
ADAPTER_REGISTRY: dict = {
    "Miltenyi UltraMicroscope Blaze (LSFM) [1st floor]": BlazeAdapter,
    "LEICA SP8 (confocal) [2nd floor]": LeicaSP8Adapter,
}


class MetadataAdapter(Protocol):
    """
    Structural protocol for microscope metadata adapters.
    Any class whose methods match these signatures qualifies —
    no subclassing required.

    Class-level attributes
    ----------------------
    selection_mode : "directory" | "file"
        Tells the file browser whether the user should pick whole directories
        (e.g. Blaze, where each acquisition is a folder of tiles) or individual
        files (e.g. a .lif file that may contain multiple scenes).
    accepted_suffixes : list[str]
        File extensions the adapter can handle (e.g. ``[".ome.tif"]``,
        ``[".lif"]``).  Shown as a hint in the UI.  Ignored when
        ``selection_mode`` is ``"directory"``.  An empty list means "any file".

    Required methods
    ----------------
    ``extract(path, ...)``      — extract canonical metadata (see below).
    ``resolve_file(selection)`` — map a browser selection to a concrete file.
    ``load(path, ...)``         — open *path* and return a ``bioio.BioImage``.

    Optional methods
    ----------------
    ``build_ome(img, img_xr) -> OME``
        Custom OME metadata construction.  Implement when the adapter must
        preserve extra annotation refs or restructure images (e.g. Blaze
        multi-tile acquisitions, Leica SP8 multi-scene .lif files).
        If absent, ``process_images`` falls back to ``img.ome_metadata``.

    Multi-scene interface (e.g. ``LeicaSP8Adapter`` for .lif files)
    ----------------------------------------------------------------
    Adapters that store several acquisitions in one file should also expose:

    ``list_scenes(path) -> list[str]``
        Returns the ordered list of scene names embedded in *path*.
    ``load(path, scene_index=0) -> BioImage``
        Opens *path* and activates the requested scene (zero-based).
    ``extract(path, scene_index=0) -> dict``
        Extracts metadata for the requested scene; the returned dict
        includes ``"Scene Index"`` and ``"Scene Name"`` in addition to
        the standard fields listed below.

    Canonical ``extract`` return fields
    ------------------------------------
    The shared base fields are defined in ``CANONICAL_FIELDS`` and
    ``CHANNEL_LIST_TO_FLAT`` in ``src.metadata_config``.  Adapter-specific
    extras (channel lists, scene info, instrument settings) are documented in
    their adapters.
    """

    selection_mode: Literal["directory", "file"]
    accepted_suffixes: list[str]

    def extract(self, path: Path) -> dict:
        """Extract canonical metadata from a single image file or directory.

        Multi-scene adapters (e.g. ``LeicaSP8Adapter``) additionally accept a
        ``scene_index: int = 0`` keyword argument to select the target scene.

        Returns
        -------
        dict
            All canonical fields (see class docstring) plus any
            adapter-specific extras.
        """
        ...

    def resolve_file(self, selection: Path) -> Path:
        """Given the path handed back by the file browser, return the single
        file that should be passed to ``load`` and ``extract``.

        For ``"directory"`` adapters this means finding the first matching
        tile/file inside the folder (e.g. the first ``.ome.tif`` for Blaze).
        For ``"file"`` adapters it returns ``selection`` unchanged after
        basic validation.

        Raises
        ------
        FileNotFoundError
            If no suitable file can be found inside *selection*.
        ValueError
            If the selection structure is unexpected (e.g. nested
            sub-directories where none are expected).
        """
        ...

    def load(self, path: Path) -> "BioImage":
        """Open *path* and return a ``BioImage`` instance.

        Uses the reader and options appropriate for this microscope type
        (e.g. ``bioio_bioformats.Reader`` for Blaze, ``bioio_lif.Reader``
        for Leica SP8).  Multi-scene adapters additionally accept a
        ``scene_index: int = 0`` keyword argument to activate the correct
        scene immediately after opening.
        """
        ...


