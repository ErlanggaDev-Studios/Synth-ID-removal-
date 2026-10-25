"""Pengumpulan file masukan dan penentuan path keluaran.

Semua bentuk masukan yang wajar didukung: satu file, banyak file, folder
(opsional rekursif), pola glob, path hasil drag & drop (dengan tanda kutip atau
backslash escape), ``~``, dan variabel lingkungan.
"""

from __future__ import annotations

import glob as globlib
import os
import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .sanitizer import (
    EXTENSION_FORMATS,
    IMAGE_SUFFIXES,
    SanitizeError,
    output_suffix_for,
)

#: Escape yang biasa dihasilkan drag & drop terminal (mis. ``/a\ b.png``).
_ESCAPE_PATTERN = re.compile(r"\\([ \t()\[\]{}&'\"!#$*?;])")


def clean_token(token: str) -> str:
    """Rapikan satu argumen path dari shell/drag & drop."""

    text = token.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1]
    if "\\" in text:
        text = _ESCAPE_PATTERN.sub(r"\1", text)
    text = os.path.expandvars(os.path.expanduser(text.strip()))
    return text


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def scan_directory(directory: Path, recursive: bool = False) -> List[Path]:
    """Cari semua gambar di dalam folder, urut berdasarkan nama."""

    try:
        entries = directory.rglob("*") if recursive else directory.glob("*")
        found = [
            entry
            for entry in entries
            if entry.is_file()
            and not entry.name.startswith(".")
            and is_supported_image(entry)
        ]
    except OSError as exc:
        raise SanitizeError(f"Folder tidak bisa dibaca: {directory} ({exc})") from exc

    return sorted(found, key=lambda item: str(item).lower())


def expand_inputs(
    tokens: Sequence[str], recursive: bool = False
) -> Tuple[List[Path], List[str]]:
    """Ubah argumen CLI menjadi daftar file gambar.

    Returns:
        (file_gambar, masalah) - ``masalah`` berisi pesan untuk path yang
        tidak ditemukan atau formatnya tidak didukung.
    """

    files: List[Path] = []
    problems: List[str] = []
    seen = set()

    def add(candidate: Path) -> None:
        try:
            key = candidate.resolve()
        except OSError:  # pragma: no cover - path sangat aneh
            key = candidate.absolute()
        if key in seen:
            return
        seen.add(key)
        files.append(candidate)

    for raw in tokens:
        token = clean_token(raw)
        if not token:
            continue

        path = Path(token)
        if path.is_dir():
            matches = scan_directory(path, recursive=recursive)
            if not matches:
                problems.append(f"Tidak ada gambar didukung di folder: {path}")
            for match in matches:
                add(match)
            continue

        if path.is_file():
            candidates = [path]
        else:
            matches = globlib.glob(token, recursive=recursive)
            if not matches:
                problems.append(f"Path tidak ditemukan: {raw}")
                continue
            candidates = [Path(match) for match in matches]

        for candidate in candidates:
            if candidate.is_dir():
                for match in scan_directory(candidate, recursive=recursive):
                    add(match)
                continue
            if not candidate.is_file():
                problems.append(f"Path tidak ditemukan: {candidate}")
                continue
            if not is_supported_image(candidate):
                problems.append(f"Format tidak didukung, dilewati: {candidate}")
                continue
            add(candidate)

    return files, problems


def is_directory_target(output: Path) -> bool:
    """Apakah ``output`` dimaksudkan sebagai folder?

    Path tanpa ekstensi gambar (``hasil``, ``bersih/``) dianggap folder supaya
    ``-o hasil`` tidak menghasilkan file tanpa ekstensi.
    """

    if output.is_dir():
        return True
    text = str(output)
    if text.endswith(("/", os.sep)) or text in (".", ".."):
        return True
    return output.suffix.lower() not in EXTENSION_FORMATS


def output_path_for(
    source: Path,
    output: Optional[Path],
    suffix: str,
    requested_format: Optional[str],
    force_directory: bool = False,
) -> Path:
    """Hitung path keluaran untuk satu file sumber.

    Args:
        force_directory: Perlakukan ``output`` sebagai folder meskipun belum
            ada dan tidak diakhiri garis miring (dipakai untuk batch).
    """

    extension = output_suffix_for(source, requested_format)

    if output is None:
        return source.with_name(f"{source.stem}{suffix}{extension}")
    if force_directory or is_directory_target(output):
        return output / f"{source.stem}{suffix}{extension}"
    return output


def same_file(first: Path, second: Path) -> bool:
    """Bandingkan dua path tanpa peduli symlink/relative."""

    try:
        return first.resolve() == second.resolve()
    except OSError:  # pragma: no cover
        return first.absolute() == second.absolute()


__all__ = [
    "clean_token",
    "expand_inputs",
    "is_directory_target",
    "is_supported_image",
    "output_path_for",
    "same_file",
    "scan_directory",
]
