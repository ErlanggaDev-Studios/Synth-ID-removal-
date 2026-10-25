"""Uji pipeline inti: metadata hilang, ukuran tetap, alpha aman."""

from __future__ import annotations

import pytest
from PIL import Image

from synthid_removal import (
    SanitizeError,
    SanitizeOptions,
    resolve_save_format,
    sanitize_image,
    sanitize_many,
)


def _buka(path):
    image = Image.open(path)
    image.load()
    return image


def test_metadata_dan_exif_hilang(buat_gambar, tmp_path):
    sumber = buat_gambar("asli.png")
    assert _buka(sumber).getexif()  # memang ada EXIF sebelum diproses

    hasil = sanitize_image(sumber, tmp_path / "bersih.png")

    keluaran = _buka(hasil.output)
    try:
        assert dict(keluaran.getexif()) == {}
        assert "parameters" not in keluaran.info
        assert "XML:com.adobe.xmp" not in keluaran.info
        assert "exif" not in keluaran.info
        assert "icc_profile" not in keluaran.info
        assert hasil.source_format == "PNG"
        assert hasil.output_format == "PNG"
        assert hasil.warnings == []
    finally:
        keluaran.close()


def test_ukuran_dan_mode_dipertahankan(buat_gambar, tmp_path):
    sumber = buat_gambar("rgba.png", mode="RGBA", size=(64, 48))
    hasil = sanitize_image(sumber, tmp_path / "out.png")

    assert hasil.size == (64, 48)
    assert hasil.source_mode == "RGBA"
    assert Image.open(hasil.output).mode == "RGBA"


def test_alpha_tidak_ikut_diubah(buat_gambar, tmp_path):
    sumber = buat_gambar("alpha.png", mode="RGBA")
    hasil = sanitize_image(sumber, tmp_path / "alpha_bersih.png")

    with Image.open(hasil.output) as image:
        assert image.getchannel("A").getextrema() == (128, 128)


def test_gambar_1x1_tetap_diproses(buat_gambar, tmp_path):
    sumber = buat_gambar("mini.png", size=(1, 1))
    hasil = sanitize_image(sumber, tmp_path / "mini_bersih.png")
    assert hasil.size == (1, 1)
    assert hasil.output.exists()


def test_metadata_only_tidak_mengubah_piksel(buat_gambar, tmp_path):
    sumber = buat_gambar("asli.png")
    hasil = sanitize_image(
        sumber,
        tmp_path / "salin.png",
        SanitizeOptions(resize_delta=0, contrast=1.0),
    )

    asli = _buka(sumber).convert("RGB")
    salinan = _buka(hasil.output).convert("RGB")
    try:
        assert asli.tobytes() == salinan.tobytes()
    finally:
        asli.close()
        salinan.close()


def test_pipeline_penuh_mengubah_piksel(buat_gambar, tmp_path):
    sumber = buat_gambar("asli.png")
    hasil = sanitize_image(sumber, tmp_path / "ubah.png")

    asli = _buka(sumber).convert("RGB")
    ubah = _buka(hasil.output).convert("RGB")
    try:
        assert asli.tobytes() != ubah.tobytes()
    finally:
        asli.close()
        ubah.close()


def test_png_ke_jpeg_diratakan_ke_putih(buat_gambar, tmp_path):
    sumber = buat_gambar("transparan.png", mode="RGBA")
    hasil = sanitize_image(
        sumber, tmp_path / "foto.jpg", SanitizeOptions(save_format="jpeg")
    )

    with Image.open(hasil.output) as keluaran:
        assert keluaran.format == "JPEG"
        assert keluaran.mode == "RGB"
        assert dict(keluaran.getexif()) == {}
    assert any("Transparansi" in pesan for pesan in hasil.warnings)


