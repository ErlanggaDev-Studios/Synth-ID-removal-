# SynthID Cleaner

CLI untuk membersihkan **metadata** dan **watermark tak terlihat** dari gambar
hasil generator AI (PNG, JPEG, WebP, BMP, TIFF). Dulu skripnya cuma satu file
dengan path hardcode ke `/sdcard/Download`; sekarang jadi alat terminal yang
bisa menerima file, folder, glob, drag & drop, sampai pipe dari `find`.

> Gunakan hanya pada gambar milik Anda sendiri atau yang Anda punya izin
> mengolahnya. Menghapus tanda provenance bisa melanggar ketentuan layanan
> platform dan aturan pengungkapan konten AI di beberapa negara.

---

## Fitur

- **Masukan fleksibel** - banyak file, folder (opsional rekursif), pola glob,
  path hasil drag & drop (dengan kutip atau `\ ` escape), `~`, variabel
  lingkungan, atau daftar path dari stdin.
- **Metadata dibuang total** - EXIF, XMP, PNG `tEXt`/`iTXt` (prompt & parameter
  generator), profil ICC, komentar, dan blok JFIF.
- **Pipeline piksel** - mikro-resize 1 piksel (bilinear -> bicubic) lalu geser
  kontras 1% untuk merusak susunan matriks watermark.
- **Aman untuk alpha** - transparansi tidak ikut diubah; kalau keluarannya JPEG,
  alpha diratakan ke latar putih dan diberi peringatan.
- **Tulis atomik** - hasil ditulis ke file sementara lalu diganti nama, jadi
  file lama tidak rusak kalau proses gagal di tengah jalan.
- **Batch yang tidak berhenti di file rusak** - satu file gagal, sisanya tetap
  diproses; ringkasan dan exit code melaporkan kegagalan.
- **Mode interaktif** - jalankan tanpa argumen, lalu tarik file ke terminal.
- **Output rapi** - progres berwarna, ringkasan ukuran sebelum/sesudah, dan
  mode `--json` untuk skrip/otomasi.

---

## Tampilan

Saat dijalankan di terminal, muncul banner dan panel seperti ini:

```text
  ███████╗██╗   ██╗███╗   ██╗████████╗██╗  ██╗    ██╗██████╗
  ██╔════╝╚██╗ ██╔╝████╗  ██║╚══██╔══╝██║  ██║   ██║██╔══██╗
  ███████╗ ╚████╔╝ ██╔██╗ ██║   ██║   ███████║   ██║██║  ██║
  ╚════██║  ╚██╔╝  ██║╚██╗██║   ██║   ██╔══██║   ██║██║  ██║
  ███████║   ██║   ██║ ╚████║   ██║   ██║  ██║██╗██║██████╔╝
  ╚══════╝   ╚═╝   ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝╚═════╝

  ╭─ SYNTH-ID REMOVAL ──────────────────────────────────────────────╮
  │ v1.1.0  AI watermark & metadata cleaner                         │
  │                                                                 │
  │ ▸  EXIF · XMP · ICC dibuang total                               │
  │ ▸  mikro-resize 1px + geser kontras 0.99                        │
  │ ▸  alpha aman · tulis atomik · batch tahan error                │
  │                                                                 │
  │ tarik file ke terminal, atau tempel path-nya                    │
  ╰─────────────────────────────────────────────────────────────────╯
  cwd /data/data/com.termux/files/home/Synth-ID-removal-
```

- Terminal sempit (< 66 kolom, umum di Termux portrait) otomatis memakai
  versi ringkas: logo blok diganti wordmark di panel.
- `--no-banner` menyembunyikan banner. `--quiet`, `--json`, atau output yang
  di-pipe juga tidak menampilkan banner.
- Progress batch tampil sebagai bar `████░░░░ 3/7 nama.png` di terminal.

---

## Persyaratan

- Python **3.9+**
- Pillow (terpasang otomatis lewat `requirements.txt`)

## Instalasi

### Cara tercepat

```bash
# Termux: pastikan Python & git ada dulu
pkg update && pkg install python git

git clone https://github.com/ErlanggaDev-Studios/Synth-ID-removal-.git
cd Synth-ID-removal-
bash install.sh
```

`install.sh` selalu pindah ke folder proyek sendiri, membuat `.venv` (di
Linux/macOS), memasang Pillow, dan mendaftarkan perintah `synthid-clean`.

> Langkah `cd Synth-ID-removal-` **wajib**. Kalau setelah `git clone` Anda
> langsung menjalankan `python main.py`, Python akan mencari
> `~/main.py` dan muncul error `can't open file .../main.py`.

