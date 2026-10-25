"""Inti pipeline pembersihan sinyal provenance (metadata + watermark) gambar.

Modul ini tidak bergantung pada CLI sehingga bisa dipakai ulang dari kode lain::

    from synthid_removal import SanitizeOptions, sanitize_image
    sanitize_image("masuk.png", "keluar.png", SanitizeOptions(contrast=0.99))
"""

from __future__ import annotations

import contextlib
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageEnhance, PngImagePlugin

# Pillow >= 9.1 memakai enum Image.Resampling; versi lama memakai konstanta modul.
try:  # pragma: no cover - bergantung versi Pillow
    _BILINEAR = Image.Resampling.BILINEAR
    _BICUBIC = Image.Resampling.BICUBIC
except AttributeError:  # pragma: no cover
    _BILINEAR = Image.BILINEAR
    _BICUBIC = Image.BICUBIC


#: Ekstensi yang dikenali sebagai gambar masukan.
IMAGE_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".jpe",
        ".jfif",
        ".webp",
        ".bmp",
        ".dib",
        ".tif",
        ".tiff",
        ".gif",
        ".ppm",
        ".pgm",
        ".pnm",
    }
)

#: Ekstensi -> nama format Pillow (dipakai saat menebak format keluaran).
EXTENSION_FORMATS = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".jpe": "JPEG",
    ".jfif": "JPEG",
    ".webp": "WEBP",
    ".bmp": "BMP",
    ".dib": "BMP",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".gif": "GIF",
    ".ppm": "PPM",
    ".pgm": "PPM",
    ".pnm": "PPM",
}

#: Format Pillow -> ekstensi kanonik.
FORMAT_EXTENSIONS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "TIFF": ".tiff",
    "GIF": ".gif",
    "PPM": ".ppm",
}

#: Format yang boleh dipilih lewat opsi ``--format`` di CLI.
OUTPUT_FORMATS = ("png", "jpeg", "webp", "bmp", "tiff", "gif", "ppm")

#: Alias CLI -> nama format Pillow.
FORMAT_ALIASES = {
    "png": "PNG",
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "webp": "WEBP",
    "bmp": "BMP",
    "tif": "TIFF",
    "tiff": "TIFF",
    "gif": "GIF",
    "ppm": "PPM",
}

#: Kunci ``Image.info`` yang bukan metadata provenance (sisa teknis Pillow).
_IGNORED_INFO_KEYS = frozenset(
    {
        "jpeg",
        "jfif",
        "jfif_version",
        "jfif_unit",
        "jfif_density",
        "adobe",
        "progressive",
        "progression",
        "dpi",
        "gamma",
        "transparency",
        "background",
        "loop",
        "duration",
        "comment",
        "version",
        "extension",
        "compression",
        "resolution",
        "timestamp",
    }
)

#: Tag TIFF yang dianggap metadata pengguna/provenance (bukan tag struktural).
_SENSITIVE_TIFF_TAGS = {
    0x010E: "ImageDescription",
    0x010F: "Make",
    0x0110: "Model",
    0x0131: "Software",
    0x0132: "DateTime",
    0x013B: "Artist",
    0x02BC: "XMP",
    0x8298: "Copyright",
    0x8769: "ExifIFD",
    0x9C9B: "XPTitle",
    0x9C9C: "XPComment",
    0x9C9D: "XPAuthor",
    0x9C9E: "XPKeywords",
    0x9C9F: "XPSubject",
}


class SanitizeError(RuntimeError):
    """Kegagalan yang bisa dilaporkan ke pengguna tanpa traceback."""


@dataclass(frozen=True)
class SanitizeOptions:
    """Pengaturan satu kali proses.

    Attributes:
        resize_delta: Piksel yang dipotong saat mikro-resize (0 = lewati).
        contrast: Faktor kontras; 1.0 = tanpa perubahan.
        save_format: Nama format Pillow atau ``"keep"``/``None`` (ikut ekstensi).
        quality: Kualitas JPEG/WebP (1-100).
        png_compress_level: Level kompresi zlib PNG (0-9).
    """

    resize_delta: int = 1
    contrast: float = 0.99
    save_format: Optional[str] = None
    quality: int = 92
    png_compress_level: int = 9

    def __post_init__(self) -> None:
        if self.resize_delta < 0:
            raise ValueError("resize_delta tidak boleh negatif")
        if not 0.0 < self.contrast <= 2.0:
            raise ValueError("contrast harus di antara 0 dan 2")
        if not 1 <= self.quality <= 100:
            raise ValueError("quality harus di antara 1 dan 100")
        if not 0 <= self.png_compress_level <= 9:
            raise ValueError("png_compress_level harus di antara 0 dan 9")


@dataclass
class SanitizeResult:
    """Ringkasan satu file yang sudah diproses."""

    source: Path
    output: Path
    source_format: str
    output_format: str
    source_mode: str
    size: Tuple[int, int]
    bytes_before: int
    bytes_after: int
    warnings: List[str] = field(default_factory=list)

    @property
    def bytes_saved(self) -> int:
        return self.bytes_before - self.bytes_after


