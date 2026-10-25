"""Uji ornamen terminal: panel, banner, progress, fallback ASCII."""

from __future__ import annotations

import os

import pytest

from synthid_removal import ui
from synthid_removal.ui import (
    ProgressBar,
    Style,
    draw_panel,
    pick_symbol,
    print_banner,
    print_prompt_rule,
    supports_unicode,
    terminal_width,
    truncate,
    visible_len,
)


class FakeStream:
    """Stream tiruan dengan encoding tertentu."""

    def __init__(self, encoding: str, tty: bool = False) -> None:
        self.encoding = encoding
        self.tty = tty

    def isatty(self) -> bool:
        return self.tty

    def write(self, text: str) -> int:  # pragma: no cover - tidak dipakai
        return len(text)


def test_visible_len_mengabaikan_ansi():
    teks = "\x1b[35mHalo\x1b[0m dunia"
    assert visible_len(teks) == len("Halo dunia")


def test_truncate_pendek_dan_panjang():
    assert truncate("pendek", 10) == "pendek"
    assert truncate("abcdefgh", 5) == "ab..."
    assert truncate("abcdefgh", 2) == "ab"


def test_pick_symbol_fallback_ascii():
    assert pick_symbol("›", ">", FakeStream("ascii")) == ">"
    assert pick_symbol("›", ">", FakeStream("utf-8")) == "›"


def test_supports_unicode_berdasarkan_encoding():
    assert supports_unicode(FakeStream("utf-8"))
    assert not supports_unicode(FakeStream("ascii"))


def test_panel_semua_baris_sama_lebar():
    panel = draw_panel(
        Style(True),
        ["baris satu", "baris dua yang sangat panjang sekali melebihi lebar panel"],
        title="judul",
        width=40,
    )
    lebar = {visible_len(baris) for baris in panel}
    assert len(lebar) == 1
    assert lebar.pop() == 40
    assert panel[0].startswith("\x1b[36m╭")
    assert panel[-1].rstrip().endswith("╯\x1b[0m")


def test_panel_bisa_tanpa_warna():
    panel = draw_panel(Style(False), [""], width=36)
    assert all(visible_len(baris) == 36 for baris in panel)
    assert "\x1b" not in "".join(panel)


def test_panel_fallback_ascii(monkeypatch):
    monkeypatch.setattr(ui, "supports_unicode", lambda stream=None: False)
    panel = draw_panel(Style(False), ["halo"], title="judul", width=40)
    assert panel[0].startswith("+")
    assert all(baris.startswith(("+", "|")) for baris in panel)
    assert "╭" not in "".join(panel)


def test_banner_lebar_menampilkan_logo(capsys, monkeypatch):
    monkeypatch.setattr(ui, "terminal_width", lambda stream=None: 96)
    print_banner(Style(False), "1.1.0")

    keluaran = capsys.readouterr().out
    assert "███████" in keluaran
    assert "SYNTH-ID REMOVAL" in keluaran
    assert "v1.1.0" in keluaran


def test_banner_sempit_tanpa_logo(capsys, monkeypatch):
    monkeypatch.setattr(ui, "terminal_width", lambda stream=None: 50)
    print_banner(Style(False), "1.1.0")

    keluaran = capsys.readouterr().out
    assert "SYNTH-ID REMOVAL" in keluaran
    assert "███████" not in keluaran
    for baris in keluaran.splitlines():
        assert visible_len(baris) <= 50


def test_banner_ascii_aman(monkeypatch, capsys):
    monkeypatch.setattr(ui, "supports_unicode", lambda stream=None: False)
    monkeypatch.setattr(ui, "terminal_width", lambda stream=None: 70)

    print_banner(Style(False), "1.1.0")
    keluaran = capsys.readouterr().out
    assert "SYNTH-ID REMOVAL" in keluaran
    assert "╭" not in keluaran
    assert "▸" not in keluaran


def test_prompt_rule_dan_tambahan(capsys, monkeypatch):
    monkeypatch.setattr(ui, "terminal_width", lambda stream=None: 60)
    print_prompt_rule(Style(False), "path gambar", "tarik file ke sini")
    ui.print_added(Style(False), 2)

    baris = capsys.readouterr().out.splitlines()
    assert any("path gambar" in item for item in baris)
    assert any("tarik file" in item for item in baris)
    assert any("2 path siap diproses" in item for item in baris)


def test_progress_bar_menulis_dan_bersih(capsys):
    bar = ProgressBar(Style(False), 4)
    bar.update(1, "satu.png")
    keluaran = capsys.readouterr().out
    assert "1/4" in keluaran
    assert "satu.png" in keluaran
    assert "\n" not in keluaran

    bar.clear()
    assert capsys.readouterr().out.strip() == ""


def test_progress_bar_unicode_fallback(monkeypatch):
    monkeypatch.setattr(ui, "pick_symbol", lambda nice, fallback, stream=None: fallback)
    bar = ProgressBar(Style(False), 2)
    assert bar.fill == "#"
    assert bar.empty == "-"


def test_terminal_width_dibatasi(monkeypatch):
    monkeypatch.setattr(
        ui.shutil,
        "get_terminal_size",
        lambda fallback=None: os.terminal_size((200, 40)),
    )
    assert terminal_width(FakeStream("utf-8")) == 96

    monkeypatch.setattr(
        ui.shutil,
        "get_terminal_size",
        lambda fallback=None: os.terminal_size((10, 40)),
    )
    assert terminal_width(FakeStream("utf-8")) == 40


def test_terminal_width_menghormati_columns(monkeypatch):
    monkeypatch.setenv("COLUMNS", "72")
    monkeypatch.setattr(
        ui.shutil,
        "get_terminal_size",
        lambda fallback=None: os.terminal_size((100, 40)),
    )
    assert terminal_width(FakeStream("utf-8", tty=True)) == 72


def test_terminal_width_columns_tidak_valid(monkeypatch):
    monkeypatch.setenv("COLUMNS", "bukan-angka")
    monkeypatch.setattr(
        ui.shutil,
        "get_terminal_size",
        lambda fallback=None: os.terminal_size((80, 40)),
    )
    assert terminal_width(FakeStream("utf-8", tty=True)) == 80


def test_style_tanpa_warna():
    style = Style(False)
    assert style.bold("x") == "x"
    assert "\x1b[" in Style(True).bold("x")


@pytest.mark.parametrize("color", ["green", "yellow", "red", "cyan", "magenta", "blue"])
def test_style_memiliki_warna(color):
    style = Style(True)
    assert getattr(style, color)("x").startswith("\x1b[")
