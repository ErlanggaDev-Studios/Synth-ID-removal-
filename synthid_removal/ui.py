"""Tampilan terminal untuk Synth-ID Removal.

Semua ornamen (banner, panel, progress bar) dibuat dari karakter ANSI biasa
supaya tetap ringan dan jalan di Termux tanpa dependensi tambahan.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import sys
from typing import List, Optional, Sequence

ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

#: Logo blok besar (lebar 62 kolom); dipakai kalau terminal cukup lebar.
LOGO = [
    "███████╗██╗   ██╗███╗   ██╗████████╗██╗  ██╗    ██╗██████╗ ",
    "██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██║  ██║   ██║██╔══██╗",
    "███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ███████║   ██║██║  ██║",
    "╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██║   ██║██║  ██║",
    "███████║   ██║   ██║ ╚████║   ██║   ██║  ██║██╗██║██████╔╝",
    "╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝╚═════╝ ",
]

LOGO_WIDTH = max(len(line) for line in LOGO)


# --------------------------------------------------------------------------- #
# Warna
# --------------------------------------------------------------------------- #


class Style:
    """Pewarnaan ANSI sederhana."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        if not self.enabled:
            return text
        return f"\x1b[{code}m{text}\x1b[0m"

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)

    def magenta(self, text: str) -> str:
        return self._wrap("35", text)

    def blue(self, text: str) -> str:
        return self._wrap("34", text)


