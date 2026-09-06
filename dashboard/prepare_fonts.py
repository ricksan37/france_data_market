"""
prepare_fonts.py

Builds dashboard/fonts/*.woff2: the three fonts for the dark theme,
subsetted to Latin and converted, ready to be embedded as base64 in the
report.

WHY EMBED RATHER THAN DECLARE. The report used to declare system fonts
('Arial Black', -apple-system, 'SF Mono') to stay a single, offline-readable
file. The intent was good, the consequence wasn't: rendered on a machine
without Arial Black, chart titles lose their accents -- measured 2026-08-31,
titles do contain \\u00c9 in the HTML but display as "DEMANDEES". A
standalone deliverable can't depend on the fonts installed on whoever opens
it. Embedding as base64 satisfies both requirements at once: standalone AND
faithful to the visual identity.

WHY A SEPARATE SCRIPT. It needs network access and fonttools, both absent
from the CI runner. The resulting .woff2 files are committed; CI just reads
them. Only needs rerunning if the visual identity changes.

DOWNLOADING VIA requests, NOT urllib. urllib relies on the interpreter's own
certificate store; a Python installed from python.org on macOS has none
until Install Certificates.command has been run, and the script fails with
CERTIFICATE_VERIFY_FAILED. requests bundles its own store via certifi and is
already a project dependency (auth.py, search.py): the script becomes
portable instead of depending on the machine's configuration.

Dependencies: pip install -r requirements-dev.txt
Usage       : from the root, with the venv's interpreter EXPLICITLY
              (zsh's resolution cache can return the system python despite
              an active venv) ->
                  .venv/bin/python3 dashboard/prepare_fonts.py
"""

import io
from pathlib import Path

import requests

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
REPO = "https://raw.githubusercontent.com/google/fonts/main/ofl"

# The three font families for the dark theme. Inter and JetBrains Mono are
# distributed as variable fonts: one instance is frozen per weight actually
# used rather than embedding the whole axis (856 KB for Inter).
SOURCES = [
    ("ArchivoBlack",           f"{REPO}/archivoblack/ArchivoBlack-Regular.ttf",      None),
    ("Inter-Regular",          f"{REPO}/inter/Inter%5Bopsz%2Cwght%5D.ttf",           400),
    ("Inter-SemiBold",         f"{REPO}/inter/Inter%5Bopsz%2Cwght%5D.ttf",           600),
    ("JetBrainsMono-Regular",  f"{REPO}/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",  400),
]

LICENSES = [
    ("ArchivoBlack-OFL.txt",   f"{REPO}/archivoblack/OFL.txt"),
    ("Inter-OFL.txt",          f"{REPO}/inter/OFL.txt"),
    ("JetBrainsMono-OFL.txt",  f"{REPO}/jetbrainsmono/OFL.txt"),
]

# Basic Latin, Latin-1 supplement (French accents), oe ligatures, typographic
# punctuation and the euro sign. Everything else is stripped: that's what
# takes Inter from 856 KB to 12 KB.
UNICODES = (
    "U+0020-007E,U+00A0-00FF,U+0152-0153,U+02C6,"
    "U+2010-2015,U+2018-201A,U+201C-201E,U+2020-2022,U+2026,U+2030,"
    "U+2039-203A,U+20AC,U+2122"
)


def build_font(name: str, url: str, weight: int | None) -> int:
    """Downloads, freezes the weight if a variable font, subsets, writes the woff2."""
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    font = TTFont(io.BytesIO(response.content))

    if weight is not None:
        axes = {a.axisTag for a in font["fvar"].axes}
        settings = {"wght": weight}
        if "opsz" in axes:
            settings["opsz"] = 14  # optical size for body text
        font = instancer.instantiateVariableFont(font, settings)

    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["kern", "liga"]
    options.desubroutinize = True
    options.name_IDs = ["*"]  # keeps the license metadata inside the file

    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=subset.parse_unicodes(UNICODES))
    subsetter.subset(font)

    target = FONTS_DIR / f"{name}.woff2"
    font.flavor = "woff2"
    font.save(target)
    return target.stat().st_size


def main() -> None:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    total = 0

    for name, url, weight in SOURCES:
        size = build_font(name, url, weight)
        total += size
        print(f"  {name:24} {size / 1024:6.1f} KB")

    # The OFL license requires the license text to accompany redistributed files.
    for name, url in LICENSES:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        (FONTS_DIR / name).write_bytes(response.content)
    print(f"  {len(LICENSES)} OFL licenses written")

    print(f"\nTotal embedded: {total / 1024:.1f} KB (~{total * 1.34 / 1024:.0f} KB once base64-encoded)")


if __name__ == "__main__":
    main()
