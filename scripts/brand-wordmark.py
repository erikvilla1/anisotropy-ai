# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools", "brotli", "uharfbuzz"]
# ///
"""Draws the logo's name as vector outlines (ADR-0080 amendments 1 and 3).

The name ANISOTROPY is set in Archivo at weight 800 with the font's own kerning and a tracking of -0.01 em, then written as one
path to public/assets/brand/anisotropy-wordmark.svg, cropped to the letters' ink. The page draws that file through a CSS mask
(app/brand.css), so no font is loaded for ten letters.

Archivo is under the SIL Open Font License 1.1. The font file is not in the repository; it comes from the npm package
@fontsource/archivo (files/archivo-latin-800-normal.woff2):

    npm pack @fontsource/archivo && tar -xzf fontsource-archivo-*.tgz
    uv run scripts/brand-wordmark.py package/files/archivo-latin-800-normal.woff2

It prints the outline's width, height and cap height, which app/brand.css uses for the name's proportions.
"""

import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

TEXT = "ANISOTROPY"
TRACKING_EM = -0.01
OUT = Path(__file__).resolve().parent.parent / "public" / "assets" / "brand" / "anisotropy-wordmark.svg"


def main(font_path: str) -> None:
    font = TTFont(font_path)
    font.flavor = None  # harfbuzz reads plain sfnt data, not woff2
    plain = Path(font_path).with_suffix(".ttf")
    font.save(plain)
    upem = font["head"].unitsPerEm
    glyphs = font.getGlyphSet()
    order = font.getGlyphOrder()

    hb_font = hb.Font(hb.Face(plain.read_bytes()))
    buffer = hb.Buffer()
    buffer.add_str(TEXT)
    buffer.guess_segment_properties()
    hb.shape(hb_font, buffer, {"kern": True})

    # Each glyph at its pen position, y turned downwards for SVG.
    placed, x = [], 0.0
    for info, pos in zip(buffer.glyph_infos, buffer.glyph_positions):
        placed.append((order[info.codepoint], x + pos.x_offset))
        x += pos.x_advance + TRACKING_EM * upem

    bounds = BoundsPen(glyphs)
    for name, at in placed:
        glyphs[name].draw(TransformPen(bounds, (1, 0, 0, 1, at, 0)))
    left, bottom, right, top = bounds.bounds

    path = SVGPathPen(glyphs, ntos=lambda value: f"{value:.1f}".rstrip("0").rstrip("."))
    for name, at in placed:
        glyphs[name].draw(TransformPen(path, (1, 0, 0, -1, at - left, top)))

    width, height = right - left, top - bottom
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" width="{width:g}" height="{height:g}">'
        f'<path fill="currentColor" d="{path.getCommands()}"/></svg>\n'
    )
    OUT.write_text(svg)
    plain.unlink()
    print(f"{OUT.name}: {width:g} by {height:g} units, cap height {font['OS/2'].sCapHeight}, {len(svg)} bytes")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: uv run scripts/brand-wordmark.py <archivo-latin-800-normal.woff2>")
    main(sys.argv[1])
