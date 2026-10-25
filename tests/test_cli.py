"""Uji CLI dari ujung ke ujung (tanpa subprocess)."""

from __future__ import annotations

import io
import json

import pytest
from PIL import Image

from synthid_removal.cli import build_parser, main


def _buka(path):
    image = Image.open(path)
    image.load()
    return image


def test_proses_default_menulis_suffix_clean(buat_gambar):
    sumber = buat_gambar("foto.png")
    kode = main([str(sumber)])

    assert kode == 0
    keluaran = sumber.with_name("foto_clean.png")
    assert keluaran.is_file()
    with Image.open(keluaran) as image:
        assert dict(image.getexif()) == {}
        assert "parameters" not in image.info


def test_suffix_dan_folder_keluaran(buat_gambar, tmp_path):
    sumber = buat_gambar("foto.png")
    tujuan = tmp_path / "hasil"
    tujuan.mkdir()

    kode = main([str(sumber), "-s", "_bersih", "-o", str(tujuan)])
    assert kode == 0
    assert (tujuan / "foto_bersih.png").is_file()


def test_keluaran_sudah_ada_menolak(buat_gambar, capsys):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber)]) == 0
    capsys.readouterr()

    kode = main([str(sumber)])
    assert kode == 1
    assert "sudah ada" in capsys.readouterr().err


def test_force_menimpa(buat_gambar):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber)]) == 0
    assert main([str(sumber), "--force"]) == 0


def test_skip_existing(buat_gambar, tmp_path):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber)]) == 0
    keluaran = tmp_path / "foto_clean.png"
    sebelum = keluaran.stat().st_mtime_ns

    assert main([str(sumber), "--skip-existing"]) == 0
    assert keluaran.stat().st_mtime_ns == sebelum


def test_unique_membuat_nama_baru(buat_gambar, tmp_path):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber)]) == 0
    assert main([str(sumber), "--unique"]) == 0
    assert (tmp_path / "foto_clean (1).png").is_file()


def test_json_keluaran_valid(buat_gambar, capsys):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber), "--json"]) == 0

    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "ok"
    assert len(data["processed"]) == 1
    assert data["processed"][0]["output_format"] == "PNG"
    assert data["failed"] == []


def test_dry_run_tidak_menulis(buat_gambar, tmp_path):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber), "--dry-run"]) == 0
    assert not (tmp_path / "foto_clean.png").exists()


def test_metadata_only_piksel_sama(buat_gambar, tmp_path):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber), "--metadata-only"]) == 0

    asli = _buka(sumber).convert("RGB")
    keluaran = _buka(tmp_path / "foto_clean.png").convert("RGB")
    try:
        assert asli.tobytes() == keluaran.tobytes()
    finally:
        asli.close()
        keluaran.close()


def test_banyak_file_ke_folder(buat_gambar, tmp_path):
    satu = buat_gambar("satu.png")
    dua = buat_gambar("dua.jpg")
    tujuan = tmp_path / "keluar"

    kode = main([str(satu), str(dua), "-o", str(tujuan)])
    assert kode == 0
    assert (tujuan / "satu_clean.png").is_file()
    assert (tujuan / "dua_clean.jpg").is_file()


def test_tanpa_argumen_dan_stdin_kosong(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main([]) == 2


def test_path_dari_stdin(buat_gambar, tmp_path, monkeypatch):
    sumber = buat_gambar("foto.png")
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{sumber}\n"))
    assert main([]) == 0
    assert (tmp_path / "foto_clean.png").is_file()


def test_path_berspasi_dari_stdin(buat_gambar, tmp_path, monkeypatch):
    sumber = buat_gambar("foto ai keren.png")
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{sumber}\n"))
    assert main([]) == 0
    assert (tmp_path / "foto ai keren_clean.png").is_file()


def test_output_tanpa_ekstensi_jadi_folder(buat_gambar, tmp_path):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber), "-o", str(tmp_path / "bersih")]) == 0
    assert (tmp_path / "bersih" / "foto_clean.png").is_file()


def test_format_gif(buat_gambar, tmp_path):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber), "-f", "gif"]) == 0
    assert (tmp_path / "foto_clean.gif").is_file()


def test_path_tidak_ditemukan(tmp_path, capsys):
    assert main([str(tmp_path / "hilang.png")]) == 1
    assert "Tidak ada gambar" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argumen",
    [
        ["--force", "--skip-existing"],
        ["--force", "--unique"],
        ["--quality", "0"],
        ["--quality", "200"],
        ["--resize-delta", "-1"],
        ["--contrast", "0"],
        ["--contrast", "9"],
        ["--metadata-only", "--contrast", "0.5"],
    ],
)
def test_kombinasi_argumen_salah(argumen):
    with pytest.raises(SystemExit) as info:
        main(["contoh.png", *argumen])
    assert info.value.code == 2


def test_inplace_dengan_force(buat_gambar, tmp_path):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber), "-o", str(sumber), "--force"]) == 0
    assert sumber.is_file()
    with Image.open(sumber) as image:
        assert dict(image.getexif()) == {}


def test_inplace_format_tidak_cocok(buat_gambar, capsys):
    sumber = buat_gambar("foto.png")
    kode = main([str(sumber), "-o", str(sumber), "-f", "jpeg", "--force"])
    assert kode == 1
    assert "tidak cocok" in capsys.readouterr().err


def test_nama_bentrok_tanpa_unique(buat_gambar, tmp_path, capsys):
    a = buat_gambar("x.png", folder=tmp_path / "a")
    b = buat_gambar("x.png", folder=tmp_path / "b")
    tujuan = tmp_path / "keluar"

    kode = main([str(a), str(b), "-o", str(tujuan)])
    assert kode == 1
    assert "bentrok" in capsys.readouterr().err
    assert (tujuan / "x_clean.png").is_file()


def test_nama_bentrok_dengan_unique(buat_gambar, tmp_path):
    a = buat_gambar("x.png", folder=tmp_path / "a")
    b = buat_gambar("x.png", folder=tmp_path / "b")
    tujuan = tmp_path / "keluar"

    assert main([str(a), str(b), "-o", str(tujuan), "--unique"]) == 0
    assert (tujuan / "x_clean.png").is_file()
    assert (tujuan / "x_clean (1).png").is_file()


def test_ganti_format_webp(buat_gambar, tmp_path):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber), "-f", "webp"]) == 0
    keluaran = tmp_path / "foto_clean.webp"
    assert keluaran.is_file()
    with Image.open(keluaran) as image:
        assert image.format == "WEBP"


def test_quiet_hanya_ringkasan(buat_gambar, capsys):
    sumber = buat_gambar("foto.png")
    assert main([str(sumber), "--quiet"]) == 0
    keluaran = capsys.readouterr().out
    assert "Selesai" in keluaran
    assert "[1/1]" not in keluaran


def test_file_rusak_dilaporkan(buat_gambar, tmp_path, capsys):
    sumber = buat_gambar("foto.png")
    rusak = tmp_path / "rusak.png"
    rusak.write_bytes(b"\x89PNG\r\n\x1a\nbukan isi png")

    kode = main([str(sumber), str(rusak)])
    assert kode == 1
    keluaran = capsys.readouterr()
    assert "rusak.png" in keluaran.err
    assert (tmp_path / "foto_clean.png").is_file()


def test_version_keluar_bersih(capsys):
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert "synthid-clean" in capsys.readouterr().out


def test_parser_punya_opsi_utama():
    parser = build_parser()
    opsi = {action.dest for action in parser._actions}
    assert {"inputs", "output", "format", "quality", "suffix", "force"} <= opsi
