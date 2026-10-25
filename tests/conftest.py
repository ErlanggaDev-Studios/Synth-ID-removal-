"""Fixture bersama untuk pengujian."""

from __future__ import annotations

import pytest
from PIL import Image, PngImagePlugin


@pytest.fixture
def buat_gambar(tmp_path):
    """Factory pembuat gambar uji lengkap dengan metadata.

    Contoh::

        path = buat_gambar("uji.png")
        path = buat_gambar("uji.jpg", mode="RGB")
    """

    def factory(
        name: str = "gambar.png",
        size: tuple = (40, 30),
        mode: str = "RGB",
        metadata: bool = True,
        folder=None,
    ):
        path = (folder or tmp_path) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        color = (180, 40, 90, 128) if "A" in mode else (180, 40, 90)
        image = Image.new(mode, size, color)
        suffix = path.suffix.lower()
        kwargs = {}

        if suffix == ".png":
            info = PngImagePlugin.PngInfo()
            if metadata:
                info.add_text("parameters", "prompt: uji")
                info.add_itxt("XML:com.adobe.xmp", "<x:xmpmeta/>")
            kwargs["pnginfo"] = info
            if metadata:
                exif = Image.Exif()
                exif[0x010E] = "AI generated"
                kwargs["exif"] = exif
        elif suffix in (".jpg", ".jpeg"):
            if "A" in mode:
                image = image.convert("RGB")
            if metadata:
                exif = Image.Exif()
                exif[0x010E] = "AI generated"
                kwargs["exif"] = exif

        image.save(path, **kwargs)
        image.close()
        return path

    return factory
