#!/usr/bin/env python3
"""Make the Noto font subsets in fonts/noto/ that the builders merge into the game's fonts.

  make_noto_subsets.py [--commit SHA]

Downloads Noto Sans, Noto Serif and Noto Sans SC (SIL Open Font License 1.1)
from github.com/google/fonts at a pinned commit (the one fonts/noto/sources.json
names, or --commit), makes static instances at the weights the game's fonts
need, and keeps only the letters the builders add:

- Latin Extended, Vietnamese, Greek (with accents), Cyrillic, some punctuation
  (REPLACE_RANGES): these replace the game's own glyphs, so Cyrillic and Greek
  get normal widths;
- the Simplified Chinese characters Japanese does not use (simplified_only()).
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fonts/noto"
REPLACE_RANGES = (
    (0x0100, 0x024F),  # Latin Extended-A and -B
    (0x0300, 0x036F),  # combining accents
    (0x0370, 0x03FF),  # Greek
    (0x0400, 0x052F),  # Cyrillic and its supplement
    (0x1E00, 0x1EFF),  # Latin Extended Additional (Vietnamese)
    (0x1F00, 0x1FFF),  # Greek Extended
    (0x2010, 0x2027),  # dashes, quotes, ellipsis
)
UPSTREAM = {
    "NotoSans": "ofl/notosans/NotoSans[wdth,wght].ttf",
    "NotoSerif": "ofl/notoserif/NotoSerif[wdth,wght].ttf",
    "NotoSansSC": "ofl/notosanssc/NotoSansSC[wght].ttf",
    "OFL.txt": "ofl/notosans/OFL.txt",
}
# file written: (upstream font, weight, codepoints)
OUTPUTS = {
    "NotoSans-400.ttf": ("NotoSans", 400, "replaced"),
    "NotoSans-600.ttf": ("NotoSans", 600, "replaced"),
    "NotoSerif-400.ttf": ("NotoSerif", 400, "replaced"),
    "NotoSansSC-400.ttf": ("NotoSansSC", 400, "simplified"),
    "NotoSansSC-600.ttf": ("NotoSansSC", 600, "simplified"),
}
DROP = ("GSUB", "GPOS", "GDEF", "BASE", "vhea", "vmtx", "VORG", "kern", "JSTF", "MATH", "DSIG", "STAT",
        "HVAR", "MVAR", "meta", "fvar", "gvar", "avar", "cvar")


def replaced_codepoints() -> frozenset[int]:
    """The codepoints whose glyphs come from Noto in place of the game's."""
    return frozenset(c for first, last in REPLACE_RANGES for c in range(first, last + 1))


def _encodes(char: str, codec: str) -> bool:
    try:
        char.encode(codec)
    except UnicodeEncodeError:
        return False
    return True


def simplified_only() -> frozenset[int]:
    """CJK ideographs in GB2312 (Simplified Chinese) that JIS X 0208 (Japanese) lacks."""
    return frozenset(c for c in range(0x4E00, 0xA000)
                     if _encodes(chr(c), "gb2312") and not _encodes(chr(c), "shift_jis"))


def _subset(source: Path, weight: int, codepoints: frozenset[int], out: Path):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    font = TTFont(source)
    axes = {"wght": float(weight)}
    if any(a.axisTag == "wdth" for a in font["fvar"].axes):
        axes["wdth"] = 100.0
    font = instancer.instantiateVariableFont(font, axes)
    for tag in DROP:
        if tag in font:
            del font[tag]
    options = subset.Options()
    options.layout_features = []
    options.notdef_outline = True
    options.hinting = False
    options.glyph_names = False
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=codepoints)
    subsetter.subset(font)
    font.save(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--commit", help="google/fonts commit (default: the one in fonts/noto/sources.json)")
    args = parser.parse_args(argv)
    commit = args.commit
    if not commit:
        commit = json.loads((OUT / "sources.json").read_text())["commit"]
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {"commit": commit, "ranges": [list(r) for r in REPLACE_RANGES], "files": {}}
    with tempfile.TemporaryDirectory() as temp:
        downloads = {}
        for name, path in UPSTREAM.items():
            url = f"https://raw.githubusercontent.com/google/fonts/{commit}/{path}"
            target = Path(temp) / name
            print("Downloading", url, file=sys.stderr)
            with urllib.request.urlopen(url) as response:
                target.write_bytes(response.read())
            sources["files"][name] = {"source": url, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
            downloads[name] = target
        (OUT / "OFL.txt").write_bytes(downloads["OFL.txt"].read_bytes())
        sets = {"replaced": replaced_codepoints(), "simplified": simplified_only()}
        for name, (upstream, weight, which) in OUTPUTS.items():
            _subset(downloads[upstream], weight, sets[which], OUT / name)
            print(name, (OUT / name).stat().st_size, file=sys.stderr)
    (OUT / "sources.json").write_text(json.dumps(sources, indent=1) + "\n")


if __name__ == "__main__":
    main()
