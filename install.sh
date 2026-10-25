#!/usr/bin/env bash
# Pemasang SynthID Cleaner.
# Aman dijalankan dari folder mana pun: skrip ini selalu pindah ke folder repo.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

info() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[!]\033[0m %s\n' "$*"; }
error() { printf '\033[31m[x]\033[0m %s\n' "$*" >&2; }

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    PYTHON=python
fi
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    error "Python tidak ditemukan."
    echo "    Termux : pkg install python" >&2
    echo "    Debian : sudo apt install python3 python3-venv" >&2
    exit 1
fi

is_termux() {
    case "${PREFIX:-}" in
        *com.termux*) return 0 ;;
    esac
    [ -n "${TERMUX_VERSION:-}" ]
}

has_pillow() {
    "$1" -c "import PIL" >/dev/null 2>&1
}

if is_termux; then
    info "Termux terdeteksi; memakai Python sistem."
    if ! has_pillow "$PYTHON"; then
        info "Memasang Pillow dari repo Termux..."
        pkg install -y python-pillow || warn "pkg install python-pillow gagal."
    fi
    if ! has_pillow "$PYTHON"; then
        info "Mencoba memasang Pillow lewat pip..."
        "$PYTHON" -m pip install --quiet --disable-pip-version-check -r requirements.txt \
            || warn "pip gagal; coba: pkg install libjpeg-turbo libpng lalu ulangi."
    fi
    RUNNER="$PYTHON"
    JALAN="$PYTHON main.py"
else
    VENV="$SCRIPT_DIR/.venv"
    if [ ! -x "$VENV/bin/python" ]; then
        info "Membuat virtualenv di .venv ..."
        "$PYTHON" -m venv "$VENV" || {
            error "Gagal membuat virtualenv."
            echo "    Debian/Ubuntu : sudo apt install python3-venv" >&2
            exit 1
        }
    fi
    RUNNER="$VENV/bin/python"
    info "Memasang dependensi dari requirements.txt ..."
    "$RUNNER" -m pip install --quiet --disable-pip-version-check -r requirements.txt
    if "$RUNNER" -m pip install --quiet --disable-pip-version-check --no-deps -e . 2>/dev/null; then
        JALAN="$SCRIPT_DIR/.venv/bin/synthid-clean"
    else
        JALAN="$RUNNER main.py"
    fi
fi

if ! has_pillow "$RUNNER"; then
    error "Pillow belum bisa diimpor oleh $RUNNER."
    echo "    Coba jalankan: $RUNNER -m pip install -r requirements.txt" >&2
    exit 1
fi

info "Pillow $("$RUNNER" -c 'import PIL; print(PIL.__version__)') siap."

cat <<EOF

Instalasi selesai.

Folder proyek : $SCRIPT_DIR
Cara menjalankan:

  cd "$SCRIPT_DIR"
  $JALAN

Atau mode interaktif (drag & drop file ke terminal):

  cd "$SCRIPT_DIR"
  $JALAN --help

Penting: perintah di atas harus dijalankan SETELAH 'cd' ke folder proyek.
Kalau muncul "can't open file .../main.py", berarti Anda masih di folder lain.
EOF

if is_termux; then
    cat <<EOF

Di Termux, agar folder Download bisa dibaca:

  termux-setup-storage
  $JALAN ~/storage/downloads -o ~/storage/downloads/bersih
EOF
fi