def resolve_save_format(
    destination: Path,
    requested: Optional[str],
    source_format: str = "",
) -> str:
    """Tentukan format Pillow untuk file keluaran.

    Urutan prioritas: opsi eksplisit -> ekstensi tujuan -> format sumber -> PNG.
    """

    if requested:
        key = requested.strip().lower()
        if key in ("", "keep", "same", "asli"):
            pass
        elif key in FORMAT_ALIASES:
            return FORMAT_ALIASES[key]
        else:
            raise SanitizeError(f"Format keluaran tidak didukung: {requested}")

    suffix = destination.suffix.lower()
    if suffix in EXTENSION_FORMATS:
        return EXTENSION_FORMATS[suffix]
    if source_format:
        fmt = source_format.upper()
        if fmt in FORMAT_EXTENSIONS:
            return fmt
    return "PNG"


def output_suffix_for(source: Path, requested: Optional[str]) -> str:
    """Ekstensi yang dipakai saat nama keluaran dibentuk otomatis."""

    if requested and requested.strip().lower() not in ("", "keep", "same", "asli"):
        key = requested.strip().lower()
        if key not in FORMAT_ALIASES:
            raise SanitizeError(f"Format keluaran tidak didukung: {requested}")
        return FORMAT_EXTENSIONS[FORMAT_ALIASES[key]]
    suffix = source.suffix.lower()
    if suffix in EXTENSION_FORMATS:
        return suffix
    return ".png"


def _to_work_mode(image: Image.Image, warnings: List[str]) -> Image.Image:
    """Ubah gambar ke mode kerja (RGB/RGBA/L) tanpa kehilangan transparansi."""

    has_alpha = (
        any(band.upper() == "A" for band in image.getbands())
        or "transparency" in image.info
    )

    if image.mode in ("I", "I;16", "I;16B", "I;16L", "F"):
        warnings.append("Kedalaman 16-bit diturunkan ke 8-bit (PNG abu-abu).")
        return image.convert("L")

    if image.mode == "L":
        return image.copy()

    if has_alpha:
        return image.convert("RGBA")

    if image.mode not in ("RGB", "L"):
        warnings.append(f"Mode {image.mode} dikonversi ke RGB.")

    return image.convert("RGB")


def _micro_resize(image: Image.Image, delta: int) -> Image.Image:
    """Perkecil 1..n piksel lalu kembalikan ke ukuran awal (bilinear -> bicubic)."""

    width, height = image.size
    largest = min(width, height) - 1
    step = max(0, min(delta, largest))
    if step == 0:
        return image

    shrunk = image.resize((width - step, height - step), _BILINEAR)
    return shrunk.resize((width, height), _BICUBIC)


def _apply_contrast(image: Image.Image, factor: float) -> Image.Image:
    """Geser kontras halus; kanal alpha tidak boleh ikut diubah."""

    if factor == 1.0:
        return image

    if image.mode == "RGBA":
        red, green, blue, alpha = image.split()
        rgb = Image.merge("RGB", (red, green, blue))
        rgb = ImageEnhance.Contrast(rgb).enhance(factor)
        red, green, blue = rgb.split()
        return Image.merge("RGBA", (red, green, blue, alpha))

    return ImageEnhance.Contrast(image).enhance(factor)


def _flatten_alpha(image: Image.Image) -> Image.Image:
    """Ratakan transparansi ke latar putih (JPEG tidak punya alpha)."""

    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, (255, 255, 255))
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def _save(
    image: Image.Image,
    destination: Path,
    fmt: str,
    options: SanitizeOptions,
) -> Image.Image:
    """Simpan gambar tanpa metadata apa pun dan kembalikan gambar yang ditulis."""

    kwargs = {}

    if fmt == "JPEG":
        if image.mode not in ("RGB", "L"):
            image = _flatten_alpha(image)
        kwargs.update(
            quality=options.quality,
            optimize=True,
            progressive=True,
            # exif kosong memastikan blok EXIF lama tidak ikut terbawa.
            exif=b"",
        )
    elif fmt == "PNG":
        if image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
            image = image.convert("RGB")
        kwargs.update(
            optimize=True,
            compress_level=options.png_compress_level,
            pnginfo=PngImagePlugin.PngInfo(),
        )
    elif fmt == "WEBP":
        kwargs.update(quality=options.quality, method=6)
    elif fmt == "TIFF":
        if image.mode not in ("RGB", "RGBA", "L", "LA"):
            image = image.convert("RGB")
        kwargs.update(compression="tiff_deflate")
    elif fmt == "BMP":
        if image.mode not in ("RGB", "RGBA", "L"):
            image = image.convert("RGB")
    elif fmt == "GIF":
        if image.mode not in ("L", "P"):
            image = image.convert("RGB").convert(
                "P", palette=Image.Palette.ADAPTIVE, colors=256
            )
    elif fmt == "PPM":
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
    else:  # pragma: no cover - dijaga oleh resolve_save_format
        raise SanitizeError(f"Format keluaran tidak didukung: {fmt}")

    image.save(destination, fmt, **kwargs)
    return image


