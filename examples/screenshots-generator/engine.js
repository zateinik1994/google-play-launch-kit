'use strict';

// Shared by the local editor and headless exporter. No requests or remote assets.
(function (global) {
  const devices = ['phone', 'tablet-7', 'tablet-10'];
  const presets = Object.freeze({
    'phone-portrait': { device: 'phone', width: 1080, height: 1920, layout: 'stacked', textRatio: .18 },
    'phone-landscape': { device: 'phone', width: 1920, height: 1080, layout: 'split', textRatio: .38 },
    'tablet-7-portrait': { device: 'tablet-7', width: 1440, height: 2560, layout: 'ui-only', textRatio: .18 },
    'tablet-7-landscape': { device: 'tablet-7', width: 2560, height: 1440, layout: 'ui-only', textRatio: .38 },
    'tablet-10-portrait': { device: 'tablet-10', width: 1440, height: 2560, layout: 'ui-only', textRatio: .18 },
    'tablet-10-landscape': { device: 'tablet-10', width: 2560, height: 1440, layout: 'ui-only', textRatio: .38 }
  });
  const MAX_PROJECT_BYTES = 225 * 1024 * 1024, MAX_SOURCE_BYTES = 20 * 1024 * 1024;
  const localePattern = /^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/;
  const copy = () => ({ headline: '', subtitle: '', altText: '' });
  const locale = () => ({ appName: '', draft: copy(), feature: copy() });
  const emptyProject = () => ({ version: 2, locale: 'en-US', format: 'screenshot', selectedId: null,
    profileId: 'phone-portrait', customProfiles: {}, profileOptions: {}, exportPresets: ['phone-portrait'],
    exportLocales: ['en-US'], exportFeature: true, featureCaptureId: null,
    palette: { background: '#e5f6ef', accent: '#3a9475', foreground: '#12382a' },
    locales: { 'en-US': locale(), 'ru-RU': locale() }, captures: [] });
  const isRTL = code => /^(ar|fa|he|ur|ps|sd|yi|dv|ug)(-|$)/i.test(code);
  const slug = value => value.normalize('NFKD').replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '').toLowerCase().slice(0, 60) || 'app';
  function object(value, message) { if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(message); }
  function checkedCopy(value) {
    object(value, 'Project copy is missing.');
    const result = {};
    for (const [key, limit] of [['headline', 100], ['subtitle', 110], ['altText', 140]]) {
      if (typeof value[key] !== 'string' || value[key].length > limit || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value[key])) throw new Error(`Invalid or oversized ${key}.`);
      result[key] = value[key];
    }
    return result;
  }
  function checkedProfile(value) {
    object(value, 'Invalid profile.');
    const { device, width, height } = value;
    if (!devices.includes(device) || !Number.isInteger(width) || !Number.isInteger(height)) throw new Error('Profile needs a device and integer dimensions.');
    if (device === 'phone') {
      if (Math.min(width, height) < 320 || Math.max(width, height) > 3840 || Math.max(width, height) > 2 * Math.min(width, height)) throw new Error('Phone dimensions: 320–3840 px, longer side at most twice the shorter.');
    } else if (Math.min(width, height) < 1080 || Math.max(width, height) > 7680 || !(width * 16 === height * 9 || width * 9 === height * 16)) throw new Error('Tablet profiles: 1080–7680 px and 9:16 or 16:9.');
    if (width * height > 24000000) throw new Error('This renderer limits each output to 24 megapixels.');
    const layout = value.layout ?? 'stacked', textRatio = value.textRatio ?? .18, imageScale = value.imageScale ?? 1;
    if (!['stacked', 'split', 'ui-only'].includes(layout) || !Number.isFinite(textRatio) || textRatio < .12 || textRatio > .6 || !Number.isFinite(imageScale) || imageScale < .5 || imageScale > 1) throw new Error('Invalid layout, text ratio (0.12–0.60) or image scale (0.50–1.00).');
    return { device, width, height, layout, textRatio, imageScale };
  }
  function sourceDimensions(base64, format) {
    const bytes = atob(format === 'png' ? base64.slice(0, 64) : base64), u16 = i => bytes.charCodeAt(i) * 256 + bytes.charCodeAt(i + 1);
    if (format === 'png') {
      if (bytes.length < 29 || bytes.slice(0, 8) !== '\x89PNG\r\n\x1a\n' || bytes.slice(12, 16) !== 'IHDR') throw new Error('Invalid PNG source header.');
      const u32 = i => bytes.charCodeAt(i) * 16777216 + bytes.charCodeAt(i + 1) * 65536 + u16(i + 2);
      return { width: u32(16), height: u32(20) };
    }
    if (bytes.charCodeAt(0) !== 255 || bytes.charCodeAt(1) !== 216) throw new Error('Invalid JPEG source header.');
    let offset = 2;
    while (offset < bytes.length) {
      if (bytes.charCodeAt(offset++) !== 255) throw new Error('Invalid JPEG source marker.');
      while (bytes.charCodeAt(offset) === 255) offset++;
      const marker = bytes.charCodeAt(offset++);
      if (marker === 217 || marker === 218) break;
      if (marker === 1 || marker >= 208 && marker <= 216) continue;
      const length = u16(offset); if (length < 2 || offset + length > bytes.length) throw new Error('Truncated JPEG source header.');
      if ([192,193,194,195,197,198,199,201,202,203,205,206,207].includes(marker)) {
        if (length < 8) throw new Error('Invalid JPEG frame header.');
        return { width: u16(offset + 5), height: u16(offset + 3) };
      }
      offset += length;
    }
    throw new Error('JPEG source has no frame dimensions.');
  }
  function profile(project, id = project.profileId) {
    if (id === 'feature-graphic') return { device: 'all', width: 1024, height: 500, layout: 'split', textRatio: .56, imageScale: 1, ...(project.profileOptions[id] || {}) };
    const base = presets[id] || project.customProfiles[id];
    if (!base) throw new Error(`Unknown export profile: ${id}`);
    return checkedProfile({ ...base, ...(project.profileOptions[id] || {}) });
  }
  async function validateProject(input, decodeImage) {
    object(input, 'Invalid project.');
    if (![1, 2].includes(input.version) || !['screenshot', 'feature-graphic'].includes(input.format)) throw new Error('Unsupported project. Expected version 1 or 2.');
    object(input.locales, 'Project needs languages.');
    const codes = Object.keys(input.locales);
    if (!codes.length || codes.length > 50) throw new Error('Project needs 1–50 languages.');
    const p = emptyProject(); p.locales = Object.create(null);
    for (const code of codes) {
      const value = input.locales[code];
      if (!localePattern.test(code) || !value || typeof value.appName !== 'string' || value.appName.length > 30 || /[\u0000-\u001f]/.test(value.appName)) throw new Error('Invalid language or app name.');
      p.locales[code] = { appName: value.appName, draft: checkedCopy(value.draft), feature: checkedCopy(value.feature) };
    }
    if (!Object.hasOwn(p.locales, input.locale)) throw new Error('Selected language is missing.');
    p.locale = input.locale; p.format = input.format;
    for (const key of ['background', 'accent', 'foreground']) {
      if (!/^#[0-9a-f]{6}$/i.test(input.palette?.[key])) throw new Error('Project colors must use six-digit hex values.');
      p.palette[key] = input.palette[key];
    }
    if (input.version === 2) {
      for (const field of ['customProfiles', 'profileOptions']) { if (input[field] !== undefined) object(input[field], `Invalid ${field}.`); }
      p.customProfiles = Object.create(null); p.profileOptions = Object.create(null);
      for (const [id, config] of Object.entries(input.customProfiles || {})) {
        if (!/^custom-(phone|tablet-7|tablet-10)$/.test(id)) throw new Error('Invalid custom profile ID.');
        p.customProfiles[id] = checkedProfile(config);
        if (id !== `custom-${config.device}`) throw new Error('Custom profile device differs from its ID.');
      }
      for (const [id, options] of Object.entries(input.profileOptions || {})) {
        object(options, 'Invalid profile options.');
        if (!presets[id] && !p.customProfiles[id] && id !== 'feature-graphic') throw new Error('Unknown profile options.');
        const config = checkedProfile({ ...(id === 'feature-graphic' ? { device: 'phone', width: 1024, height: 512 } : presets[id] || p.customProfiles[id]), layout: options.layout, textRatio: options.textRatio, imageScale: options.imageScale });
        p.profileOptions[id] = { layout: config.layout, textRatio: config.textRatio, imageScale: config.imageScale };
      }
      p.profileId = input.profileId ?? 'phone-portrait'; profile(p);
      for (const [field, allowed, fallback] of [['exportPresets', [...Object.keys(presets), ...Object.keys(p.customProfiles)], [p.profileId]], ['exportLocales', codes, [p.locale]]]) {
        const values = input[field] ?? fallback;
        if (!Array.isArray(values) || values.length > allowed.length || values.some(v => !allowed.includes(v)) || new Set(values).size !== values.length) throw new Error(`Invalid ${field}.`);
        p[field] = [...values];
      }
      if (input.exportFeature !== undefined && typeof input.exportFeature !== 'boolean') throw new Error('Invalid exportFeature.');
      p.exportFeature = input.exportFeature ?? true;
    } else p.exportLocales = [p.locale];
    if (!Array.isArray(input.captures) || input.captures.length > 24) throw new Error('Project supports up to eight captures per device (24 total).');
    const images = new Map(), counts = {}, captures = []; let totalBytes = 0, totalPixels = 0;
    const checkedSource = async (source, key) => {
      object(source, 'Invalid source capture.');
      if (typeof source.name !== 'string' || !source.name || source.name.length > 300) throw new Error('Invalid source name.');
      const match = typeof source.dataUrl === 'string' && source.dataUrl.match(/^data:image\/(png|jpeg);base64,((?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?)$/);
      if (!match || !match[2]) throw new Error('Sources must embed local PNG/JPEG base64 data.');
      const bytes = match[2].length * 3 / 4 - (match[2].endsWith('==') ? 2 : match[2].endsWith('=') ? 1 : 0);
      totalBytes += source.dataUrl.length;
      if (bytes > MAX_SOURCE_BYTES || totalBytes > MAX_PROJECT_BYTES) throw new Error('Sources exceed 20 MB each or 225 MB total.');
      const header = sourceDimensions(match[2], match[1]);
      if (Math.min(header.width, header.height) < 1 || Math.max(header.width, header.height) > 8192 || header.width * header.height > 40000000) throw new Error('Sources are limited to 8192 px per side and 40 megapixels.');
      const image = await decodeImage(source.dataUrl);
      const width = image.width, height = image.height;
      if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 || Math.max(width, height) > 8192 || width * height > 40000000) throw new Error('Sources are limited to 8192 px per side and 40 megapixels.');
      totalPixels += width * height;
      if (totalPixels > 120000000) throw new Error('Decoded project sources exceed 120 megapixels. Split into smaller projects.');
      images.set(key, image); return { name: source.name, dataUrl: source.dataUrl, width, height };
    };
    for (const item of input.captures) {
      if (!item || typeof item.id !== 'string' || !item.id || item.id.length > 100 || captures.some(c => c.id === item.id)) throw new Error('Invalid or duplicate capture ID.');
      const device = input.version === 1 ? 'phone' : item.device;
      if (!devices.includes(device) || (counts[device] = (counts[device] || 0) + 1) > 8) throw new Error('Use up to eight captures for each device.');
      const source = await checkedSource(item, `${item.id}:default`), translations = Object.create(null), sources = Object.create(null);
      for (const code of codes) translations[code] = checkedCopy(item.copy?.[code]);
      if (item.sources !== undefined) object(item.sources, 'Invalid localized sources.');
      for (const [code, override] of Object.entries(input.version === 1 ? {} : item.sources || {})) {
        if (!codes.includes(code)) throw new Error('Source override language is missing.');
        sources[code] = await checkedSource(override, `${item.id}:${code}`);
      }
      const layouts = Object.create(null);
      if (item.layouts !== undefined) object(item.layouts, 'Invalid per-capture layouts.');
      for (const [id, options] of Object.entries(input.version === 1 ? {} : item.layouts || {})) {
        object(options, 'Invalid capture layout.');
        const base = profile(p, id);
        if (id === 'feature-graphic' || base.device !== device) throw new Error('Capture layout profile/device mismatch.');
        const checked = checkedProfile({ ...base, layout: options.layout, textRatio: options.textRatio, imageScale: options.imageScale });
        layouts[id] = { layout: checked.layout, textRatio: checked.textRatio, imageScale: checked.imageScale };
      }
      captures.push({ id: item.id, device, ...source, copy: translations, sources, layouts });
    }
    p.captures = captures;
    p.selectedId = captures.some(c => c.id === input.selectedId) ? input.selectedId : captures[0]?.id || null;
    p.featureCaptureId = captures.some(c => c.id === input.featureCaptureId) ? input.featureCaptureId : p.selectedId;
    return { project: p, images };
  }
  const sourceFor = (capture, code) => ({ source: capture.sources?.[code] || capture, key: `${capture.id}:${capture.sources?.[code] ? code : 'default'}`, fallback: !capture.sources?.[code] });
  function jobs(project, options = {}) {
    const codes = options.locales || project.exportLocales, ids = options.presets || project.exportPresets;
    if (!Array.isArray(codes) || !Array.isArray(ids) || !codes.length || codes.some(c => !Object.hasOwn(project.locales, c)) || new Set(codes).size !== codes.length || new Set(ids).size !== ids.length) throw new Error('Choose distinct existing export languages/profiles.');
    const result = [];
    for (const code of codes) {
      for (const id of ids) {
        const config = profile(project, id), captures = project.captures.filter(c => c.device === config.device);
        for (const [index, capture] of captures.entries()) result.push({ locale: code, profileId: id, captureId: capture.id, order: index + 1, kind: 'screenshot', file: `${code}/${id}/${String(index + 1).padStart(2, '0')}-${slug(capture.name)}.png` });
      }
      if (options.feature ?? project.exportFeature) {
        const capture = project.captures.find(c => c.id === project.featureCaptureId);
        if (!capture) throw new Error('Choose a real capture for the feature graphic.');
        result.push({ locale: code, profileId: 'feature-graphic', captureId: capture.id, order: 0, kind: 'feature-graphic', file: `${code}/feature-graphic.png` });
      }
    }
    if (!result.length) throw new Error('No captures match the selected device profiles.');
    if (result.length > 400) throw new Error('Export is limited to 400 assets. Split the batch.');
    return result;
  }
  function render(canvas, project, images, job, guides = false, preview = false) {
    const capture = project.captures.find(c => c.id === job.captureId), code = job.locale;
    const config = { ...profile(project, job.profileId), ...(capture?.layouts?.[job.profileId] || {}) };
    if (!capture || !Object.hasOwn(project.locales, code)) throw new Error('Capture/language is missing.');
    if (job.kind !== 'feature-graphic' && capture.device !== config.device) throw new Error('A phone capture cannot demonstrate a tablet experience.');
    const chosen = sourceFor(capture, code), image = images.get(chosen.key), words = job.kind === 'feature-graphic' ? project.locales[code].feature : capture.copy[code];
    if (!image) throw new Error('Source capture is not decoded.');
    if (!preview && config.layout !== 'ui-only' && (!project.locales[code].appName.trim() || !words.headline.trim())) throw new Error(`${code} / ${job.profileId} / ${job.order}: app name and headline are required for this layout.`);
    canvas.width = config.width; canvas.height = config.height;
    const ctx = canvas.getContext('2d', { alpha: false }), w = canvas.width, h = canvas.height, rtl = isRTL(code), pad = Math.min(w, h) * .045;
    ctx.fillStyle = project.palette.background; ctx.fillRect(0, 0, w, h);
    ctx.direction = rtl ? 'rtl' : 'ltr'; ctx.textBaseline = 'top'; ctx.fillStyle = project.palette.foreground;
    let overflow = false, box;
    function lines(text, width) {
      const output = [];
      for (const paragraph of text.split('\n')) {
        let line = '';
        const tokens = /\s/.test(paragraph) ? paragraph.split(/\s+/) : (/[\u0600-\u06ff]/.test(paragraph) ? [paragraph] : Array.from(new Intl.Segmenter(code, { granularity: 'grapheme' }).segment(paragraph), s => s.segment));
        const separator = /\s/.test(paragraph) ? ' ' : '';
        for (const token of tokens) { const next = line ? line + separator + token : token; if (line && ctx.measureText(next).width > width) { output.push(line); line = token; } else line = next; }
        output.push(line);
      }
      return output;
    }
    function text(value, x, y, width, height, startSize, maxLines, weight, align) {
      if (!value) return;
      let size = startSize, wrapped;
      while (true) {
        ctx.font = `${weight} ${size}px system-ui, -apple-system, "Segoe UI", sans-serif`; wrapped = lines(value, width);
        if ((wrapped.length <= maxLines && wrapped.length * size * 1.14 <= height && wrapped.every(line => ctx.measureText(line).width <= width)) || size <= startSize * .6) break;
        size -= Math.max(1, startSize * .025);
      }
      if (wrapped.length > maxLines || wrapped.length * size * 1.14 > height || wrapped.some(line => ctx.measureText(line).width > width)) overflow = true;
      ctx.textAlign = align;
      wrapped.slice(0, maxLines).forEach((line, i) => ctx.fillText(line, x, y + i * size * 1.14));
    }
    const name = project.locales[code].appName || (preview ? 'Your app name' : ''), headline = words.headline || (preview ? 'Tell your app’s story' : '');
    if (config.layout === 'ui-only') box = { x: 0, y: 0, width: w, height: h };
    else if (config.layout === 'stacked') {
      const header = h * config.textRatio;
      text(name, w / 2, pad, w - 2 * pad, header * .15, w * .024, 1, 600, 'center');
      text(headline, w / 2, pad + header * .18, w - 2 * pad, header * .6, w * .072, 2, 700, 'center');
      text(words.subtitle, w / 2, pad + header * .8, w - 2 * pad, header * .16, w * .028, 1, 400, 'center');
      box = { x: pad, y: header + pad * 1.6, width: w - 2 * pad, height: h - header - pad * 2.6 };
    } else {
      const textWidth = (w - 3 * pad) * config.textRatio, imageWidth = w - 3 * pad - textWidth, textX = rtl ? w - pad : pad, align = rtl ? 'right' : 'left';
      text(name, textX, h * .15, textWidth, h * .08, h * .04, 1, 600, align);
      text(headline, textX, h * .28, textWidth, h * .35, h * .1, 3, 700, align);
      text(words.subtitle, textX, h * .7, textWidth, h * .16, h * .04, 2, 400, align);
      box = { x: rtl ? pad : 2 * pad + textWidth, y: pad, width: imageWidth, height: h - 2 * pad };
    }
    const scale = Math.min(box.width / image.width, box.height / image.height) * config.imageScale, iw = image.width * scale, ih = image.height * scale;
    const bounds = { x: box.x + (box.width - iw) / 2, y: box.y + (box.height - ih) / 2, width: iw, height: ih };
    ctx.drawImage(image, bounds.x, bounds.y, iw, ih);
    if (guides) { ctx.strokeStyle = project.palette.accent; ctx.setLineDash([9, 9]); ctx.lineWidth = 2; ctx.strokeRect(pad, pad, w - 2 * pad, h - 2 * pad); }
    if (overflow && !preview) throw new Error(`${code} / ${job.profileId} / ${job.order}: text overflows; shorten copy or adjust the layout.`);
    return { ...job, device_type: job.kind === 'feature-graphic' ? 'all' : capture.device, width: w, height: h, app_name: project.locales[code].appName,
      source_name: chosen.source.name, source_locale: chosen.fallback ? 'default' : code, source_fallback: chosen.fallback,
      headline: config.layout === 'ui-only' ? '' : words.headline, alt_text: words.altText, rtl, layout: config.layout, image_bounds: bounds,
      technical_status: 'RGB-PNG-rendered', visual_status: 'pending', console_status: 'not-uploaded', warnings: [...(scale > 1 ? ['source_upscaled'] : []), ...(!words.altText.trim() ? ['alt_text_missing'] : []), ...(capture.device !== 'phone' && config.layout !== 'ui-only' ? ['tablet_has_text_overlay'] : []), ...(chosen.fallback ? ['default_source_used_verify_UI_language'] : [])], overflow };
  }
  const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  function crc32(bytes) { let crc = 0xffffffff; for (const byte of bytes) crc = crcTable[(crc ^ byte) & 255] ^ (crc >>> 8); return (crc ^ 0xffffffff) >>> 0; }
  function chunk(type, data) {
    const bytes = new Uint8Array(data.length + 12), view = new DataView(bytes.buffer); view.setUint32(0, data.length);
    bytes.set(new TextEncoder().encode(type), 4); bytes.set(data, 8); view.setUint32(data.length + 8, crc32(bytes.subarray(4, data.length + 8))); return bytes;
  }
  function storedDeflate(bytes) {
    const count = Math.ceil(bytes.length / 65535), output = new Uint8Array(bytes.length + count * 5 + 6); let offset = 2; output[0] = 0x78; output[1] = 0x01;
    for (let start = 0; start < bytes.length; start += 65535) { const size = Math.min(65535, bytes.length - start), last = start + size === bytes.length; output[offset++] = last ? 1 : 0; output[offset++] = size & 255; output[offset++] = size >>> 8; output[offset++] = ~size & 255; output[offset++] = ~size >>> 8 & 255; output.set(bytes.subarray(start, start + size), offset); offset += size; }
    let a = 1, b = 0; for (const byte of bytes) { a = (a + byte) % 65521; b = (b + a) % 65521; }
    new DataView(output.buffer).setUint32(offset, ((b << 16) | a) >>> 0); return output;
  }
  async function rgbPNG(canvas) {
    const { width, height } = canvas, pixels = canvas.getContext('2d').getImageData(0, 0, width, height).data, row = width * 3 + 1, raw = new Uint8Array(row * height);
    for (let y = 0; y < height; y++) { let target = y * row + 1, source = y * width * 4; for (let x = 0; x < width; x++) { raw[target++] = pixels[source++]; raw[target++] = pixels[source++]; raw[target++] = pixels[source++]; source++; } }
    const packed = typeof CompressionStream === 'function' ? new Uint8Array(await new Response(new Blob([raw]).stream().pipeThrough(new CompressionStream('deflate'))).arrayBuffer()) : storedDeflate(raw);
    const ihdr = new Uint8Array(13), view = new DataView(ihdr.buffer); view.setUint32(0, width); view.setUint32(4, height); ihdr[8] = 8; ihdr[9] = 2;
    return new Blob([new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', packed), chunk('IEND', new Uint8Array())], { type: 'image/png' });
  }
  // ZIP STORE preserves PNG bytes; UTF-8 names and checksums, no dependency/CDN.
  function zip(entries) {
    if (entries.length > 402 || entries.reduce((sum, e) => sum + e.data.length, 0) > 256 * 1024 * 1024) throw new Error('ZIP is limited to 400 assets / 256 MB. Split the batch.');
    const parts = [], directory = []; let offset = 0, directorySize = 0;
    for (const entry of entries) {
      if (typeof entry.name !== 'string' || /(^\/|\\|(?:^|\/)\.\.(?:\/|$))/.test(entry.name)) throw new Error('Invalid ZIP path.');
      const name = new TextEncoder().encode(entry.name), data = entry.data, crc = crc32(data), header = new Uint8Array(30), h = new DataView(header.buffer);
      h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x800, true); h.setUint16(12, 0x21, true); h.setUint32(14, crc, true); h.setUint32(18, data.length, true); h.setUint32(22, data.length, true); h.setUint16(26, name.length, true);
      parts.push(header, name, data);
      const central = new Uint8Array(46), c = new DataView(central.buffer); c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x800, true); c.setUint16(14, 0x21, true); c.setUint32(16, crc, true); c.setUint32(20, data.length, true); c.setUint32(24, data.length, true); c.setUint16(28, name.length, true); c.setUint32(42, offset, true);
      directory.push(central, name); directorySize += central.length + name.length; offset += header.length + name.length + data.length;
    }
    const end = new Uint8Array(22), e = new DataView(end.buffer); e.setUint32(0, 0x06054b50, true); e.setUint16(8, entries.length, true); e.setUint16(10, entries.length, true); e.setUint32(12, directorySize, true); e.setUint32(16, offset, true);
    return new Blob([...parts, ...directory, end], { type: 'application/zip' });
  }
  function manifestCSV(assets) {
    const fields = ['file', 'locale', 'device_type', 'profileId', 'kind', 'order', 'width', 'height', 'captureId', 'source_name', 'source_locale', 'source_fallback', 'headline', 'alt_text', 'rtl', 'layout', 'technical_status', 'visual_status', 'console_status', 'warnings'];
    const cell = value => { let text = Array.isArray(value) ? value.join(';') : String(value ?? ''); if (/^[=+@-]/.test(text)) text = "'" + text; return '"' + text.replace(/"/g, '""') + '"'; };
    return fields.join(',') + '\r\n' + assets.map(a => fields.map(f => cell(a[f])).join(',')).join('\r\n') + '\r\n';
  }
  const api = { devices, presets, MAX_PROJECT_BYTES, emptyCopy: copy, emptyLocale: locale, emptyProject, isRTL, slug, checkedProfile, sourceDimensions, profile, validateProject, sourceFor, jobs, render, crc32, rgbPNG, zip, manifestCSV };
  global.PlayStudio = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : window);
