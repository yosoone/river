#!/usr/bin/env python3
"""Rebuild the book's fonts in book/fonts from the full Shippori Mincho files.

Only needed if a text ever uses a character the book fonts lack. Download
ShipporiMincho-Regular.ttf and ShipporiMincho-SemiBold.ttf from
https://github.com/google/fonts/tree/main/ofl/shipporimincho, then:

    python3 book/make_fonts.py /path/to/folder-with-the-full-fonts

Each font is cut down to Latin, punctuation and 川 (about 115 KB instead of
8.7 MB). Its ellipsis (…) is also redrawn as three full stops on the
baseline: Shippori Mincho's own is the Japanese one, centred in a wide box,
which looks out of place in English lines.
"""
import sys
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent

UNICODES = (
    list(range(0x20, 0x7F)) + list(range(0xA0, 0x180)) + list(range(0x2000, 0x2070))
    + [0x2190, 0x2191, 0x2192, 0x2193, 0x2212, 0x5DDD, 0x3001, 0x3002]
)
OUT = Path(__file__).resolve().parent / "fonts"


def latin_ellipsis(font):
    cmap = font.getBestCmap()
    period, ell = cmap[ord(".")], cmap[0x2026]
    adv, lsb = font["hmtx"][period]
    gap = round(adv * 0.12)
    comps = []
    for i in range(3):
        c = GlyphComponent()
        c.glyphName, c.x, c.y, c.flags = period, i * (adv + gap), 0, 0x4 if i == 0 else 0
        comps.append(c)
    g = Glyph()
    g.numberOfContours, g.components = -1, comps
    font["glyf"][ell] = g
    font["hmtx"][ell] = (3 * adv + 2 * gap, lsb)


def main(src):
    OUT.mkdir(exist_ok=True)
    for weight in ("Regular", "SemiBold"):
        font = TTFont(Path(src) / f"ShipporiMincho-{weight}.ttf")
        opts = Options()
        opts.layout_features = ["*"]
        s = Subsetter(opts)
        s.populate(unicodes=UNICODES)
        s.subset(font)
        latin_ellipsis(font)
        font["glyf"].glyphs[font.getBestCmap()[0x2026]].recalcBounds(font["glyf"])
        dest = OUT / f"ShipporiMincho-{weight}-Latin.ttf"
        font.save(dest)
        print(dest.name, dest.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
