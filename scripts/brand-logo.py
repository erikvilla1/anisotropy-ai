# /// script
# requires-python = ">=3.11"
# dependencies = ["svgpathtools"]
# ///
"""Cuts the site's logo files from the designer's approved logo (ADR-0080 amendment 2).

The approved file is the stacked logo on a 1920 by 1080 artboard: the triangle, one path, over the name, one path a letter.
The site sets the two side by side (app/brand.css), so this writes each on its own, cropped to its ink and filled with the
current colour, and the tab icon with the same triangle:

    public/assets/brand/anisotropy-triangle.svg
    public/assets/brand/anisotropy-wordmark.svg
    public/assets/brand/anisotropy-icon.svg

    uv run scripts/brand-logo.py

It prints each file's width and height in the artboard's units, which app/brand.css uses for the proportions. The outlines
are the designer's, unchanged: only the box around them and the fill are set here.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from svgpathtools import parse_path

BRAND = Path(__file__).resolve().parent.parent / "public" / "assets" / "brand"
SOURCE = BRAND / "official" / "Anisotropy Logo approved-03.svg"  # black on white: the paths carry no colour of their own
SVG = "{http://www.w3.org/2000/svg}"


def box(paths: list[str]) -> tuple[float, float, float, float]:
    """The box around some paths: left, top, width, height."""
    boxes = [parse_path(d).bbox() for d in paths]  # each is (xmin, xmax, ymin, ymax)
    left, right = min(b[0] for b in boxes), max(b[1] for b in boxes)
    top, bottom = min(b[2] for b in boxes), max(b[3] for b in boxes)
    return left, top, right - left, bottom - top


def flat(d: str) -> str:
    return " ".join(d.split())


def write(name: str, paths: list[str]) -> tuple[float, float]:
    left, top, width, height = box(paths)
    body = "".join(f'<path fill="currentColor" d="{flat(d)}"/>' for d in paths)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{left:.3f} {top:.3f} {width:.3f} {height:.3f}" '
           f'width="{width:.3f}" height="{height:.3f}">{body}</svg>\n')
    (BRAND / name).write_text(svg)
    print(f"{name}: {width:.1f} by {height:.1f} units, {len(svg)} bytes")
    return width, height


def main() -> None:
    logo = ET.parse(SOURCE).getroot().find(f"{SVG}g")
    name_group, mark_group = logo.findall(f"{SVG}g")
    letters = [path.get("d") for path in name_group.iter(f"{SVG}path")]
    mark = [path.get("d") for path in mark_group.iter(f"{SVG}path")]
    if len(letters) != 10 or len(mark) != 1:
        raise SystemExit(f"expected ten letters and one triangle, found {len(letters)} and {len(mark)}")
    write("anisotropy-wordmark.svg", letters)
    write("anisotropy-triangle.svg", mark)

    # The tab icon: the triangle in the site's light grey, 46 of 64 units wide, centred on the near-black ground.
    left, top, width, height = box(mark)
    scale = 46 / width
    x, y = (64 - width * scale) / 2 - left * scale, (64 - height * scale) / 2 - top * scale
    icon = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#0d0d0d"/>'
            f'<path transform="translate({x:.3f} {y:.3f}) scale({scale:.5f})" fill="#efefef" d="{flat(mark[0])}"/></svg>\n')
    (BRAND / "anisotropy-icon.svg").write_text(icon)
    print(f"anisotropy-icon.svg: {len(icon)} bytes")


if __name__ == "__main__":
    main()
