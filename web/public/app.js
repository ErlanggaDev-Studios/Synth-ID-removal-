/* Synth-ID Removal — PWA
 * Semua pemrosesan terjadi di browser: decode -> mikro-resize -> kontras ->
 * encode ulang (metadata otomatis hilang) -> unduh / ZIP.
 */
(() => {
  "use strict";

  const MAX_PIXELS = 48_000_000;
  const SETTINGS_KEY = "synthid.settings.v1";
  const FORMATS = ["keep", "image/png", "image/jpeg", "image/webp"];
  const DEFAULTS = {
    format: "keep",
    quality: 92,
    resize: 1,
    contrast: 0.99,
    suffix: "_clean",
    metadataOnly: false,
  };

  const state = {
    items: [],
    settings: { ...DEFAULTS },
    busy: false,
    counter: 0,
  };

  const $ = (id) => document.getElementById(id);
  const dom = {
    hero: $("hero"),
    workspace: $("workspace"),
    dropzone: $("dropzone"),
    dropOverlay: $("dropOverlay"),
    fileInput: $("fileInput"),
    folderInput: $("folderInput"),
    fileList: $("fileList"),
    queueMeta: $("queueMeta"),
    addBtn: $("addBtn"),
    clearBtn: $("clearBtn"),
    pickBtn: $("pickBtn"),
    pickFolderBtn: $("pickFolderBtn"),
    emptyPickBtn: $("emptyPickBtn"),
    formatGroup: $("formatGroup"),
    quality: $("quality"),
    qualityOut: $("qualityOut"),
    resize: $("resize"),
    resizeOut: $("resizeOut"),
    contrast: $("contrast"),
    contrastOut: $("contrastOut"),
    suffix: $("suffix"),
    metadataOnly: $("metadataOnly"),
    resetBtn: $("resetBtn"),
    settingsPanel: $("settingsPanel"),
    processBtn: $("processBtn"),
    zipBtn: $("zipBtn"),
    summary: $("summary"),
    progress: $("progress"),
    progressFill: $("progressFill"),
    progressLabel: $("progressLabel"),
    progressCount: $("progressCount"),
    toastWrap: $("toastWrap"),
    installBtn: $("installBtn"),
    modal: $("compareModal"),
    compareStage: $("compareStage"),
    compareBefore: $("compareBefore"),
    compareAfter: $("compareAfter"),
    compareRange: $("compareRange"),
    compareTitle: $("compareTitle"),
    compareBeforeInfo: $("compareBeforeInfo"),
    compareAfterInfo: $("compareAfterInfo"),
    closeCompare: $("closeCompare"),
  };

  /* ------------------------------------------------------------------ util */

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  function fmtBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes < 0) return "—";
    if (bytes < 1024) return `${bytes} B`;
    const units = ["KB", "MB", "GB"];
    let value = bytes / 1024;
    let index = 0;
    while (value >= 1024 && index < units.length - 1) {
      value /= 1024;
      index += 1;
    }
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`;
  }

  function fmtDims(width, height) {
    return width && height ? `${width}×${height}` : "—";
  }

  function extFor(type) {
    if (type === "image/jpeg") return "jpg";
    if (type === "image/webp") return "webp";
    return "png";
  }

  function stripExtension(name) {
    return name.replace(/\.[^.\\/]+$/, "") || "gambar";
  }

  function outputName(name, suffix, type) {
    const clean = String(suffix || "").replace(/[\\/:*?"<>|]+/g, "").slice(0, 24);
    return `${stripExtension(name)}${clean}.${extFor(type)}`;
  }

  function toast(message, kind = "") {
    if (!dom.toastWrap) return;
    while (dom.toastWrap.children.length >= 3) {
      dom.toastWrap.firstElementChild.remove();
    }
    const node = document.createElement("div");
    node.className = `toast ${kind}`.trim();
    node.textContent = message;
    dom.toastWrap.append(node);
    setTimeout(() => node.remove(), 3400);
  }

  function isImageFile(file) {
    if (file.type && file.type.startsWith("image/")) return true;
    return /\.(png|jpe?g|webp|gif|bmp|avif)$/i.test(file.name || "");
  }

  /* -------------------------------------------------------------- settings */

  function normaliseSettings(raw) {
    const value = { ...DEFAULTS, ...(raw && typeof raw === "object" ? raw : {}) };
    return {
      format: FORMATS.includes(value.format) ? value.format : DEFAULTS.format,
      quality: clamp(Number(value.quality) || DEFAULTS.quality, 40, 100),
      resize: clamp(Number(value.resize), 0, 3),
      contrast: clamp(Number(value.contrast) || DEFAULTS.contrast, 0.98, 1),
      suffix: typeof value.suffix === "string" ? value.suffix.slice(0, 24) : DEFAULTS.suffix,
      metadataOnly: Boolean(value.metadataOnly),
    };
  }

  function loadSettings() {
    try {
      return normaliseSettings(JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}"));
    } catch {
      return { ...DEFAULTS };
    }
  }

  function saveSettings() {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(state.settings));
    } catch {
      /* mode privat: abaikan */
    }
  }

  function renderSettings() {
    const s = state.settings;
    dom.formatGroup.querySelectorAll("[data-format]").forEach((button) => {
      const active = button.dataset.format === s.format;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    dom.quality.value = String(s.quality);
    dom.qualityOut.textContent = `${s.quality}%`;
    dom.resize.value = String(s.resize);
    dom.resizeOut.textContent = `${s.resize} px`;
    dom.contrast.value = String(s.contrast);
    dom.contrastOut.textContent = s.contrast.toFixed(3);
    dom.suffix.value = s.suffix;
    dom.metadataOnly.checked = s.metadataOnly;
    dom.resize.disabled = s.metadataOnly;
    dom.contrast.disabled = s.metadataOnly;
  }

  function updateSettings(patch) {
    state.settings = normaliseSettings({ ...state.settings, ...patch });
    renderSettings();
    saveSettings();
    updateActionBar();
  }

  /* -------------------------------------------------------------- metadata */

  function concatBytes(parts) {
    const total = parts.reduce((sum, part) => sum + part.length, 0);
    const output = new Uint8Array(total);
    let offset = 0;
    for (const part of parts) {
      output.set(part, offset);
      offset += part.length;
    }
    return output;
  }

  function ascii(bytes, start, length) {
    let text = "";
    for (let i = start; i < start + length; i += 1) text += String.fromCharCode(bytes[i]);
    return text;
  }

  /** Buang segmen APP1/APP2/APP13/COM pada JPEG (EXIF, XMP, ICC, IPTC). */
  function stripJpeg(bytes) {
    if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return bytes;
    const parts = [bytes.subarray(0, 2)];
    let i = 2;
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    while (i + 1 < bytes.length) {
      if (bytes[i] !== 0xff) break;
      const marker = bytes[i + 1];
      if (marker === 0xda) {
        parts.push(bytes.subarray(i));
        return concatBytes(parts);
      }
      if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd9)) {
        parts.push(bytes.subarray(i, i + 2));
        i += 2;
        continue;
      }
      if (i + 4 > bytes.length) break;
      const length = view.getUint16(i + 2);
      const end = i + 2 + length;
      if (length < 2 || end > bytes.length) break;
      const drop = (marker >= 0xe1 && marker !== 0xee) || marker === 0xfe;
      if (!drop) parts.push(bytes.subarray(i, end));
      i = end;
    }
    if (i < bytes.length) parts.push(bytes.subarray(i));
    return concatBytes(parts);
  }

  /** Buang chunk ICCP/EXIF/XMP pada WebP dan bersihkan flag VP8X. */
  function stripWebp(bytes) {
    if (bytes.length < 16 || ascii(bytes, 0, 4) !== "RIFF" || ascii(bytes, 8, 4) !== "WEBP") {
      return bytes;
    }
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const chunks = [];
    let i = 12;
    while (i + 8 <= bytes.length) {
      const fourcc = ascii(bytes, i, 4);
      const size = view.getUint32(i + 4, true);
      const total = 8 + size + (size & 1);
      if (i + total > bytes.length) break;
      chunks.push({ fourcc, start: i, size, total });
      i += total;
    }

    if (!chunks.length) return bytes;

    const skip = new Set(["ICCP", "EXIF", "XMP "]);
    const parts = [];
    let payload = 4;
    for (const chunk of chunks) {
      if (skip.has(chunk.fourcc)) continue;
      let raw = bytes.subarray(chunk.start, chunk.start + chunk.total);
      if (chunk.fourcc === "VP8X") {
        const flags = bytes[chunk.start + 8];
        const cleaned = flags & ~(0x20 | 0x08 | 0x04);
        if (cleaned === 0) continue; // hanya berisi penanda metadata -> buang
        raw = bytes.slice(chunk.start, chunk.start + chunk.total);
        raw[8] = cleaned;
      }
      parts.push(raw);
      payload += chunk.total;
    }

    const output = new Uint8Array(8 + payload);
    output.set(bytes.subarray(0, 4), 0);
    new DataView(output.buffer).setUint32(4, payload, true);
    output.set(bytes.subarray(8, 12), 8);
    let offset = 12;
    for (const part of parts) {
      output.set(part, offset);
      offset += part.length;
    }
    return output;
  }

  /** Buang chunk teks/EXIF/ICC pada PNG (biasanya sudah bersih dari canvas). */
  function stripPng(bytes) {
    if (bytes.length < 16 || bytes[0] !== 0x89 || ascii(bytes, 1, 3) !== "PNG") return bytes;
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const skip = new Set(["tEXt", "iTXt", "zTXt", "eXIf", "iCCP", "tIME"]);
    const parts = [bytes.subarray(0, 8)];
    let i = 8;
    while (i + 12 <= bytes.length) {
      const length = view.getUint32(i);
      const type = ascii(bytes, i + 4, 4);
      const total = 12 + length;
      if (i + total > bytes.length) break;
      if (!skip.has(type)) parts.push(bytes.subarray(i, i + total));
      i += total;
    }
    return i === bytes.length ? concatBytes(parts) : bytes;
  }

  async function stripMetadata(blob, type) {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let cleaned = bytes;
    if (type === "image/jpeg") cleaned = stripJpeg(bytes);
    else if (type === "image/webp") cleaned = stripWebp(bytes);
    else if (type === "image/png") cleaned = stripPng(bytes);
    return new Blob([cleaned], { type });
  }

  async function scanMetadata(blob) {
    if (!blob || !blob.size) return [];
    const bytes = new Uint8Array(await blob.slice(0, 256 * 1024).arrayBuffer());
    let text = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      text += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    const found = new Set();
    if (text.includes("Exif\u0000\u0000") || text.includes("eXIf")) found.add("EXIF");
    if (text.includes("http://ns.adobe.com/xap") || text.includes("<x:xmpmeta")) found.add("XMP");
    if (/\btEXt\b|\biTXt\b|\bzTXt\b/.test(text)) found.add("teks PNG");
    if (text.includes("iCCP") || text.includes("ICC_PROFILE")) found.add("ICC");
    if (text.includes("parameters") || text.includes('"prompt"')) found.add("prompt");
    return [...found];
  }

  /* ---------------------------------------------------------------- canvas */

  const supportsEncoding = new Map();

  function canEncode(type) {
    if (supportsEncoding.has(type)) return supportsEncoding.get(type);
    let ok = false;
    try {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 1;
      ok = canvas.toDataURL(type).startsWith(`data:${type}`);
    } catch {
      ok = false;
    }
    supportsEncoding.set(type, ok);
    return ok;
  }

  const HAS_CANVAS_FILTER = (() => {
    try {
      const ctx = document.createElement("canvas").getContext("2d");
      if (!ctx) return false;
      ctx.filter = "contrast(0.9)";
      return ctx.filter === "contrast(0.9)";
    } catch {
      return false;
    }
  })();

  function makeCanvas(width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }

  async function decodeImage(file) {
    if (typeof createImageBitmap === "function") {
      try {
        return await createImageBitmap(file, { imageOrientation: "from-image" });
      } catch {
        /* jatuh ke <img> di bawah */
      }
    }
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("Gambar tidak bisa dibaca browser ini"));
      };
      img.src = url;
    });
  }

  function applyContrast(source, factor) {
    if (Math.abs(factor - 1) < 0.00001) return source;

    if (HAS_CANVAS_FILTER) {
      const output = makeCanvas(source.width, source.height);
      const ctx = output.getContext("2d");
      ctx.filter = `contrast(${factor})`;
      ctx.drawImage(source, 0, 0);
      ctx.filter = "none";
      return output;
    }

    // Fallback manual: rumus kontras CSS.
    const ctx = source.getContext("2d");
    const image = ctx.getImageData(0, 0, source.width, source.height);
    const px = image.data;
    const intercept = 127.5 * (1 - factor);
    for (let i = 0; i < px.length; i += 4) {
      px[i] = px[i] * factor + intercept;
      px[i + 1] = px[i + 1] * factor + intercept;
      px[i + 2] = px[i + 2] * factor + intercept;
    }
    ctx.putImageData(image, 0, 0);
    return source;
  }

  function encodeCanvas(canvas, type, quality) {
    return new Promise((resolve, reject) => {
      try {
        canvas.toBlob(
          (blob) => (blob ? resolve(blob) : reject(new Error("Gagal meng-encode gambar"))),
          type,
          quality,
        );
      } catch (error) {
        reject(error);
      }
    });
  }

  function resolveType(inputType, format) {
    if (format !== "keep") return format;
    if (["image/png", "image/jpeg", "image/webp"].includes(inputType)) return inputType;
    return "image/png";
  }

  async function cleanImage(file, settings) {
    const type = resolveType(file.type, settings.format);
    if (!canEncode(type)) {
      throw new Error(`Browser ini tidak bisa menyimpan ${type.split("/")[1].toUpperCase()}`);
    }

    const source = await decodeImage(file);
    const width = source.width || source.naturalWidth;
    const height = source.height || source.naturalHeight;
    if (!width || !height) throw new Error("Dimensi gambar tidak terbaca");
    if (width * height > MAX_PIXELS) {
      throw new Error(`Gambar terlalu besar (${fmtDims(width, height)}). Maksimal 48 MP.`);
    }

    const delta = settings.metadataOnly
      ? 0
      : clamp(settings.resize, 0, Math.min(width, height) - 1);

    let canvas;
    let ctx;

    if (delta > 0) {
      const small = makeCanvas(width - delta, height - delta);
      const smallCtx = small.getContext("2d");
      smallCtx.imageSmoothingEnabled = true;
      smallCtx.imageSmoothingQuality = "low";
      smallCtx.drawImage(source, 0, 0, width - delta, height - delta);

      canvas = makeCanvas(width, height);
      ctx = canvas.getContext("2d");
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(small, 0, 0, width - delta, height - delta, 0, 0, width, height);
    } else {
      canvas = makeCanvas(width, height);
      ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("Canvas 2D tidak tersedia");
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(source, 0, 0);
    }

    // Deteksi canvas yang gagal alokasi (khas gambar raksasa di iOS).
    try {
      ctx.getImageData(0, 0, 1, 1);
    } catch {
      throw new Error("Gambar terlalu besar untuk browser ini");
    }

    if (typeof source.close === "function") source.close();

    if (!settings.metadataOnly) {
      canvas = applyContrast(canvas, settings.contrast);
    }

    let output = canvas;
    if (type === "image/jpeg") {
      output = makeCanvas(width, height);
      const flat = output.getContext("2d");
      flat.fillStyle = "#ffffff";
      flat.fillRect(0, 0, width, height);
      flat.drawImage(canvas, 0, 0);
    }

    const quality = type === "image/png" ? undefined : settings.quality / 100;
    const encoded = await encodeCanvas(output, type, quality);
    const blob = await stripMetadata(encoded, type);
    const leftover = await scanMetadata(blob);

    return {
      blob,
      type,
      width,
      height,
      name: outputName(file.name, settings.suffix, type),
      size: blob.size,
      leftover,
      sourceType: file.type || "tidak diketahui",
    };
  }

  /* ------------------------------------------------------------------- zip */

  const CRC_TABLE = (() => {
    const table = new Uint32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) {
        c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      }
      table[n] = c >>> 0;
    }
    return table;
  })();

  function crc32(bytes) {
    let crc = 0xffffffff;
    for (let i = 0; i < bytes.length; i += 1) {
      crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
    }
    return (crc ^ 0xffffffff) >>> 0;
  }

  function dosTimestamp(date) {
    const time =
      (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2);
    const day = ((date.getFullYear() - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate();
    return { time: time & 0xffff, date: day & 0xffff };
  }

  async function buildZip(entries) {
    const encoder = new TextEncoder();
    const parts = [];
    const central = [];
    let offset = 0;
    const stamp = dosTimestamp(new Date());

    for (const entry of entries) {
      const data = new Uint8Array(await entry.blob.arrayBuffer());
      const name = encoder.encode(entry.name);
      const crc = crc32(data);

      const local = new Uint8Array(30 + name.length);
      const lv = new DataView(local.buffer);
      lv.setUint32(0, 0x04034b50, true);
      lv.setUint16(4, 20, true);
      lv.setUint16(6, 0x0800, true);
      lv.setUint16(8, 0, true);
      lv.setUint16(10, stamp.time, true);
      lv.setUint16(12, stamp.date, true);
      lv.setUint32(14, crc, true);
      lv.setUint32(18, data.length, true);
      lv.setUint32(22, data.length, true);
      lv.setUint16(26, name.length, true);
      lv.setUint16(28, 0, true);
      local.set(name, 30);
      parts.push(local, data);

      const header = new Uint8Array(46 + name.length);
      const cv = new DataView(header.buffer);
      cv.setUint32(0, 0x02014b50, true);
      cv.setUint16(4, 20, true);
      cv.setUint16(6, 20, true);
      cv.setUint16(8, 0x0800, true);
      cv.setUint16(10, 0, true);
      cv.setUint16(12, stamp.time, true);
      cv.setUint16(14, stamp.date, true);
      cv.setUint32(16, crc, true);
      cv.setUint32(20, data.length, true);
      cv.setUint32(24, data.length, true);
      cv.setUint16(28, name.length, true);
      cv.setUint16(30, 0, true);
      cv.setUint16(32, 0, true);
      cv.setUint16(34, 0, true);
      cv.setUint16(36, 0, true);
      cv.setUint32(38, 0, true);
      cv.setUint32(42, offset, true);
      header.set(name, 46);
      central.push(header);

      offset += local.length + data.length;
    }

    const centralSize = central.reduce((total, chunk) => total + chunk.length, 0);
    const end = new Uint8Array(22);
    const ev = new DataView(end.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(4, 0, true);
    ev.setUint16(6, 0, true);
    ev.setUint16(8, entries.length, true);
    ev.setUint16(10, entries.length, true);
    ev.setUint32(12, centralSize, true);
    ev.setUint32(16, offset, true);
    ev.setUint16(20, 0, true);

    return new Blob([...parts, ...central, end], { type: "application/zip" });
  }

  function download(blob, name) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }

  /* ----------------------------------------------------------------- queue */

  function addFiles(fileList) {
    if (state.busy) {
      toast("Tunggu proses sebelumnya selesai", "error");
      return;
    }
    const existing = new Set(
      state.items.map((item) => `${item.file.name}:${item.file.size}:${item.file.lastModified}`),
    );
    let added = 0;
    let skipped = 0;

    for (const file of Array.from(fileList || [])) {
      if (!isImageFile(file)) {
        skipped += 1;
        continue;
      }
      const key = `${file.name}:${file.size}:${file.lastModified}`;
      if (existing.has(key)) {
        skipped += 1;
        continue;
      }
      existing.add(key);
      state.counter += 1;
      state.items.push({
        id: `f${state.counter}`,
        file,
        name: file.name,
        size: file.size,
        type: file.type,
        thumb: URL.createObjectURL(file),
        status: "queued",
        error: null,
        warn: "",
        result: null,
        meta: [],
      });
      const item = state.items[state.items.length - 1];
      scanMetadata(file)
        .then((meta) => {
          item.meta = meta;
          if (item.status === "queued") renderItem(item);
        })
        .catch(() => {});
      added += 1;
    }

    if (added === 0) {
      toast(skipped ? "Tidak ada gambar baru" : "File itu bukan gambar", "error");
      return;
    }
    if (skipped) toast(`${added} ditambahkan, ${skipped} dilewati`);

    renderAll();
    updateActionBar();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function removeItem(id) {
    if (state.busy) return;
    const index = state.items.findIndex((item) => item.id === id);
    if (index === -1) return;
    const [item] = state.items.splice(index, 1);
    if (item.thumb) URL.revokeObjectURL(item.thumb);
    renderAll();
    updateActionBar();
  }

  function clearAll() {
    if (state.busy) return;
    state.items.forEach((item) => item.thumb && URL.revokeObjectURL(item.thumb));
    state.items = [];
    renderAll();
    updateActionBar();
  }

  async function processAll() {
    if (state.busy) return;
    const pending = state.items.filter((item) => item.status !== "done");
    if (!pending.length) {
      toast("Semua gambar sudah diproses");
      return;
    }

    const settings = { ...state.settings };
    state.busy = true;
    setBusyUI(true);
    let index = 0;

    for (const item of pending) {
      index += 1;
      item.status = "processing";
      item.error = null;
      renderItem(item);
      showProgress(index - 1, pending.length, item.name);

      await new Promise((resolve) => setTimeout(resolve, 0));

      try {
        const result = await cleanImage(item.file, settings);
        item.result = result;
        item.status = "done";
        item.warn = result.leftover.length
          ? `Metadata tersisa: ${result.leftover.join(", ")}`
          : "";
      } catch (error) {
        item.status = "error";
        item.error = error && error.message ? error.message : "Gagal memproses";
      }

      renderItem(item);
      showProgress(index, pending.length, item.name);
      updateActionBar();
    }

    state.busy = false;
    setBusyUI(false);
    hideProgress();

    const failed = pending.filter((item) => item.status === "error").length;
    const ok = pending.length - failed;
    toast(
      `${ok} gambar bersih${failed ? `, ${failed} gagal` : ""}`,
      failed ? "error" : "ok",
    );
    updateActionBar();
  }

  /* ------------------------------------------------------------------ view */

  function statusText(item) {
    if (item.status === "processing") return "Memproses";
    if (item.status === "done") return "Bersih";
    if (item.status === "error") return "Gagal";
    return "Siap";
  }

  function renderAll() {
    const hasItems = state.items.length > 0;
    dom.hero.hidden = hasItems;
    dom.workspace.hidden = !hasItems;

    dom.fileList.replaceChildren();
    state.items.forEach((item) => dom.fileList.append(buildRow(item)));
    updateQueueMeta();
  }

  function buildRow(item) {
    const row = document.createElement("li");
    row.className = "file-item";
    row.dataset.id = item.id;

    const thumb = document.createElement("img");
    thumb.className = "thumb";
    thumb.src = item.thumb;
    thumb.alt = "";
    thumb.loading = "lazy";
    thumb.decoding = "async";

    const main = document.createElement("div");
    main.className = "file-main";

    const name = document.createElement("span");
    name.className = "file-name";
    name.textContent = item.name;
    name.title = item.name;

    const meta = document.createElement("div");
    meta.className = "file-meta";
    meta.append(buildStatus(item));

    const size = document.createElement("span");
    size.textContent = item.result
      ? `${fmtDims(item.result.width, item.result.height)} · ${fmtBytes(item.size)} → ${fmtBytes(
          item.result.size,
        )}`
      : fmtBytes(item.size);
    meta.append(size);

    if (item.result) {
      const format = document.createElement("span");
      format.className = "tag";
      format.textContent = item.result.type.split("/")[1].toUpperCase();
      meta.append(format);
    }

    if (item.meta.length && item.status === "done") {
      const removed = document.createElement("span");
      removed.className = "tag";
      const shown = item.meta.slice(0, 2).join(", ");
      const extra = item.meta.length - 2;
      removed.textContent = `dihapus: ${shown}${extra > 0 ? ` +${extra}` : ""}`;
      meta.append(removed);
    } else if (item.meta.length) {
      const tags = document.createElement("span");
      tags.className = "tags";
      item.meta.slice(0, 3).forEach((label) => {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = label;
        tags.append(tag);
      });
      meta.append(tags);
    }

    if (item.status === "done") {
      const tag = document.createElement("span");
      tag.className = "tag ok";
      tag.textContent = "metadata bersih";
      meta.append(tag);
    }

    if (item.error) {
      const error = document.createElement("span");
      error.style.color = "var(--danger)";
      error.textContent = item.error;
      meta.append(error);
    }

    if (item.warn) {
      const warning = document.createElement("span");
      warning.className = "tag";
      warning.style.color = "var(--danger)";
      warning.textContent = item.warn;
      meta.append(warning);
    }

    main.append(name, meta);

    const actions = document.createElement("div");
    actions.className = "file-actions";
    actions.append(
      actionButton("compare", "Bandingkan", iconCompare(), !item.result),
      actionButton("download", "Unduh", iconDownload(), !item.result),
      actionButton("remove", "Hapus dari antrean", iconClose(), false),
    );

    row.append(thumb, main, actions);
    return row;
  }

  function buildStatus(item) {
    const chip = document.createElement("span");
    chip.className = "status";
    chip.dataset.state = item.status;
    chip.textContent = statusText(item);
    return chip;
  }

  function actionButton(action, label, icon, disabled) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon-btn";
    button.dataset.action = action;
    button.title = label;
    button.setAttribute("aria-label", label);
    button.innerHTML = icon;
    if (disabled) button.hidden = true;
    return button;
  }

  function iconCompare() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20V4M4 8l4-4 4 4M20 16l-4 4-4-4"/></svg>';
  }

  function iconDownload() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11m0 0 4-4m-4 4-4-4M5 19h14"/></svg>';
  }

  function iconClose() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
  }

  function renderItem(item) {
    const row = dom.fileList.querySelector(`[data-id="${item.id}"]`);
    if (!row) return;
    row.replaceWith(buildRow(item));
    updateQueueMeta();
  }

  function updateQueueMeta() {
    const total = state.items.reduce((sum, item) => sum + item.size, 0);
    const done = state.items.filter((item) => item.status === "done").length;
    dom.queueMeta.textContent = `${state.items.length} file · ${fmtBytes(total)}${
      done ? ` · ${done} selesai` : ""
    }`;
  }

  function updateActionBar() {
    const done = state.items.filter((item) => item.status === "done" && item.result);
    const pending = state.items.filter((item) => item.status !== "done");
    const total = state.items.reduce((sum, item) => sum + item.size, 0);

    if (!state.items.length) {
      dom.summary.textContent = "Pilih gambar untuk memulai";
    } else if (state.busy) {
      dom.summary.textContent = "Memproses di perangkat…";
    } else if (pending.length) {
      dom.summary.textContent = `${state.items.length} file · ${fmtBytes(total)} · ${pending.length} siap diproses`;
    } else {
      dom.summary.textContent = `${done.length} gambar siap · ${fmtBytes(
        done.reduce((sum, item) => sum + item.result.size, 0),
      )}`;
    }

    dom.processBtn.disabled = state.busy || pending.length === 0;
    dom.processBtn.textContent = state.busy
      ? "Memproses…"
      : !state.items.length
        ? "Proses"
        : pending.length
          ? `Proses ${pending.length} gambar`
          : "Selesai";

    dom.zipBtn.disabled = state.busy || done.length === 0;
    dom.zipBtn.textContent = done.length ? `Unduh ZIP (${done.length})` : "Unduh ZIP";
  }

  function setBusyUI(busy) {
    dom.addBtn.disabled = busy;
    dom.clearBtn.disabled = busy;
    dom.pickBtn.disabled = busy;
    dom.pickFolderBtn.disabled = busy;
    dom.metadataOnly.disabled = busy;
    dom.suffix.disabled = busy;
    dom.formatGroup.querySelectorAll("button").forEach((button) => {
      button.disabled = busy;
    });
    if (!busy) renderSettings();
  }

  function showProgress(done, total, label) {
    dom.progress.hidden = false;
    dom.progressFill.style.width = `${total ? Math.round((done / total) * 100) : 0}%`;
    dom.progressLabel.textContent = done >= total ? "Selesai" : label;
    dom.progressCount.textContent = `${done}/${total}`;
  }

  function hideProgress() {
    dom.progress.hidden = true;
    dom.progressFill.style.width = "0%";
  }

  /* --------------------------------------------------------------- compare */

  let compareUrls = [];

  function openCompare(item) {
    if (!item.result) return;
    closeCompare();

    const beforeUrl = URL.createObjectURL(item.file);
    const afterUrl = URL.createObjectURL(item.result.blob);
    compareUrls = [beforeUrl, afterUrl];

    dom.compareBefore.src = beforeUrl;
    dom.compareAfter.src = afterUrl;
    dom.compareTitle.textContent = item.name;
    dom.compareBeforeInfo.textContent = `${fmtDims(item.result.width, item.result.height)} · ${fmtBytes(item.size)}`;
    dom.compareAfterInfo.textContent = `${item.result.type.split("/")[1].toUpperCase()} · ${fmtBytes(item.result.size)}`;
    dom.modal.hidden = false;
    document.body.style.overflow = "hidden";
    setComparePosition(50);
    dom.closeCompare.focus();
  }

  function closeCompare() {
    if (dom.modal.hidden) return;
    dom.modal.hidden = true;
    document.body.style.overflow = "";
    dom.compareBefore.removeAttribute("src");
    dom.compareAfter.removeAttribute("src");
    compareUrls.forEach((url) => URL.revokeObjectURL(url));
    compareUrls = [];
  }

  function setComparePosition(percent) {
    const value = clamp(percent, 2, 98);
    dom.compareStage.style.setProperty("--pos", `${value}%`);
    dom.compareRange.value = String(Math.round(value));
  }

  /* ------------------------------------------------------------------ zip */

  async function downloadZip() {
    const done = state.items.filter((item) => item.result);
    if (!done.length) return;

    dom.zipBtn.disabled = true;
    const original = dom.zipBtn.textContent;
    dom.zipBtn.textContent = "Menyiapkan…";

    try {
      const used = new Map();
      const entries = done.map((item) => {
        let name = item.result.name;
        const count = used.get(name) || 0;
        used.set(name, count + 1);
        if (count) {
          const dot = name.lastIndexOf(".");
          name = `${name.slice(0, dot)}-${count + 1}${name.slice(dot)}`;
        }
        return { name, blob: item.result.blob };
      });

      const zip = await buildZip(entries);
      const stamp = new Date().toISOString().slice(0, 10);
      download(zip, `synthid-clean-${stamp}.zip`);
      toast(`${entries.length} gambar dimasukkan ke ZIP`, "ok");
    } catch (error) {
      toast(error.message || "Gagal membuat ZIP", "error");
    } finally {
      dom.zipBtn.textContent = original;
      updateActionBar();
    }
  }

  /* --------------------------------------------------------------- events */

  function bindEvents() {
    dom.pickBtn.addEventListener("click", () => dom.fileInput.click());
    dom.addBtn.addEventListener("click", () => dom.fileInput.click());
    dom.emptyPickBtn?.addEventListener("click", () => dom.fileInput.click());
    dom.pickFolderBtn.addEventListener("click", () => dom.folderInput.click());
    dom.dropzone.addEventListener("click", () => dom.fileInput.click());
    dom.dropzone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        dom.fileInput.click();
      }
    });

    dom.fileInput.addEventListener("change", () => {
      addFiles(dom.fileInput.files);
      dom.fileInput.value = "";
    });
    dom.folderInput.addEventListener("change", () => {
      addFiles(dom.folderInput.files);
      dom.folderInput.value = "";
    });

    dom.fileList.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-action]");
      if (!button) return;
      const row = button.closest("[data-id]");
      const item = state.items.find((entry) => entry.id === row?.dataset.id);
      if (!item) return;

      if (button.dataset.action === "remove") removeItem(item.id);
      if (button.dataset.action === "download" && item.result) {
        download(item.result.blob, item.result.name);
      }
      if (button.dataset.action === "compare") openCompare(item);
    });

    dom.clearBtn.addEventListener("click", clearAll);
    dom.processBtn.addEventListener("click", processAll);
    dom.zipBtn.addEventListener("click", downloadZip);

    dom.formatGroup.addEventListener("click", (event) => {
      const button = event.target.closest("[data-format]");
      if (!button) return;
      updateSettings({ format: button.dataset.format });
    });

    dom.quality.addEventListener("input", () => {
      updateSettings({ quality: Number(dom.quality.value) });
    });
    dom.resize.addEventListener("input", () => {
      updateSettings({ resize: Number(dom.resize.value) });
    });
    dom.contrast.addEventListener("input", () => {
      updateSettings({ contrast: Number(dom.contrast.value) });
    });
    dom.suffix.addEventListener("input", () => {
      updateSettings({ suffix: dom.suffix.value });
    });
    dom.metadataOnly.addEventListener("change", () => {
      updateSettings({ metadataOnly: dom.metadataOnly.checked });
    });
    dom.resetBtn.addEventListener("click", () => {
      state.settings = { ...DEFAULTS };
      renderSettings();
      saveSettings();
      toast("Pengaturan direset");
    });

    dom.closeCompare.addEventListener("click", closeCompare);
    dom.modal.addEventListener("click", (event) => {
      if (event.target === dom.modal) closeCompare();
    });
    dom.compareRange.addEventListener("input", () => {
      setComparePosition(Number(dom.compareRange.value));
    });

    const stage = dom.compareStage;
    let dragging = false;
    const positionFromEvent = (event) => {
      const rect = stage.getBoundingClientRect();
      setComparePosition(((event.clientX - rect.left) / rect.width) * 100);
    };
    stage.addEventListener("pointerdown", (event) => {
      if (event.target === dom.compareRange) return;
      dragging = true;
      stage.setPointerCapture?.(event.pointerId);
      positionFromEvent(event);
    });
    stage.addEventListener("pointermove", (event) => {
      if (dragging) positionFromEvent(event);
    });
    stage.addEventListener("pointerup", () => {
      dragging = false;
    });
    stage.addEventListener("pointercancel", () => {
      dragging = false;
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeCompare();
    });

    // Drag & drop global
    let dragDepth = 0;
    const hasFiles = (event) => Array.from(event.dataTransfer?.types || []).includes("Files");
    window.addEventListener("dragenter", (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      dragDepth += 1;
      dom.dropOverlay.hidden = false;
    });
    window.addEventListener("dragover", (event) => {
      if (hasFiles(event)) event.preventDefault();
    });
    window.addEventListener("dragleave", () => {
      dragDepth = Math.max(0, dragDepth - 1);
      if (!dragDepth) dom.dropOverlay.hidden = true;
    });
    window.addEventListener("drop", (event) => {
      if (!hasFiles(event)) return;
      event.preventDefault();
      dragDepth = 0;
      dom.dropOverlay.hidden = true;
      addFiles(event.dataTransfer.files);
    });

    window.addEventListener("paste", (event) => {
      const files = Array.from(event.clipboardData?.files || []);
      if (files.length) addFiles(files);
    });

    // Install prompt
    let deferredPrompt = null;
    window.addEventListener("beforeinstallprompt", (event) => {
      event.preventDefault();
      deferredPrompt = event;
      dom.installBtn.hidden = false;
    });
    dom.installBtn.addEventListener("click", async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      dom.installBtn.hidden = true;
    });
    window.addEventListener("appinstalled", () => {
      dom.installBtn.hidden = true;
      toast("Aplikasi terpasang di perangkat", "ok");
    });
  }

  /* ------------------------------------------------------------- bootstrap */

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    const host = location.hostname;
    const secure =
      location.protocol === "https:" ||
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "[::1]";
    if (!secure) return;
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./sw.js").catch(() => {
        /* abaikan: aplikasi tetap jalan tanpa offline */
      });
    });
  }

  function init() {
    /* di layar sempit, pengaturan dilipat agar antrean langsung terlihat */
    dom.settingsPanel.open = window.matchMedia("(min-width: 981px)").matches;
    state.settings = loadSettings();
    renderSettings();
    bindEvents();
    renderAll();
    updateActionBar();
    registerServiceWorker();

    state.items.forEach(async (item) => {
      item.meta = await scanMetadata(item.file);
      renderItem(item);
    });
  }

  init();
})();