def test_output_webp(buat_gambar, tmp_path):
    sumber = buat_gambar("asli.png", mode="RGBA")
    hasil = sanitize_image(sumber, tmp_path / "hasil.webp")
    assert hasil.output_format == "WEBP"
    with Image.open(hasil.output) as keluaran:
        assert keluaran.size == (40, 30)
        assert "A" in keluaran.getbands()


def test_folder_keluaran_dibuat_otomatis(buat_gambar, tmp_path):
    sumber = buat_gambar("asli.png")
    tujuan = tmp_path / "a" / "b" / "hasil.png"
    sanitize_image(sumber, tujuan)
    assert tujuan.is_file()


def test_file_tidak_ada(tmp_path):
    with pytest.raises(SanitizeError):
        sanitize_image(tmp_path / "hilang.png", tmp_path / "out.png")


def test_file_bukan_gambar(tmp_path):
    palsu = tmp_path / "catatan.png"
    palsu.write_text("bukan gambar", encoding="utf-8")
    with pytest.raises(SanitizeError):
        sanitize_image(palsu, tmp_path / "out.png")
    assert not (tmp_path / "out.png").exists()


def test_sanitize_many(buat_gambar, tmp_path):
    satu = buat_gambar("satu.png")
    dua = buat_gambar("dua.jpg")
    hasil = sanitize_many(
        [(satu, tmp_path / "satu_bersih.png"), (dua, tmp_path / "dua_bersih.jpg")]
    )
    assert len(hasil) == 2
    assert all(item.output.is_file() for item in hasil)


@pytest.mark.parametrize(
    ("kwargs", "pesan"),
    [
        ({"resize_delta": -1}, "resize_delta"),
        ({"contrast": 0}, "contrast"),
        ({"contrast": 5}, "contrast"),
        ({"quality": 0}, "quality"),
        ({"quality": 101}, "quality"),
        ({"png_compress_level": -1}, "png_compress_level"),
    ],
)
def test_opsi_tidak_valid(kwargs, pesan):
    with pytest.raises(ValueError, match=pesan):
        SanitizeOptions(**kwargs)


def test_resolve_save_format(tmp_path):
    assert resolve_save_format(tmp_path / "a.png", None) == "PNG"
    assert resolve_save_format(tmp_path / "a.jpg", None) == "JPEG"
    assert resolve_save_format(tmp_path / "a.webp", "png") == "PNG"
    assert resolve_save_format(tmp_path / "a.tanpa_ekstensi", None, "JPEG") == "JPEG"
    assert resolve_save_format(tmp_path / "a.tanpa_ekstensi", None) == "PNG"
    assert resolve_save_format(tmp_path / "a.png", "keep") == "PNG"
    with pytest.raises(SanitizeError):
        resolve_save_format(tmp_path / "a.png", "avif")


def test_gif_keluaran_memberi_peringatan(buat_gambar, tmp_path):
    sumber = buat_gambar("asli.png")
    hasil = sanitize_image(sumber, tmp_path / "hasil.gif")
    assert hasil.output_format == "GIF"
    assert any("GIF" in pesan for pesan in hasil.warnings)


def test_tiff_tidak_dianggap_bermetadata(buat_gambar, tmp_path):
    sumber = buat_gambar("asli.png")
    hasil = sanitize_image(sumber, tmp_path / "hasil.tiff")
    assert hasil.output_format == "TIFF"
    assert not any("Metadata tersisa" in pesan for pesan in hasil.warnings)


def test_webp_tanpa_metadata_tersisa(buat_gambar, tmp_path):
    sumber = buat_gambar("asli.png", mode="RGBA")
    hasil = sanitize_image(sumber, tmp_path / "hasil.webp")
    assert hasil.warnings == []


def test_bmp_memberi_peringatan_alpha(buat_gambar, tmp_path):
    sumber = buat_gambar("asli.png", mode="RGBA")
    hasil = sanitize_image(sumber, tmp_path / "hasil.bmp")
    assert any("transparansi" in pesan for pesan in hasil.warnings)
