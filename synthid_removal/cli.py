"""Antarmuka terminal untuk pembersihan gambar."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import __version__
from .files import clean_token, expand_inputs, output_path_for, same_file
from .sanitizer import (
    EXTENSION_FORMATS,
    OUTPUT_FORMATS,
    SanitizeError,
    SanitizeOptions,
    SanitizeResult,
    resolve_save_format,
    sanitize_image,
)

# --------------------------------------------------------------------------- #
# Tampilan terminal
# --------------------------------------------------------------------------- #


class Style:
    """Pewarnaan ANSI sederhana tanpa dependensi tambahan."""

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


def _stream_supports_color(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _symbol(nice: str, fallback: str) -> str:
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        nice.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return fallback
    return nice


def human_size(size: int) -> str:
    """Format ukuran byte menjadi string pendek."""

    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"  # pragma: no cover


def _label(path: Path, base: Optional[Path] = None) -> str:
    if base is not None:
        try:
            return str(path.relative_to(base))
        except ValueError:
            pass
    return path.name


# --------------------------------------------------------------------------- #
# Argumen
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="synthid-clean",
        description=(
            "Bersihkan metadata dan watermark tak terlihat dari gambar "
            "hasil generator AI (PNG, JPEG, WebP, BMP, TIFF)."
        ),
        epilog=(
            "Contoh:\n"
            "  synthid-clean foto.png\n"
            "  synthid-clean 'foto hasil ai.png' -o bersih/\n"
            "  synthid-clean ~/Download -r -f webp -s _clean\n"
            "  synthid-clean *.png --metadata-only --dry-run\n"
            "Tanpa argumen, alat ini masuk mode interaktif (drag & drop)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        metavar="GAMBAR",
        help="File, folder, atau pola glob. Bisa lebih dari satu.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="File keluaran tunggal, atau folder untuk banyak masukan.",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="keep",
        choices=("keep",) + OUTPUT_FORMATS,
        help="Format keluaran (default: ikut format asli).",
    )
    parser.add_argument(
        "-q",
        "--quality",
        type=int,
        default=92,
        metavar="1-100",
        help="Kualitas JPEG/WebP (default: 92).",
    )
    parser.add_argument(
        "-s",
        "--suffix",
        default="_clean",
        help="Akhiran nama file keluaran (default: _clean).",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Telusuri folder masukan sampai ke subfolder.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Timpa file keluaran yang sudah ada (hati-hati).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Lewati file yang keluarannya sudah ada, tanpa menggagalkan proses.",
    )
    parser.add_argument(
        "--unique",
        action="store_true",
        help="Kalau keluaran sudah ada, buat nama baru (nama (1).png).",
    )
    parser.add_argument(
        "--resize-delta",
        type=int,
        default=1,
        metavar="N",
        help="Piksel yang dipotong saat mikro-resize, 0 = nonaktif (default: 1).",
    )
    parser.add_argument(
        "--contrast",
        type=float,
        default=0.99,
        metavar="FAKTOR",
        help="Faktor kontras, 1.0 = nonaktif (default: 0.99).",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Hanya buang metadata, piksel tidak diubah.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tampilkan rencana proses tanpa menulis file.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Cetak hasil dalam format JSON (untuk skrip).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Hanya tampilkan ringkasan akhir.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Matikan warna ANSI.",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


# --------------------------------------------------------------------------- #
# Mode interaktif
# --------------------------------------------------------------------------- #


def _print_banner(style: Style) -> None:
    print()
    judul = style.bold(style.magenta("  SynthID Cleaner "))
    print(judul + style.dim(f"v{__version__}"))
    print(style.dim("  Bersihkan metadata + watermark tak terlihat dari gambar AI"))
    print(style.dim("  " + "-" * 58))
    print(style.dim("  Tarik file ke terminal, atau tempel path-nya."))
    print(style.dim("  Boleh banyak file/folder sekaligus, dipisah spasi."))
    print(style.dim("  Tekan Enter tanpa isi untuk keluar."))
    print()


def prompt_for_inputs(style: Style) -> List[str]:
    """Baca path dari pengguna secara interaktif."""

    _print_banner(style)
    collected: List[str] = []
    while True:
        label = "Path gambar" if not collected else "Tambah path lain"
        hint = "Enter untuk mulai" if collected else "Enter untuk keluar"
        try:
            line = input(f"{style.cyan('>')} {label} ({style.dim(hint)}): ")
        except (EOFError, KeyboardInterrupt):
            print()
            return collected
        line = line.strip()
        if not line:
            return collected
        collected.extend(_split_line(line))


def _split_line(line: str) -> List[str]:
    """Pisahkan satu baris input menjadi path, tahan terhadap spasi.

    Jika ``shlex`` memecah sebuah path berspasi menjadi beberapa bagian yang
    tidak ada, dan seluruh baris ternyata path yang valid, baris itu dipakai
    utuh.
    """

    try:
        tokens = shlex.split(line, posix=os.name != "nt")
    except ValueError:
        tokens = line.split()
    if (
        len(tokens) > 1
        and not any(Path(clean_token(token)).exists() for token in tokens)
        and Path(clean_token(line)).exists()
    ):
        return [line]
    return [token for token in tokens if token.strip()]


def _read_piped_inputs() -> List[str]:
    """Baca daftar path dari stdin (mis. hasil pipe ``find``)."""

    tokens: List[str] = []
    try:
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            if Path(clean_token(line)).exists():
                tokens.append(line)
            else:
                tokens.extend(_split_line(line))
    except (OSError, KeyboardInterrupt):
        return tokens
    return tokens


# --------------------------------------------------------------------------- #
# Perencanaan pekerjaan
# --------------------------------------------------------------------------- #


class Job:
    __slots__ = ("destination", "source")

    def __init__(self, source: Path, destination: Path) -> None:
        self.source = source
        self.destination = destination


def _free_name(path: Path, planned: set) -> Path:
    """Nama yang belum dipakai, baik di disk maupun di rencana batch."""

    candidate = path
    index = 1
    while candidate in planned or candidate.exists():
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        index += 1
    return candidate


def build_jobs(
    sources: Sequence[Path],
    output: Optional[Path],
    suffix: str,
    requested_format: Optional[str],
    force: bool,
    skip_existing: bool,
    make_unique: bool,
) -> Tuple[List[Job], List[Tuple[Path, str]], List[Tuple[Path, str]]]:
    """Susun daftar pekerjaan beserta daftar gagal dan daftar dilewati."""

    jobs: List[Job] = []
    failures: List[Tuple[Path, str]] = []
    skipped: List[Tuple[Path, str]] = []
    planned: set = set()

    batch = len(sources) > 1
    if output is not None and batch:
        if output.exists() and output.is_file():
            raise SanitizeError(
                "Beberapa file masukan membutuhkan folder keluaran, bukan satu file."
            )
        if not output.exists() and output.suffix.lower() in EXTENSION_FORMATS:
            raise SanitizeError(
                f"'{output}' terlihat seperti nama file, padahal ada {len(sources)} "
                "file masukan; pakai nama folder tanpa ekstensi."
            )

    for source in sources:
        try:
            destination = output_path_for(
                source,
                output,
                suffix,
                requested_format,
                force_directory=batch,
            )
        except SanitizeError as exc:
            failures.append((source, str(exc)))
            continue

        if same_file(source, destination):
            if not force:
                failures.append(
                    (
                        source,
                        (
                            "Path keluaran sama dengan file sumber; pakai "
                            "--force atau ubah --suffix."
                        ),
                    )
                )
                continue
            if skip_existing:
                skipped.append((source, "keluaran sama dengan sumber"))
                continue
            target_format = resolve_save_format(destination, requested_format)
            extension_format = EXTENSION_FORMATS.get(source.suffix.lower())
            if extension_format and extension_format != target_format:
                failures.append(
                    (
                        source,
                        (
                            f"format {target_format} tidak cocok dengan ekstensi "
                            f"{source.suffix}; ganti nama keluaran."
                        ),
                    )
                )
                continue

        if destination in planned:
            if make_unique:
                destination = _free_name(destination, planned)
            else:
                failures.append(
                    (
                        source,
                        (
                            f"nama keluaran bentrok: {destination}; pakai "
                            "--unique atau folder keluaran lain."
                        ),
                    )
                )
                continue
        elif destination.exists() and not force:
            if skip_existing:
                skipped.append((source, f"sudah ada: {destination}"))
                continue
            if make_unique:
                destination = _free_name(destination, planned)
            else:
                failures.append(
                    (
                        source,
                        (
                            f"keluaran sudah ada: {destination}; pakai --force, "
                            "--skip-existing, atau --unique."
                        ),
                    )
                )
                continue

        planned.add(destination)
        jobs.append(Job(source, destination))

    return jobs, failures, skipped


# --------------------------------------------------------------------------- #
# Eksekusi
# --------------------------------------------------------------------------- #


def _print_result(
    style: Style,
    index: int,
    total: int,
    result: SanitizeResult,
    symbols: Dict[str, str],
    verbose: bool,
) -> None:
    width, height = result.size
    detail = (
        f"{result.output_format} {width}x{height} "
        f"{human_size(result.bytes_before)} -> {human_size(result.bytes_after)}"
    )
    arrow = symbols["arrow"]
    line = (
        f"[{index}/{total}] {style.green(symbols['ok'])} "
        f"{style.bold(result.source.name)} {arrow} "
        f"{style.cyan(_label(result.output, result.source.parent))} "
        f"{style.dim(detail)}"
    )
    print(line)
    if verbose:
        for warning in result.warnings:
            print(style.dim(f"        {symbols['warn']} {warning}"))


def _result_payload(result: SanitizeResult) -> dict:
    return {
        "status": "ok",
        "source": str(result.source),
        "output": str(result.output),
        "source_format": result.source_format,
        "output_format": result.output_format,
        "size": list(result.size),
        "bytes_before": result.bytes_before,
        "bytes_after": result.bytes_after,
        "warnings": result.warnings,
    }


def _validate_options(args: argparse.Namespace) -> Optional[str]:
    if args.force and args.skip_existing:
        return "--force dan --skip-existing tidak bisa dipakai bersamaan."
    if args.force and args.unique:
        return "--force dan --unique tidak bisa dipakai bersamaan."
    if not 1 <= args.quality <= 100:
        return "--quality harus di antara 1 dan 100."
    if args.resize_delta < 0:
        return "--resize-delta tidak boleh negatif."
    if not 0.0 < args.contrast <= 2.0:
        return "--contrast harus di antara 0 dan 2."
    if args.metadata_only and (args.resize_delta != 1 or args.contrast != 0.99):
        return "--metadata-only tidak bisa digabung dengan --resize-delta/--contrast."
    return None


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    started = time.perf_counter()
    style = Style(
        enabled=not args.no_color
        and not args.json
        and _stream_supports_color(sys.stdout)
    )
    symbols = {
        "ok": _symbol("✓", "OK"),
        "warn": _symbol("!", "!"),
        "error": _symbol("✗", "x"),
        "arrow": _symbol("→", "->"),
        "bullet": _symbol("·", "-"),
    }

    tokens = list(args.inputs)
    if not tokens:
        interactive = sys.stdin is not None and sys.stdin.isatty()
        if interactive and not args.json:
            tokens = prompt_for_inputs(style)
        elif not interactive:
            tokens = _read_piped_inputs()

        if not tokens:
            if args.json:
                print(json.dumps({"status": "error", "message": "Tidak ada masukan."}))
            else:
                print(
                    style.red("Tidak ada file yang dipilih."),
                    file=sys.stderr,
                )
                parser.print_usage(sys.stderr)
            return 2

    try:
        sources, problems = expand_inputs(tokens, recursive=args.recursive)
    except SanitizeError as exc:
        print(style.red(f"Gagal membaca masukan: {exc}"), file=sys.stderr)
        return 1

    for problem in problems:
        if not args.json and not args.quiet:
            print(style.yellow(f"{symbols['warn']} {problem}"), file=sys.stderr)

    if not sources:
        message = "Tidak ada gambar yang bisa diproses."
        if args.json:
            print(json.dumps({"status": "error", "message": message}))
        else:
            print(style.red(message), file=sys.stderr)
        return 1

    requested_format = None if args.format == "keep" else args.format
    try:
        jobs, failures, skipped = build_jobs(
            sources,
            args.output,
            args.suffix,
            requested_format,
            force=args.force,
            skip_existing=args.skip_existing,
            make_unique=args.unique,
        )
    except SanitizeError as exc:
        print(style.red(f"{symbols['error']} {exc}"), file=sys.stderr)
        return 2

    resize_delta = 0 if args.metadata_only else args.resize_delta
    contrast = 1.0 if args.metadata_only else args.contrast
    try:
        options = SanitizeOptions(
            resize_delta=resize_delta,
            contrast=contrast,
            save_format=requested_format,
            quality=args.quality,
            png_compress_level=9,
        )
    except ValueError as exc:
        print(style.red(f"{symbols['error']} {exc}"), file=sys.stderr)
        return 2

    if args.dry_run:
        if args.json:
            print(
                json.dumps(
                    {
                        "status": "dry-run",
                        "planned": [
                            {
                                "source": str(job.source),
                                "output": str(job.destination),
                            }
                            for job in jobs
                        ],
                        "skipped": [
                            {"source": str(src), "message": reason}
                            for src, reason in skipped
                        ],
                        "failed": [
                            {"source": str(src), "message": reason}
                            for src, reason in failures
                        ],
                        "problems": problems,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(style.bold(f"Rencana proses ({len(jobs)} file)"))
            for index, job in enumerate(jobs, start=1):
                print(
                    f"  {index}. {job.source} {symbols['arrow']} {job.destination}"
                )
            for source, reason in failures + skipped:
                print(style.yellow(f"  {symbols['warn']} {source.name}: {reason}"))
            print(style.dim("Tidak ada file yang ditulis (--dry-run)."))
        return 0 if not failures else 1

    if failures and not args.json:
        for source, reason in failures:
            print(
                style.red(f"{symbols['error']} {source}: {reason}"),
                file=sys.stderr,
            )

    results: List[SanitizeResult] = []
    payloads: List[dict] = []
    failures_payload: List[dict] = []
    skipped_payload: List[dict] = []

    total = len(jobs)
    show_progress = not args.quiet and not args.json and sys.stdout.isatty()
    for index, job in enumerate(jobs, start=1):
        if show_progress:
            print(
                style.dim(f"[{index}/{total}] memproses {job.source.name}..."),
                end="\r",
                flush=True,
            )
        try:
            result = sanitize_image(job.source, job.destination, options)
        except SanitizeError as exc:
            failures.append((job.source, str(exc)))
            if not args.json:
                if show_progress:
                    print(" " * 70, end="\r")
                print(
                    style.red(
                        f"[{index}/{total}] {symbols['error']} "
                        f"{job.source.name}: {exc}"
                    ),
                    file=sys.stderr,
                )
            continue
        results.append(result)
        if args.json:
            payloads.append(_result_payload(result))
        elif not args.quiet:
            if show_progress:
                print(" " * 70, end="\r")
            _print_result(style, index, total, result, symbols, verbose=True)

    for source, reason in failures:
        failures_payload.append(
            {"status": "error", "source": str(source), "message": reason}
        )
    for source, reason in skipped:
        skipped_payload.append(
            {"status": "skipped", "source": str(source), "message": reason}
        )
        if not args.json and not args.quiet:
            print(style.yellow(f"{symbols['bullet']} dilewati {source.name}: {reason}"))

    elapsed = time.perf_counter() - started

    if args.json:
        print(
            json.dumps(
                {
                    "status": "ok" if not failures else "partial",
                    "elapsed_seconds": round(elapsed, 3),
                    "processed": payloads,
                    "skipped": skipped_payload,
                    "failed": failures_payload,
                    "problems": problems,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not failures else 1

    total_before = sum(item.bytes_before for item in results)
    total_after = sum(item.bytes_after for item in results)
    summary = (
        f"{len(results)} berhasil {symbols['bullet']} "
        f"{len(skipped)} dilewati {symbols['bullet']} "
        f"{len(failures)} gagal {symbols['bullet']} "
        f"{human_size(total_before)} -> {human_size(total_after)} "
        f"{symbols['bullet']} {elapsed:.2f}s"
    )
    print()
    if failures:
        judul = style.red(style.bold("Selesai dengan kegagalan"))
        print(judul + " " + style.dim(summary))
        return 1
    print(style.green(style.bold("Selesai")) + " " + style.dim(summary))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    problem = _validate_options(args)
    if problem:
        parser.error(problem)

    try:
        return run(args, parser)
    except KeyboardInterrupt:
        print("\nDibatalkan.", file=sys.stderr)
        return 130
    except SanitizeError as exc:
        print(f"Kesalahan: {exc}", file=sys.stderr)
        return 1


def run_cli() -> None:
    """Entry point untuk ``python -m`` dan skrip terpasang."""

    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    run_cli()
