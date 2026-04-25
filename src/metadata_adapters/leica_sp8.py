import re
from pathlib import Path

from bioio import BioImage
import bioio_lif

from src.metadata_config import CHANNEL_LIST_SEP


def _local_tag(element) -> str:
    """Return the local tag name of an XML element, stripping any namespace."""
    tag = element.tag
    return tag.split("}")[-1] if "}" in tag else tag


def _find_confocal_settings(xml_root, scene_name: str) -> dict:
    """Return the attribute dict of the ATLConfocalSettingDefinition element.

    Searches within the ``<Element Name=scene_name>`` subtree first so that
    the correct settings are returned for multi-scene files.  Falls back to
    the first match anywhere in the tree if the scene element is not found.
    """
    try:
        # Scoped search: find the Element whose Name matches the scene first.
        scene_root = None
        for elem in xml_root.iter():
            if _local_tag(elem) == "Element" and elem.get("Name") == scene_name:
                scene_root = elem
                break

        search_root = scene_root if scene_root is not None else xml_root
        for elem in search_root.iter():
            if _local_tag(elem) == "ATLConfocalSettingDefinition":
                return dict(elem.attrib)
    except Exception:
        pass
    return {}


def _iter_tag(elem, tag_name: str):
    """Yield all descendants of *elem* whose local tag equals *tag_name*."""
    for child in elem.iter():
        if _local_tag(child) == tag_name:
            yield child


def _extract_channel_data(
    xml_root, scene_name: str, n_channels: int
) -> list[tuple[str, str]]:
    """
    Return a list of ``(exc_nm, em_range)`` tuples — one per channel.

    Navigates the ``LDM_Block_Sequential_List`` inside the scene's
    ``HardwareSetting`` attachment.  Each child
    ``ATLConfocalSettingDefinition`` that has at least one active detector
    (``IsActive='1'``) represents one sequential scan step (channel).  Steps
    with no active detectors are skipped — they are the "extra" master entry
    that Leica LAS X inserts at the start of the list.

    EM range
    --------
    Read from ``Spectro/MultiBand`` whose ``ChannelName`` matches the active
    detector's ``ChannelName``.  ``LeftWorld`` and ``RightWorld`` are in nm.

    EXC wavelength
    --------------
    Read from ``LaserLineSetting/@LaserLine`` where ``@IntensityDev > 0``.
    Each sequential step has one ``LaserLineSetting`` per available laser
    line; only the line actually used for that step carries a non-zero
    ``IntensityDev``.  This correctly resolves multi-line lasers (e.g.
    Argon 488 nm appears as its own entry, distinct from the 458/514 lines)
    unlike the ``Laser/@Wavelength`` attribute which only reflects the
    primary nominal wavelength of the laser head.

    Padding / trimming
    ------------------
    The returned list always has exactly *n_channels* entries.
    """
    # Scope search to the correct scene element
    scene_root = None
    for elem in xml_root.iter():
        if _local_tag(elem) == "Element" and elem.get("Name") == scene_name:
            scene_root = elem
            break
    search_root = scene_root if scene_root is not None else xml_root

    # Locate the sequential scan list
    seq_list_elem = None
    for elem in search_root.iter():
        if _local_tag(elem) == "LDM_Block_Sequential_List":
            seq_list_elem = elem
            break
    if seq_list_elem is None:
        return [("", "")] * n_channels

    channels: list[tuple[str, str]] = []
    for seq_conf in seq_list_elem:
        if _local_tag(seq_conf) != "ATLConfocalSettingDefinition":
            continue

        # Only process steps that have at least one active detector
        active_dets = [
            d for d in _iter_tag(seq_conf, "Detector")
            if d.get("IsActive") == "1"
        ]
        if not active_dets:
            continue

        # --- EXC: LaserLineSetting with IntensityDev > 0 gives the active line ---
        exc_str = ""
        for lls in _iter_tag(seq_conf, "LaserLineSetting"):
            try:
                intensity = float(lls.get("IntensityDev", "0"))
            except (ValueError, TypeError):
                intensity = 0.0
            if intensity > 0:
                line = lls.get("LaserLine", "")
                if line:
                    try:
                        exc_str = str(int(float(line)))
                    except (ValueError, TypeError):
                        exc_str = line
                break  # take the first (and typically only) active line per step

        # --- EM range: match MultiBand to the active detector's ChannelName ---
        active_ch_name = active_dets[0].get("ChannelName", "")
        em_str = ""
        for mb in _iter_tag(seq_conf, "MultiBand"):
            if mb.get("ChannelName") == active_ch_name:
                try:
                    left = float(mb.get("LeftWorld", ""))
                    right = float(mb.get("RightWorld", ""))
                    em_str = f"{left:.0f}-{right:.0f}"
                    break
                except (ValueError, TypeError):
                    pass

        channels.append((exc_str, em_str))

    # Pad / trim to the expected channel count
    while len(channels) < n_channels:
        channels.append(("", ""))
    return channels[:n_channels]