### Termux (Android)

```bash
pkg update && pkg install python git
pkg install python-pillow        # biasanya lebih cepat & andal daripada pip

git clone https://github.com/ErlanggaDev-Studios/Synth-ID-removal-.git
cd Synth-ID-removal-

termux-setup-storage   # sekali saja, agar folder Download bisa dibaca
python main.py          # jalan dari dalam folder proyek
```

Kalau `python-pillow` tidak tersedia di repo Termux, gunakan
`pip install -r requirements.txt` dari dalam folder proyek.

### Linux / macOS

```bash
git clone https://github.com/ErlanggaDev-Studios/Synth-ID-removal-.git
cd Synth-ID-removal-
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
git clone https://github.com/ErlanggaDev-Studios/Synth-ID-removal-.git
cd Synth-ID-removal-
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Perintah `synthid-clean` (opsional)

Kalau ingin memanggil alat ini dari folder mana pun:

```bash
pip install -e .
synthid-clean --version
```

Tanpa instalasi pun tetap bisa: `python main.py ...` atau
`python -m synthid_removal ...`.

---

## Cara pakai

### 1. Interaktif (paling gampang)

```bash
python main.py
```

Banner muncul, lalu tarik file ke terminal (atau tempel path-nya) dan tekan
Enter. Bisa menambah beberapa path sebelum diproses. Enter pada input kosong
mengakhiri sesi.

### 2. Satu file

```bash
python main.py foto_ai.png
# hasil: foto_ai_clean.png di folder yang sama
```

### 3. Nama keluaran sendiri

```bash
python main.py foto_ai.png -o hasil/galaxy.png
```

### 4. Banyak file ke satu folder

```bash
python main.py foto1.png foto2.jpg "foto tiga.webp" -o bersih/
```

### 5. Satu folder penuh (dan subfolder)

```bash
python main.py ~/Download -o ~/Download/bersih
python main.py ~/Pictures/ai -r -o ~/Pictures/ai/bersih
```

### 6. Pola glob

```bash
python main.py "*.png" --suffix _bersih
python main.py "galaxy_*.jpg" -f webp
```

### 7. Hanya buang metadata (piksel tidak disentuh)

```bash
python main.py foto.png --metadata-only
```

### 8. Cek dulu tanpa menulis apa pun

```bash
python main.py ~/Download -r --dry-run
```

### 9. Pipe dari perintah lain

```bash
find ~/Download -name "*.png" | python main.py -o bersih/
```

Setiap baris dibaca sebagai satu path, jadi nama file berspasi tetap aman.

### 10. Untuk skrip

```bash
python main.py foto.png --json
```

---

## Opsi

| Opsi | Arti |
| --- | --- |
| `GAMBAR ...` | File, folder, atau pola glob. Bisa lebih dari satu. |
| `-o, --output PATH` | File keluaran tunggal, atau folder. Path tanpa ekstensi gambar (`hasil`, `bersih/`) dianggap folder. |
| `-f, --format {keep,png,jpeg,webp,bmp,tiff,gif,ppm}` | Format keluaran; default `keep` (ikut aslinya). |
| `-q, --quality 1-100` | Kualitas JPEG/WebP; default `92`. |
| `-s, --suffix TEKS` | Akhiran nama keluaran; default `_clean`. |
| `-r, --recursive` | Telusuri subfolder. |
| `--force` | Timpa keluaran yang sudah ada. |
| `--skip-existing` | Lewati file yang keluarannya sudah ada. |
| `--unique` | Kalau sudah ada, pakai nama baru `nama (1).png`. |
| `--resize-delta N` | Piksel yang dipotong saat mikro-resize; `0` = nonaktif. |
| `--contrast FAKTOR` | Faktor kontras; `1.0` = nonaktif. |
| `--metadata-only` | Setara `--resize-delta 0 --contrast 1.0`. |
| `--dry-run` | Tampilkan rencana, tidak menulis file. |
| `--json` | Hasil dalam JSON. |
| `--quiet` | Hanya ringkasan akhir. |
| `--no-banner` | Jangan tampilkan banner pembuka. |
| `--no-color` | Matikan warna ANSI. |
| `-V, --version` | Versi alat. |

### Exit code

| Kode | Arti |
| --- | --- |
| `0` | Semua berhasil (termasuk file yang sengaja dilewati). |
| `1` | Ada file yang gagal diproses. |
| `2` | Argumen salah / tidak ada masukan. |
| `130` | Dibatalkan dengan Ctrl+C. |

---

## Cara kerjanya

1. **Mode kerja** - gambar dikonversi ke RGB/RGBA/L; transparansi dipertahankan,
   CMYK dan 16-bit diturunkan dengan peringatan.
2. **Mikro-resize** - gambar diperkecil 1 piksel (bilinear) lalu dikembalikan ke
   ukuran asli (bicubic). Ini menggeser koordinat matriks watermark.
3. **Geser kontras** - kontras RGB diubah 1% (alpha tidak ikut) sehingga nilai
   biner watermark tidak lagi cocok.
4. **Simpan bersih** - metadata dikosongkan, chunk teks PNG/EXIF tidak ditulis,
   lalu file ditulis atomik (temp -> `os.replace`).

Setelah menulis, alat ini **membaca ulang** hasilnya dan memastikan tidak ada
EXIF maupun metadata provenance yang tersisa; kalau masih ada, peringatan
ditampilkan.

### Batasan yang perlu diketahui

- Ini bukan jaminan watermark SynthID hilang 100%. Watermark yang tahan
  crop/rotasi/kompresi bisa bertahan pada perubahan halus.
- Konversi CMYK ke RGB dan pembuangan profil ICC bisa sedikit mengubah warna.
- GIF memakai palet maksimal 256 warna; gambar animasi hanya frame pertamanya
  yang diproses.
- Format 16-bit diturunkan ke 8-bit.

---

## Format yang didukung

Masukan: `.png`, `.jpg`, `.jpeg`, `.jpe`, `.jfif`, `.webp`, `.bmp`, `.dib`,
`.tif`, `.tiff`, `.gif`, `.ppm`, `.pgm`, `.pnm`.

Keluaran: PNG, JPEG, WebP, BMP, TIFF, GIF, PPM.

---

## Pakai sebagai library

```python
from synthid_removal import SanitizeOptions, sanitize_image

