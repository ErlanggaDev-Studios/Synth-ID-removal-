"""Uji pengumpulan file masukan dan penentuan path keluaran."""

from __future__ import annotations

from pathlib import Path

import pytest

from synthid_removal.files import (
    clean_token,
    expand_inputs,
    is_directory_target,
    is_supported_image,
    output_path_for,
    same_file,
    scan_directory,
)
from synthid_removal.sanitizer import SanitizeError


def test_clean_token_membuang_kutip(tmp_path):
    assert clean_token("'/tmp/a b.png'") == "/tmp/a b.png"
    assert clean_token('"/tmp/a b.png"') == "/tmp/a b.png"


def test_clean_token_membuang_escape_spasi():
    assert clean_token("/tmp/a\\ b.png") == "/tmp/a b.png"


def test_clean_token_expand_user():
    assert clean_token("~/gambar.png").endswith("/gambar.png")
    assert clean_token("~/gambar.png").startswith("/")


def test_clean_token_variabel_lingkungan(monkeypatch):
    monkeypatch.setenv("FOLDER_UJI", "/tmp/folder")
    assert clean_token("$FOLDER_UJI/a.png") == "/tmp/folder/a.png"


def test_is_supported_image():
    assert is_supported_image(Path("a.PNG"))
    assert is_supported_image(Path("a.jpeg"))
    assert not is_supported_image(Path("a.txt"))


def test_scan_directory_melewati_file_tersembunyi(buat_gambar, tmp_path):
    buat_gambar("satu.png")
    buat_gambar("dua.jpg")
    buat_gambar(".tersembunyi.png")
    (tmp_path / "catatan.txt").write_text("x", encoding="utf-8")

    hasil = scan_directory(tmp_path)
    assert [item.name for item in hasil] == ["dua.jpg", "satu.png"]


def test_scan_directory_rekursif(buat_gambar, tmp_path):
    buat_gambar("atas.png")
    sub = tmp_path / "sub"
    buat_gambar("dalam.png", size=(8, 8), folder=sub)

    assert len(scan_directory(tmp_path)) == 1
    assert len(scan_directory(tmp_path, recursive=True)) == 2


def test_expand_inputs_folder_dan_file(buat_gambar, tmp_path):
    satu = buat_gambar("satu.png")
    dua = buat_gambar("dua.jpg")

    hasil, masalah = expand_inputs([str(tmp_path), str(satu)])
    assert masalah == []
    assert {item.name for item in hasil} == {"satu.png", "dua.jpg"}
    assert len(hasil) == 2  # duplikat dibuang
    assert dua.name in {item.name for item in hasil}


def test_expand_inputs_glob(buat_gambar, tmp_path):
    buat_gambar("satu.png")
    buat_gambar("dua.png")
    buat_gambar("tiga.jpg")

    hasil, masalah = expand_inputs([str(tmp_path / "*.png")])
    assert masalah == []
    assert len(hasil) == 2


def test_expand_inputs_path_tidak_ada(tmp_path):
    hasil, masalah = expand_inputs([str(tmp_path / "hilang.png")])
    assert hasil == []
    assert len(masalah) == 1
    assert "tidak ditemukan" in masalah[0]


def test_expand_inputs_format_tidak_didukung(tmp_path):
    catatan = tmp_path / "catatan.txt"
    catatan.write_text("x", encoding="utf-8")

    hasil, masalah = expand_inputs([str(catatan)])
    assert hasil == []
    assert "tidak didukung" in masalah[0]


def test_expand_inputs_folder_kosong(tmp_path):
    hasil, masalah = expand_inputs([str(tmp_path)])
    assert hasil == []
    assert "Tidak ada gambar" in masalah[0]


def test_expand_inputs_kutip_dan_spasi(buat_gambar, tmp_path):
    berkas = buat_gambar("nama dengan spasi.png")
    hasil, masalah = expand_inputs([f"'{berkas}'"])
    assert masalah == []
    assert hasil == [berkas]


def test_output_path_for_default(tmp_path):
    sumber = tmp_path / "foto.png"
    assert output_path_for(sumber, None, "_clean", None) == tmp_path / "foto_clean.png"


def test_output_path_for_ganti_format(tmp_path):
    sumber = tmp_path / "foto.jpeg"
    hasil = output_path_for(sumber, None, "_clean", "webp")
    assert hasil.name == "foto_clean.webp"


def test_output_path_for_folder(tmp_path):
    sumber = tmp_path / "foto.png"
    folder = tmp_path / "bersih"
    folder.mkdir()
    assert output_path_for(sumber, folder, "_clean", None) == folder / "foto_clean.png"


def test_output_path_for_folder_belum_ada(tmp_path):
    sumber = tmp_path / "foto.png"
    tujuan = tmp_path / "baru"
    hasil = output_path_for(sumber, tujuan, "_clean", None, force_directory=True)
    assert hasil == tujuan / "foto_clean.png"


def test_output_path_for_file_tunggal(tmp_path):
    sumber = tmp_path / "foto.png"
    hasil = output_path_for(sumber, tmp_path / "khusus.png", "_clean", None)
    assert hasil == tmp_path / "khusus.png"


def test_suffix_kosong_tanpa_format(tmp_path):
    sumber = tmp_path / "foto.png"
    assert output_path_for(sumber, None, "", None) == sumber


def test_is_directory_target(tmp_path):
    assert is_directory_target(tmp_path)
    assert is_directory_target(Path(str(tmp_path) + "/"))
    assert is_directory_target(tmp_path / "belum-ada")
    assert not is_directory_target(tmp_path / "belum-ada.png")
    assert not is_directory_target(tmp_path / "belum-ada.webp")


def test_same_file_relatif_vs_absolut(tmp_path, monkeypatch):
    berkas = tmp_path / "a.png"
    berkas.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert same_file(Path("a.png"), berkas)


def test_format_tidak_dikenal(tmp_path):
    with pytest.raises(SanitizeError):
        output_path_for(tmp_path / "a.png", None, "_clean", "avif")