class LeicaSP8Adapter:
    """Metadata adapter for Leica SP8 confocal acquisitions stored in .lif files.

    A single .lif file may contain multiple acquisitions (scenes).  The file
    browser operates in file-selection mode; the uploader then offers a
    per-scene picker so users can select which scenes to process.

    Optional multi-scene interface
    --------------------------------
    ``list_scenes(path)``
        Returns all scene names embedded in the file.
    ``load(path, scene_index=0)``
        Opens the file and activates the requested scene.
    ``extract(path, scene_index=0)``
        Extracts canonical metadata for the requested scene.
    """

    selection_mode = "file"
    accepted_suffixes: list[str] = [".lif"]

    def resolve_file(self, selection: Path) -> Path:
        """Return *selection* unchanged — it is already the target .lif file."""
        if not selection.exists():
            raise FileNotFoundError(f"`{selection}` does not exist")
        if selection.suffix.lower() != ".lif":
            raise ValueError(f"`{selection.name}` is not a .lif file")
        return selection

    def list_scenes(self, path: Path) -> list[str]:
        """Return the ordered list of scene names inside *path*."""
        img = BioImage(path, reader=bioio_lif.Reader)
        return list(img.scenes)

    def load(self, path: Path, scene_index: int = 0) -> BioImage:
        """Open *path* and activate *scene_index*."""
        img = BioImage(path, reader=bioio_lif.Reader)
        img.set_scene(scene_index)
        return img

    def extract(self, path: Path, scene_index: int = 0) -> dict:
        """
        Extract canonical metadata from a single scene of a .lif file.

        Parameters
        ----------
        path:
            Path to the .lif file.
        scene_index:
            Zero-based index of the scene to extract metadata from.

        Returns
        -------
        dict with all canonical fields plus per-channel EXC/EM/Exposure entries
        and extra ``Scene Index`` / ``Scene Name`` keys.
        """
        img = self.load(path, scene_index)
        sm = img.standard_metadata

        scene_name = img.scenes[scene_index] if img.scenes else str(scene_index)
        n_channels = (
            sm.image_size_c
            if sm.image_size_c is not None
            else len(img.channel_names)
        )

        # --- Objective / zoom from ATLConfocalSettingDefinition ---
        _conf = _find_confocal_settings(img.metadata, scene_name)
        obj_magnification = _conf.get("Magnification")
        obj_na = _conf.get("NumericalAperture")
        digital_zoom = _conf.get("Zoom")

        # --- Per-channel EXC / EM from sequential scan XML ---
        ch_data = _extract_channel_data(img.metadata, scene_name, n_channels)
        exc_list = [ch[0] for ch in ch_data]
        em_list = [ch[1] for ch in ch_data]

        # --- Pixel dwell time: SP8 stores it as a plain float in seconds ---
        dwell_list: list[str] = [""] * n_channels
        _pixel_dwell_raw = _conf.get("PixelDwellTime", "")
        if _pixel_dwell_raw:
            try:
                _dwell_us = float(_pixel_dwell_raw) * 1e6
                dwell_list = [f"{_dwell_us:.4f}"] * n_channels
            except ValueError:
                # Fallback: try "1.2 µs" style
                _m = re.search(r"([\d.]+)\s*µs", _pixel_dwell_raw)
                if _m:
                    dwell_list = [f"{float(_m.group(1)):.4f}"] * n_channels

        return {
            "File Name": path.name,
            "File Path": str(path.resolve()),
            "Scene Index": scene_index,
            "Scene Name": scene_name,
            "Image Size (X,Y,Z) [pixels]": (
                f"{sm.image_size_x},{sm.image_size_y},{sm.image_size_z}"
            ),
            "Pixel Size X [um]": sm.pixel_size_x,
            "Pixel Size Y [um]": sm.pixel_size_y,
            "Pixel Size Z [um]": sm.pixel_size_z,
            "Number of Channels": n_channels,
            "Obj. Magnification": obj_magnification,
            "Obj. NA": obj_na,
            "Digital Zoom": digital_zoom,
            "Measurement TimeStamp": (
                sm.imaging_datetime.isoformat() if sm.imaging_datetime else None
            ),
            "Channel EXC [nm]": CHANNEL_LIST_SEP.join(str(v) for v in exc_list),
            "Channel EM [nm]": CHANNEL_LIST_SEP.join(str(v) for v in em_list),
            "Channel Pixel Dwell Time [µs]": CHANNEL_LIST_SEP.join(
                str(v) for v in dwell_list
            ),
        }