def _atomic_save(
    image: Image.Image,
    destination: Path,
    fmt: str,
    options: SanitizeOptions,
) -> Image.Image:
    """Tulis ke file sementara lalu ganti nama, agar file lama tidak rusak."""

    temporary = destination.with_name(
        f".{destination.name}.{uuid.uuid4().hex[:8]}.tmp"
    )
    try:
        written = _save(image, temporary, fmt, options)
        os.replace(temporary, destination)
        return written
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise


def _leftover_metadata(destination: Path) -> List[str]:
    """Cek ulang file hasil: metadata apa yang masih tersisa?"""

    with Image.open(destination) as written:
        written.load()
        leftover = sorted(
            key for key in written.info if key not in _IGNORED_INFO_KEYS
        )
        if (written.format or "").upper() == "TIFF":
            # TIFF memakai struktur IFD; hanya tag deskriptif yang dicek.
            tags = getattr(written, "tag_v2", {})
            for tag, label in _SENSITIVE_TIFF_TAGS.items():
                if tag in tags:
                    leftover.append(label)
        else:
            try:
                exif = written.getexif()
            except (OSError, ValueError, SyntaxError):  # pragma: no cover
                exif = None
            if exif:
                leftover.append("exif")
    return leftover


def sanitize_image(
    source: "str | Path",
    destination: "str | Path",
    options: Optional[SanitizeOptions] = None,
) -> SanitizeResult:
    """Proses satu gambar dan tulis hasil bersih ke ``destination``.

    Raises:
        SanitizeError: file tidak ada, bukan gambar, atau gagal ditulis.
    """

    opts = options or SanitizeOptions()
    src = Path(source)
    dst = Path(destination)

    if not src.is_file():
        raise SanitizeError(f"File tidak ditemukan: {src}")

    warnings: List[str] = []
    try:
        bytes_before = src.stat().st_size
    except OSError as exc:
        raise SanitizeError(f"File tidak bisa dibaca: {src} ({exc})") from exc

    try:
        with Image.open(src) as opened:
            opened.load()
            source_format = (opened.format or "").upper()
            source_mode = opened.mode
            size = opened.size
            frames = int(getattr(opened, "n_frames", 1) or 1)
            if frames > 1:
                warnings.append(
                    f"Gambar berisi {frames} frame; hanya frame pertama diproses."
                )
            if opened.info.get("icc_profile"):
                warnings.append("Profil ICC dibuang (warna bisa sedikit bergeser).")
            image = _to_work_mode(opened, warnings)
    except SanitizeError:
        raise
    except (OSError, ValueError) as exc:
        raise SanitizeError(f"Gagal membaca {src.name}: {exc}") from exc

    try:
        image = _micro_resize(image, opts.resize_delta)
        image = _apply_contrast(image, opts.contrast)

        fmt = resolve_save_format(dst, opts.save_format, source_format)
        has_alpha = any(band.upper() == "A" for band in image.getbands())
        if fmt == "JPEG" and has_alpha:
            warnings.append("Transparansi diratakan ke latar putih untuk JPEG.")
        elif fmt in ("BMP", "PPM") and has_alpha:
            warnings.append(
                f"Format {fmt} tidak menyimpan transparansi; alpha dibuang."
            )
        if fmt == "GIF":
            warnings.append("GIF memakai palet maksimal 256 warna (kualitas turun).")

        # resize()/convert() menyalin .info; kosongkan agar tidak ada sisa metadata.
        image.info.clear()

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SanitizeError(
                f"Folder keluaran tidak bisa dibuat: {dst.parent} ({exc})"
            ) from exc
        try:
            image = _atomic_save(image, dst, fmt, opts)
        except (OSError, ValueError) as exc:
            raise SanitizeError(f"Gagal menulis {dst.name}: {exc}") from exc
    finally:
        image.close()

    try:
        leftover = _leftover_metadata(dst)
        bytes_after = dst.stat().st_size
    except (OSError, ValueError) as exc:
        raise SanitizeError(f"Hasil tidak bisa diverifikasi: {exc}") from exc
    if leftover:
        warnings.append("Metadata tersisa: " + ", ".join(leftover))

    return SanitizeResult(
        source=src,
        output=dst,
        source_format=source_format or "UNKNOWN",
        output_format=fmt,
        source_mode=source_mode,
        size=size,
        bytes_before=bytes_before,
        bytes_after=bytes_after,
        warnings=warnings,
    )


def sanitize_many(
    pairs: Sequence[Tuple[Path, Path]],
    options: Optional[SanitizeOptions] = None,
) -> List[SanitizeResult]:
    """Proses beberapa pasangan (sumber, tujuan) secara berurutan."""

    return [sanitize_image(src, dst, options) for src, dst in pairs]


__all__ = [
    "EXTENSION_FORMATS",
    "FORMAT_ALIASES",
    "FORMAT_EXTENSIONS",
    "IMAGE_SUFFIXES",
    "OUTPUT_FORMATS",
    "SanitizeError",
    "SanitizeOptions",
    "SanitizeResult",
    "output_suffix_for",
    "resolve_save_format",
    "sanitize_image",
    "sanitize_many",
]