hasil = sanitize_image(
    "masuk.png",
    "keluar.png",
    SanitizeOptions(resize_delta=1, contrast=0.99),
)

print(hasil.output)           # Path keluar
print(hasil.bytes_saved)      # selisih ukuran
print(hasil.warnings)         # peringatan konversi
```

Fungsi lain yang tersedia: `sanitize_many()`, `expand_inputs()`,
`output_path_for()`, `resolve_save_format()`.

---

## Struktur proyek

```
install.sh                  # pemasang otomatis (aman dari folder mana pun)
main.py                     # entry point: python main.py
synthid_removal/
  __init__.py               # API publik + versi
  __main__.py               # python -m synthid_removal
  cli.py                    # argparse, mode interaktif, tampilan
  files.py                  # ekspansi path, penentuan nama keluaran
  sanitizer.py              # pipeline gambar
  ui.py                     # banner, panel, progress bar, warna
tests/
  conftest.py               # fixture pembuat gambar uji
  test_sanitizer.py         # uji inti pipeline
  test_files.py             # uji path/glob/folder
  test_cli.py               # uji CLI end-to-end
  test_ui.py                # uji banner/panel/progress
requirements.txt
requirements-dev.txt
pyproject.toml
```

## Pengembangan & pengujian

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

---

## Troubleshooting

**`can't open file '.../main.py': [Errno 2] No such file or directory`**
Terminal masih di folder lain (biasanya `home`). Masuk dulu ke folder proyek:

```bash
cd ~/Synth-ID-removal-
python main.py
```

**`No such file or directory: 'requirements.txt'`**
Sama penyebabnya: jalankan dari dalam folder proyek, atau pakai
`bash install.sh` yang otomatis pindah folder.

**`ModuleNotFoundError: No module named 'PIL'`**
Jalankan `pip install -r requirements.txt` (atau aktifkan venv dulu).

**`error: externally-managed-environment` (Debian/Ubuntu/Arch)**
Pakai virtualenv seperti pada bagian instalasi, atau
`pip install --user -r requirements.txt`.

**Termux tidak bisa membaca `/sdcard/Download`**
Jalankan `termux-setup-storage`, lalu izinkan akses penyimpanan. Bisa juga
memakai path `~/storage/downloads`.

**Termux gagal saat memasang Pillow lewat pip**
Pakai paket bawaan Termux: `pkg install python-pillow`. Kalau masih gagal:
`pkg install libjpeg-turbo libpng` lalu ulangi `pip install -r requirements.txt`.

**Nama file ada spasinya**
Bungkus dengan kutip (`"foto ai.png"`) atau drag & drop langsung; keduanya
didukung.

**Hasil tidak mau menimpa file lama**
Itu disengaja. Pakai `--force` (timpa), `--skip-existing` (lewati), atau
`--unique` (nama baru).

---

## Lisensi

MIT - lihat [LICENSE](LICENSE).
