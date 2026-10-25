#!/usr/bin/env python3
"""Buat ikon PWA (PNG) dari geometri sederhana.

Jalankan dari mana saja::

    python3 web/tools/make_icons.py

Output ditulis ke ``web/public/icons/``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent.parent / "public" / "icons"

TOP = (21, 16, 38)
BOTTOM = (9, 11, 16)
CYAN = (70, 216, 224)
MAGENTA = (255, 79, 147)

SUPERSAMPLE = 2


def gradient(size: int) -> Image.Image:
    """Gradien vertikal halus dari TOP ke BOTTOM."""

    strip = Image.new("RGBA", (1, size))
    draw = ImageDraw.Draw(strip)
    for y in range(size):
        ratio = y / max(1, size - 1)
        draw.point(
            (0, y),
            fill=(
                round(TOP[0] + (BOTTOM[0] - TOP[0]) * ratio),
                round(TOP[1] + (BOTTOM[1] - TOP[1]) * ratio),
                round(TOP[2] + (BOTTOM[2] - TOP[2]) * ratio),
                255,
            ),
        )
    return strip.resize((size, size), Image.Resampling.BILINEAR)


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=radius, fill=255
    )
    return mask


def draw_mark(image: Image.Image, size: int) -> None:
    """Cincin watermark + garis miring (simbol 'dibersihkan')."""

    draw = ImageDraw.Draw(image, "RGBA")
    center = size / 2
    ring_radius = size * 0.255
    ring_width = size * 0.048
    box = (
        center - ring_radius,
        center - ring_radius,
        center + ring_radius,
        center + ring_radius,
    )

    # Glow tipis di belakang cincin.
    draw.ellipse(box, outline=CYAN + (55,), width=round(ring_width * 2.1))
    draw.ellipse(box, outline=CYAN + (255,), width=round(ring_width))

    # Garis miring magenta dengan ujung membulat.
    start = (size * 0.315, size * 0.685)
    end = (size * 0.685, size * 0.315)
    width = round(size * 0.082)
    draw.line([start, end], fill=MAGENTA + (255,), width=width)
    for point in (start, end):
        radius = width / 2
        draw.ellipse(
            (
                point[0] - radius,
                point[1] - radius,
                point[0] + radius,
                point[1] + radius,
            ),
            fill=MAGENTA + (255,),
        )


def build(size: int, maskable: bool) -> Image.Image:
    work = size * SUPERSAMPLE
    canvas = gradient(work).convert("RGBA")
    draw_mark(canvas, work)

    if maskable:
        # Latar penuh supaya aman saat dipotong bentuk apa pun.
        return canvas.resize((size, size), Image.Resampling.LANCZOS)

    rounded = Image.new("RGBA", (work, work), (0, 0, 0, 0))
    rounded.paste(canvas, (0, 0), rounded_mask(work, round(work * 0.225)))
    return rounded.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "icon-192.png": build(192, maskable=False),
        "icon-512.png": build(512, maskable=False),
        "icon-maskable-512.png": build(512, maskable=True),
        "apple-touch-icon-180.png": build(180, maskable=True),
    }
    for name, image in outputs.items():
        path = OUT_DIR / name
        image.save(path, optimize=True)
        print(f"  {path.relative_to(OUT_DIR.parent.parent)} ({path.stat().st_size} B)")


if __name__ == "__main__":
    main()
