#!/usr/bin/env python3
"""Titik masuk sederhana: ``python main.py [GAMBAR ...]``.

Semua logika ada di paket ``synthid_removal``; file ini hanya menjaga agar
perintah lama (``python main.py``) tetap berjalan.
"""

from __future__ import annotations

from synthid_removal.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