def stream_supports_color(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def visible_len(text: str) -> int:
    """Panjang teks tanpa menghitung kode warna ANSI."""

    return len(ANSI_PATTERN.sub("", text))


def truncate(text: str, limit: int) -> str:
    plain = ANSI_PATTERN.sub("", text)
    if len(plain) <= limit:
        return text
    if limit <= 3:
        return plain[:limit]
    return plain[: limit - 3] + "..."


def terminal_width(stream=None) -> int:
    source = stream or sys.stdout
    try:
        columns = shutil.get_terminal_size((80, 24)).columns
    except OSError:  # pragma: no cover
        columns = 80
    if getattr(source, "isatty", lambda: False)() and os.environ.get("COLUMNS"):
        with contextlib.suppress(ValueError):
            columns = int(os.environ["COLUMNS"])
    return max(40, min(columns, 96))


def pick_symbol(nice: str, fallback: str, stream=None) -> str:
    """Pilih simbol Unicode kalau encoding terminal mendukung."""

    encoding = getattr(stream or sys.stdout, "encoding", None) or "ascii"
    try:
        nice.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return fallback
    return nice


_PROBE = "─│╭╮╰╯▸›·█░✓"


def supports_unicode(stream=None) -> bool:
    """Apakah terminal sanggup menampilkan karakter kotak & simbol?"""

    encoding = getattr(stream or sys.stdout, "encoding", None) or "ascii"
    try:
        _PROBE.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


# --------------------------------------------------------------------------- #
# Panel
# --------------------------------------------------------------------------- #


def draw_panel(
    style: Style,
    lines: Sequence[str],
    title: str = "",
    width: Optional[int] = None,
    color: str = "cyan",
) -> List[str]:
    """Gambar kotak dengan sudut membulat; semua baris lebarnya sama."""

    box_width = max(34, width or min(terminal_width() - 2, 72))
    paint = getattr(style, color, style.cyan)

    if supports_unicode():
        kiri_atas, kanan_atas = "╭", "╮"
        kiri_bawah, kanan_bawah = "╰", "╯"
        garis, tegak = "─", "│"
    else:  # pragma: no cover - terminal non-Unicode
        kiri_atas = kanan_atas = kiri_bawah = kanan_bawah = "+"
        garis, tegak = "-", "|"

    if title:
        label = truncate(f" {title} ", box_width - 4)
        isi = box_width - 3 - visible_len(label)
        top = paint(kiri_atas + garis) + paint(label) + paint(
            garis * max(0, isi) + kanan_atas
        )
    else:
        top = paint(kiri_atas + garis * (box_width - 2) + kanan_atas)

    rows = [top]
    content_width = box_width - 4
    for line in lines:
        body = truncate(line, content_width)
        padding = " " * max(0, content_width - visible_len(body))
        rows.append(paint(tegak) + " " + body + padding + " " + paint(tegak))
    rows.append(paint(kiri_bawah + garis * (box_width - 2) + kanan_bawah))
    return rows


def print_panel(style: Style, lines: Sequence[str], **kwargs) -> None:
    indent = "  "
    for row in draw_panel(style, lines, **kwargs):
        print(indent + row)


# --------------------------------------------------------------------------- #
# Banner
# --------------------------------------------------------------------------- #


def print_banner(style: Style, version: str) -> None:
    """Banner pembuka: logo blok + panel identitas."""

    width = terminal_width()
    full_logo = supports_unicode() and width >= LOGO_WIDTH + 4
    box_width = min(width - 2, 68)

    print()
    if full_logo:
        for line in LOGO:
            print("  " + style.magenta(line.rstrip()))
        print()

    unicode_ok = supports_unicode()
    titik = "▸" if unicode_ok else "*"
    tengah = "·" if unicode_ok else "-"
    baris = [
        style.dim(f"v{version}")
        + "  "
        + style.bold("AI watermark & metadata cleaner"),
        "",
        style.cyan(titik)
        + "  EXIF "
        + tengah
        + " XMP "
        + tengah
        + " ICC dibuang total",
        style.cyan(titik) + "  mikro-resize 1px + geser kontras 0.99",
        style.cyan(titik)
        + "  alpha aman "
        + tengah
        + " tulis atomik "
        + tengah
        + " batch tahan error",
        "",
        style.dim("tarik file ke terminal, atau tempel path-nya"),
    ]
    print_panel(
        style, baris, title="SYNTH-ID REMOVAL", width=box_width, color="magenta"
    )

    cwd = os.getcwd()
    if visible_len(cwd) > box_width - 8:
        cwd = "..." + cwd[-(box_width - 11) :]
    print("  " + style.dim("cwd ") + style.dim(cwd))
    print()


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #


def print_prompt_rule(style: Style, label: str, note: str = "") -> None:
    width = terminal_width() - 4
    teks = f" {label} "
    sisa = max(0, width - visible_len(teks) - 2)
    if supports_unicode():
        print("  " + style.cyan("├─") + style.bold(teks) + style.dim("─" * sisa))
    else:  # pragma: no cover - terminal non-Unicode
        print("  " + style.cyan("|-") + style.bold(teks) + style.dim("-" * sisa))
    tegak = "│ " if supports_unicode() else "| "
    if note:
        print("  " + style.dim(tegak) + style.dim(note))


def print_added(style: Style, count: int) -> None:
    tegak = "│ " if supports_unicode() else "| "
    print("  " + style.dim(tegak) + style.green(f"{count} path siap diproses"))


# --------------------------------------------------------------------------- #
# Progress
# --------------------------------------------------------------------------- #


class ProgressBar:
    """Satu baris progress yang ditulis ulang di tempat."""

    def __init__(self, style: Style, total: int) -> None:
        self.style = style
        self.total = max(1, total)
        self.fill = pick_symbol("█", "#")
        self.empty = pick_symbol("░", "-")
        self.active = False

    def update(self, index: int, label: str) -> None:
        width = min(terminal_width() - 2, 78)
        bar_width = max(12, min(24, width // 3))
        ratio = min(1.0, index / self.total)
        filled = int(round(bar_width * ratio))
        bar = self.fill * filled + self.empty * (bar_width - filled)
        prefix = f"  {bar} {index}/{self.total} "
        room = max(0, width - visible_len(prefix))
        line = prefix + truncate(label, room)
        print("\r" + line + " " * max(0, width - visible_len(line)), end="", flush=True)
        self.active = True

    def clear(self) -> None:
        if not self.active:
            return
        print("\r" + " " * max(0, terminal_width() - 1) + "\r", end="", flush=True)
        self.active = False


__all__ = [
    "LOGO",
    "LOGO_WIDTH",
    "ProgressBar",
    "Style",
    "draw_panel",
    "pick_symbol",
    "print_added",
    "print_banner",
    "print_panel",
    "print_prompt_rule",
    "stream_supports_color",
    "supports_unicode",
    "terminal_width",
    "truncate",
    "visible_len",
]
