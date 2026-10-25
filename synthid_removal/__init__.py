"""SynthID Cleaner - pembersih metadata & watermark gambar hasil AI.

Pemakaian dari kode lain::

    from synthid_removal import SanitizeOptions, sanitize_image

    hasil = sanitize_image("asli.png", "bersih.png", SanitizeOptions())
    print(hasil.output, hasil.bytes_saved)
"""

from __future__ import annotations

from .files import (
    clean_token,
    expand_inputs,
    is_directory_target,
    is_supported_image,
    output_path_for,
    same_file,
    scan_directory,
)
from .sanitizer import (
    EXTENSION_FORMATS,
    FORMAT_ALIASES,
    FORMAT_EXTENSIONS,
    IMAGE_SUFFIXES,
    OUTPUT_FORMATS,
    SanitizeError,
    SanitizeOptions,
    SanitizeResult,
    output_suffix_for,
    resolve_save_format,
    sanitize_image,
    sanitize_many,
)

__version__ = "1.0.0"

__all__ = [
    "EXTENSION_FORMATS",
    "FORMAT_ALIASES",
    "FORMAT_EXTENSIONS",
    "IMAGE_SUFFIXES",
    "OUTPUT_FORMATS",
    "SanitizeError",
    "SanitizeOptions",
    "SanitizeResult",
    "__version__",
    "clean_token",
    "expand_inputs",
    "is_directory_target",
    "is_supported_image",
    "output_path_for",
    "output_suffix_for",
    "resolve_save_format",
    "same_file",
    "sanitize_image",
    "sanitize_many",
    "scan_directory",
]
