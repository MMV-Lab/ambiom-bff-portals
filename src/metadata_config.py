# Canonical output field names produced by all metadata adapters.
# Channel-level fields (e.g. "Channel 0 EXC [nm]") are added dynamically
# and are not listed here since the number of channels varies per image.
CANONICAL_FIELDS = [
    "File Name",
    "File Path",
    "Image Size (X,Y,Z) [pixels]",
    "Pixel Size X [um]",
    "Pixel Size Y [um]",
    "Pixel Size Z [um]",
    "Number of Channels",
    "Obj. Magnification",
    "Obj. NA",
    "Digital Zoom",
    "Measurement TimeStamp",
]

# Separator used to serialise channel lists inside CSV cells.
# Must not appear in any channel value (wavelengths, dye/marker names).
CHANNEL_LIST_SEP = "|"

# Maps each list-column name (intermediate CSV) → flat column template (BFF CSV).
# Use {i} as the channel-index placeholder.
CHANNEL_LIST_TO_FLAT: dict[str, str] = {
    "Channel EXC [nm]":          "Channel {i} EXC [nm]",
    "Channel EM [nm]":           "Channel {i} EM [nm]",
    "Channel Exposure Time [ms]": "Channel {i} Exposure Time [ms]",
    "Channel Pixel Dwell Time [µs]": "Channel {i} Pixel Dwell Time [µs]",
    "Channel Names":             "Channel {i}",
}

# Experiment metadata dropdown options for manual metadata collection UI
EXPERIMENT_METADATA_OPTIONS: dict[str, list[str]] = {
    "Host": [
        "Human",
        "Mouse",
        "Rat",
        "Zebrafish",
        "C. elegans",
        "Drosophila",
        "Arabidopsis",
        "Yeast",
        "Bacteria",
        "Plant",
        "Custom",
    ],
    "Cell Line": [
        "hMSCs",
        "HUVEC",
        "HeLa",
        "HEK293",
        "CHO",
        "COS-7",
        "NIH 3T3",
        "Primary Culture",
        "E. Coli",
        "Biopsy",
        "Whole Tissue",
        "Organoid",
        "Spheroid",
        "Custom",
    ],
    "Location": [
        "Liver",
        "Knee Joint",
        "Heart",
        "Lung",
        "Bladder",
        "Peritoneum",
        "Colon",
        "Brain",
        "Spinal Cord",
        "Kidney",
        "Pancreas",
        "Stomach",
        "Small Intestine",
        "Skin",
        "Muscle",
        "Bone",
        "Blood Vessel",
        "Adipose Tissue",
        "Lymph Node",
        "Thymus",
        "Spleen",
        "Eye",
        "Ear",
        "Prostate",
        "Uterus",
        "Breast",
        "Custom",
    ],
    "Treatment": [
        "CTRL",
        "WT",
        "Disease",
        "Inflammation",
        "Hypoxia",
        "Drug Treatment",
        "Genetic Modification",
        "Mechanical Stress",
        "Chemical Stress",
        "Oxidative Stress",
        "Infection",
        "Injury",
        "Recovery",
        "Custom",
    ],
    "Timepoint unit": [
        "seconds",
        "minutes",
        "hours",
        "days",
        "weeks",
        "months",
    ],
}



