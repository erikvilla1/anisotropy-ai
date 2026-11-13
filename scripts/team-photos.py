# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow"]
# ///
"""Cuts the team's portraits for the home page's cards (ADR-0057 amendment 2).

The cards' frames are 4 wide by 5 tall (app/home.css, .home-face-frame). This crops each original in
public/assets/brand/Headshots/ to that shape around the person, makes it 800 by 1000 px and writes it to
public/assets/team/, the files lib/team.ts names:

    uv run scripts/team-photos.py

For each portrait the table gives where the person stands across the picture (0 the left edge, 1 the right) and how far
down the crop starts, as a share of what the crop leaves over; the crop keeps the full width or height where it can.
The originals are not changed.
"""

from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "public" / "assets" / "brand" / "Headshots"
OUT = ROOT / "public" / "assets" / "team"
SIZE = (800, 1000)

# file, name on the card, where the person stands across the picture, how far down the crop starts
PORTRAITS = [
    ("AIAA-V-Christopher-5.jpg", "christopher-valerio", 0.50, 0.00),
    ("Erik.jpeg", "erik-villa", 0.50, 0.30),
    ("IMG_7003.JPG", "kai-saucedo", 0.50, 0.00),
    ("Jus.jpeg", "jusung-park", 0.50, 0.00),
    ("Tab.jpg", "tabassum-zaman", 0.58, 0.00),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for file, name, across, down in PORTRAITS:
        picture = ImageOps.exif_transpose(Image.open(SOURCE / file)).convert("RGB")
        width, height = picture.size
        shape = SIZE[0] / SIZE[1]
        if width / height > shape:  # too wide: keep the height, cut the sides around the person
            crop_w, crop_h = round(height * shape), height
        else:  # too tall: keep the width, cut from the foot (and the top by `down`)
            crop_w, crop_h = width, round(width / shape)
        left = min(max(round(across * width - crop_w / 2), 0), width - crop_w)
        top = round(down * (height - crop_h))
        portrait = picture.crop((left, top, left + crop_w, top + crop_h)).resize(SIZE, Image.LANCZOS)
        target = OUT / f"{name}.jpg"
        portrait.save(target, "JPEG", quality=82, optimize=True, progressive=True)
        print(f"{target.relative_to(ROOT)}: {target.stat().st_size // 1024} KB from {file} ({width} by {height})")


if __name__ == "__main__":
    main()
