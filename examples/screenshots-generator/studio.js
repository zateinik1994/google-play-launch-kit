'use strict';

(() => {
  const $ = id => document.getElementById(id);
  const canvas = $('preview');
  const ctx = canvas.getContext('2d', { alpha: false });
  const palettes = {
    mint: { background: '#e5f6ef', accent: '#3a9475', foreground: '#12382a' },
    ink: { background: '#172e32', accent: '#66cca6', foreground: '#edfaf4' },
    apricot: { background: '#fff0df', accent: '#d98253', foreground: '#562e24' }
  };
  const emptyCopy = () => ({ headline: '', subtitle: '', altText: '' });
  const emptyLocale = () => ({ appName: '', draft: emptyCopy(), feature: emptyCopy() });
  let state = { version: 1, locale: 'en-US', format: 'screenshot', selectedId: null, palette: { ...palettes.mint }, locales: { 'en-US': emptyLocale(), 'ru-RU': emptyLocale() }, captures: [] };
  const decodedImages = new Map();
  let overflow = false;
  let exporting = false;
  const selected = () => state.captures.find(item => item.id === state.selectedId);
  const copy = () => state.format === 'feature-graphic' ? state.locales[state.locale].feature : (selected()?.copy[state.locale] || state.locales[state.locale].draft);
  const tell = (message, error = false) => { $('status').textContent = message; $('status').classList.toggle('error', error); };
  const localePattern = /^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/;

  function syncFields() {
    $('locale').replaceChildren(...Object.keys(state.locales).map(code => {
      const option = document.createElement('option'); option.value = code; option.textContent = code; return option;
    }));
    $('locale').value = state.locale;
    $('app-name').value = state.locales[state.locale].appName;
    $('headline').value = copy().headline;
    $('subtitle').value = copy().subtitle;
    $('alt-text').value = copy().altText;
    $('headline-scope').textContent = state.format === 'screenshot' ? 'for this capture' : 'for the feature graphic';
    for (const key of ['background', 'accent', 'foreground']) $(key).value = state.palette[key];
    document.querySelectorAll('[data-format]').forEach(button => {
      const active = button.dataset.format === state.format;
      button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active));
    });
    $('preview-title').textContent = state.format === 'screenshot' ? 'Phone screenshot' : 'Feature graphic';
    $('size-label').textContent = state.format === 'screenshot' ? '1080 × 1920 · 9:16' : '1024 × 500 · feature graphic';
    canvas.classList.toggle('feature', state.format === 'feature-graphic');
    renderCaptureList();
    render();
  }

  function renderCaptureList() {
    $('capture-count').textContent = `${state.captures.length} / 8`;
    $('capture-list').replaceChildren(...state.captures.map((capture, index) => {
      const item = document.createElement('div'); item.className = 'capture-item';
      const button = document.createElement('button'); button.className = `capture-select${capture.id === state.selectedId ? ' selected' : ''}`;
      button.setAttribute('aria-label', `Select capture ${index + 1}: ${capture.name}`);
      button.setAttribute('aria-pressed', String(capture.id === state.selectedId));
      const image = document.createElement('img'); image.src = capture.dataUrl; image.alt = '';
      const label = document.createElement('span'); label.textContent = `${String(index + 1).padStart(2, '0')}`;
      button.append(image, label); button.addEventListener('click', () => { state.selectedId = capture.id; syncFields(); tell(''); });
      const remove = document.createElement('button'); remove.className = 'capture-remove'; remove.textContent = '×'; remove.setAttribute('aria-label', `Remove capture ${index + 1}`);
      remove.addEventListener('click', () => {
        state.captures = state.captures.filter(value => value.id !== capture.id); decodedImages.delete(capture.id);
        if (state.selectedId === capture.id) state.selectedId = state.captures[0]?.id || null;
        syncFields(); tell('Capture removed. Save the project to keep this change.');
      });
      item.append(button, remove); return item;
    }));
    const current = selected();
    $('source-info').textContent = current ? `${current.name} · ${current.width} × ${current.height} px. Fit preserves the full capture.` : 'Use captures from the current Android app. The entire image is preserved without cropping.';
  }

  function roundRect(x, y, width, height, radius) {
    ctx.beginPath(); ctx.roundRect(x, y, width, height, radius);
  }

  function fitImage(image, x, y, width, height) {
    const scale = Math.min(width / image.width, height / image.height);
    const w = image.width * scale, h = image.height * scale;
    ctx.save();
    ctx.shadowColor = '#071f1c29'; ctx.shadowBlur = 38; ctx.shadowOffsetY = 18;
    ctx.fillStyle = state.palette.background;
    roundRect(x + (width - w) / 2, y + (height - h) / 2, w, h, 12); ctx.fill();
    ctx.restore();
    // No hardware frame, fake status bar, cropping, or rounded clipping of real UI.
    ctx.drawImage(image, x + (width - w) / 2, y + (height - h) / 2, w, h);
    return scale;
  }

  function textLines(text, maxWidth, fontSize, weight) {
    ctx.font = `${weight} ${fontSize}px system-ui, -apple-system, "Segoe UI", sans-serif`;
    const result = [];
    for (const paragraph of text.split('\n')) {
      let line = '';
      // Character-level fallback also supports unspaced CJK copy and long words.
      for (const char of Array.from(paragraph)) {
        if (line && ctx.measureText(line + char).width > maxWidth) {
          const breakAt = line.lastIndexOf(' ');
          if (breakAt > line.length / 2) { result.push(line.slice(0, breakAt)); line = line.slice(breakAt + 1) + char; }
          else { result.push(line); line = char; }
        } else line += char;
      }
      result.push(line.trim());
    }
    return result;
  }

  function drawText(text, x, y, width, maxLines, fontSize, minimumSize, weight, lineHeight, align = 'left') {
    let size = fontSize, lines;
    do { lines = textLines(text, width, size, weight); if (lines.length <= maxLines || size <= minimumSize) break; size -= 2; } while (true);
    if (lines.length > maxLines) overflow = true;
    ctx.textAlign = align; ctx.textBaseline = 'top'; ctx.fillStyle = state.palette.foreground;
    const direction = /^(ar|fa|he|ur)(-|$)/.test(state.locale) ? 'rtl' : 'ltr'; ctx.direction = direction;
    lines.slice(0, maxLines).forEach((line, i) => ctx.fillText(line, x, y + i * size * lineHeight));
    ctx.direction = 'ltr';
  }

  function placeholder(x, y, width, height) {
    ctx.save(); ctx.globalAlpha = .45; ctx.strokeStyle = state.palette.accent; ctx.lineWidth = 3; ctx.setLineDash([12, 12]); roundRect(x, y, width, height, 18); ctx.stroke(); ctx.restore();
    ctx.fillStyle = state.palette.foreground; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = `500 ${state.format === 'screenshot' ? 37 : 20}px system-ui`; ctx.fillText('Your real app capture', x + width / 2, y + height / 2 - 24);
    ctx.globalAlpha = .65; ctx.font = `${state.format === 'screenshot' ? 26 : 15}px system-ui`; ctx.fillText('Upload a PNG or JPEG to begin', x + width / 2, y + height / 2 + 28); ctx.globalAlpha = 1;
  }

  function render(withGuides = $('guides').checked) {
    const isPhone = state.format === 'screenshot';
    canvas.width = isPhone ? 1080 : 1024; canvas.height = isPhone ? 1920 : 500;
    overflow = false;
    ctx.fillStyle = state.palette.background; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.save(); ctx.globalAlpha = .07; ctx.fillStyle = state.palette.accent;
    ctx.beginPath(); ctx.arc(isPhone ? 970 : 980, isPhone ? 1450 : 430, isPhone ? 720 : 430, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    const appName = state.locales[state.locale].appName || 'Your app name';
    const headline = copy().headline || 'Tell your app’s story';
    const image = selected() && decodedImages.get(selected().id);
    if (isPhone) {
      drawText(appName, 540, 56, 890, 1, 26, 24, 600, 1.1, 'center');
      drawText(headline, 540, 123, 930, 2, 78, 50, 700, 1.09, 'center');
      if (copy().subtitle) drawText(copy().subtitle, 540, 300, 890, 1, 31, 24, 400, 1.15, 'center');
      if (image) fitImage(image, 60, 360, 960, 1500); else placeholder(230, 415, 620, 1320);
      if (withGuides) {
        ctx.save(); ctx.strokeStyle = state.palette.accent; ctx.globalAlpha = .7; ctx.setLineDash([9, 9]); ctx.lineWidth = 2; ctx.strokeRect(54, 54, 972, 1812); ctx.beginPath(); ctx.moveTo(54, 384); ctx.lineTo(1026, 384); ctx.stroke(); ctx.restore();
      }
    } else {
      drawText(appName, 82, 88, 535, 1, 20, 18, 600, 1.1);
      drawText(headline, 82, 150, 520, 3, 52, 32, 700, 1.13);
      if (copy().subtitle) drawText(copy().subtitle, 82, 346, 520, 2, 21, 16, 400, 1.25);
      if (image) fitImage(image, 646, 62, 294, 376); else placeholder(680, 74, 215, 352);
      if (withGuides) { ctx.save(); ctx.strokeStyle = state.palette.accent; ctx.setLineDash([6, 6]); ctx.lineWidth = 1; ctx.strokeRect(64, 50, 896, 400); ctx.restore(); }
    }
    updateExport();
  }

  function exportProblem() {
    if (!selected()) return 'Add a real app capture to enable export.';
    if (!state.locales[state.locale].appName.trim()) return 'Add your app name to enable export.';
    if (!copy().headline.trim()) return 'Write a headline for this language and asset.';
    if (overflow) return 'Text is too long for this layout. Shorten the headline or supporting line.';
    return '';
  }

  function updateExport() {
    const problem = exportProblem(); $('export').disabled = exporting || Boolean(problem);
    const image = selected();
    const lowResolution = image && Math.min(960 / image.width, 1500 / image.height) > 1 && state.format === 'screenshot';
    $('export-note').textContent = problem || (lowResolution ? 'This capture will be upscaled. Use a larger source for crisp app UI.' : `Ready to export ${state.locale}. Review text, app UI and content before upload.`);
  }

  const readFile = file => new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('Could not read the local file.')); reader.readAsDataURL(file); });
  const decodeImage = url => new Promise((resolve, reject) => { const image = new Image(); image.onload = () => resolve(image); image.onerror = () => reject(new Error('Could not decode this PNG or JPEG.')); image.src = url; });
  async function checkedImage(dataUrl) {
    if (typeof dataUrl !== 'string' || !/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/=]+$/.test(dataUrl) || dataUrl.length > 28 * 1024 * 1024) throw new Error('Captures must be local PNG or JPEG data, at most 20 MB each.');
    const image = await decodeImage(dataUrl);
    if (image.width > 8192 || image.height > 8192 || image.width * image.height > 40000000) throw new Error('Source captures must be at most 8192 px per side and 40 megapixels.');
    return image;
  }

  $('images').addEventListener('change', async event => {
    const files = Array.from(event.target.files); let added = 0; const errors = [];
    for (const file of files) {
      if (state.captures.length >= 8) { errors.push('Only eight captures are supported per project.'); break; }
      try {
        if (!['image/png', 'image/jpeg'].includes(file.type) || file.size > 20 * 1024 * 1024) throw new Error(`${file.name}: choose a PNG or JPEG under 20 MB.`);
        const dataUrl = await readFile(file); const image = await checkedImage(dataUrl); const id = crypto.randomUUID();
        const capture = { id, name: file.name, width: image.width, height: image.height, dataUrl, copy: {} };
        Object.keys(state.locales).forEach(code => capture.copy[code] = { ...state.locales[code].draft });
        state.captures.push(capture); decodedImages.set(id, image); if (!state.selectedId) state.selectedId = id; added++;
      } catch (error) { errors.push(error.message); }
    }
    event.target.value = ''; syncFields(); tell(errors.length ? `${added} capture(s) added. ${errors.join(' ')}` : `${added} capture(s) added. Select a capture to edit its story.`, errors.length > 0);
  });

  $('app-name').addEventListener('input', event => { state.locales[state.locale].appName = event.target.value; render(); });
  for (const [field, key] of [['headline', 'headline'], ['subtitle', 'subtitle'], ['alt-text', 'altText']]) $(field).addEventListener('input', event => { copy()[key] = event.target.value; render(); });
  $('locale').addEventListener('change', event => { state.locale = event.target.value; syncFields(); tell(''); });
  for (const key of ['background', 'accent', 'foreground']) $(key).addEventListener('input', event => { state.palette[key] = event.target.value; render(); });
  document.querySelectorAll('[data-palette]').forEach(button => button.addEventListener('click', () => { state.palette = { ...palettes[button.dataset.palette] }; syncFields(); }));
  document.querySelectorAll('[data-format]').forEach(button => button.addEventListener('click', () => { state.format = button.dataset.format; syncFields(); tell(''); }));
  $('guides').addEventListener('change', () => render());
  $('theme').addEventListener('click', () => { const dark = document.body.classList.toggle('dark'); $('theme').textContent = dark ? 'Light mode' : 'Dark mode'; });
  $('add-locale').addEventListener('click', () => { $('locale-code').value = ''; $('locale-dialog').showModal(); $('locale-code').focus(); });
  $('confirm-locale').addEventListener('click', event => {
    const code = $('locale-code').value.trim();
    if (!localePattern.test(code)) { event.preventDefault(); $('locale-code').setCustomValidity('Use a language code such as de-DE or es-ES.'); $('locale-code').reportValidity(); return; }
    if (!state.locales[code]) { state.locales[code] = emptyLocale(); state.captures.forEach(capture => capture.copy[code] = emptyCopy()); }
    state.locale = code; syncFields(); tell(`Editing ${code}. Add translated copy for every asset.`);
  });
  $('locale-code').addEventListener('input', () => $('locale-code').setCustomValidity(''));

  function download(blob, name) {
    const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = name; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
  const slug = text => text.normalize('NFKD').replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '').toLowerCase().slice(0, 60) || 'app';
  $('save-config').addEventListener('click', () => { download(new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' }), `${slug(state.locales[state.locale].appName)}-play-project.json`); tell('Project saved locally, including captures and language variants.'); });

  function validateCopy(value) {
    if (!value || typeof value !== 'object') throw new Error('Project copy is missing.');
    const result = {};
    for (const [key, limit] of [['headline', 100], ['subtitle', 110], ['altText', 140]]) {
      if (typeof value[key] !== 'string' || value[key].length > limit) throw new Error(`Invalid or oversized ${key} in the project.`);
      result[key] = value[key];
    }
    return result;
  }
  async function validateProject(input) {
    if (!input || input.version !== 1 || !['screenshot', 'feature-graphic'].includes(input.format)) throw new Error('Unsupported project format. Expected version 1.');
    if (!input.locales || typeof input.locales !== 'object' || Array.isArray(input.locales) || !Object.keys(input.locales).length || Object.keys(input.locales).length > 50) throw new Error('Project needs 1–50 language variants.');
    const locales = Object.create(null);
    for (const [code, value] of Object.entries(input.locales)) {
      if (!localePattern.test(code) || !value || typeof value.appName !== 'string' || value.appName.length > 30) throw new Error('Invalid language or app name in the project.');
      locales[code] = { appName: value.appName, draft: validateCopy(value.draft), feature: validateCopy(value.feature) };
    }
    if (!Object.hasOwn(locales, input.locale)) throw new Error('Selected language is missing.');
    const palette = {};
    for (const key of ['background', 'accent', 'foreground']) { if (!/^#[0-9a-f]{6}$/i.test(input.palette?.[key])) throw new Error('Project colors must use six-digit hex values.'); palette[key] = input.palette[key]; }
    if (!Array.isArray(input.captures) || input.captures.length > 8) throw new Error('Project supports up to eight captures.');
    const captures = [], images = new Map();
    for (const item of input.captures) {
      if (!item || typeof item.id !== 'string' || item.id.length > 100 || images.has(item.id) || typeof item.name !== 'string' || item.name.length > 300) throw new Error('Invalid or duplicate capture in the project.');
      const image = await checkedImage(item.dataUrl), translations = Object.create(null);
      for (const code of Object.keys(locales)) translations[code] = validateCopy(item.copy?.[code]);
      captures.push({ id: item.id, name: item.name, dataUrl: item.dataUrl, width: image.width, height: image.height, copy: translations }); images.set(item.id, image);
    }
    return { state: { version: 1, locale: input.locale, format: input.format, selectedId: captures.some(item => item.id === input.selectedId) ? input.selectedId : captures[0]?.id || null, palette, locales, captures }, images };
  }
  $('load-config').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file) return;
    try {
      if (file.size > 225 * 1024 * 1024) throw new Error('Project is too large. Maximum size is 225 MB.');
      const result = await validateProject(JSON.parse(await file.text())); state = result.state; decodedImages.clear(); result.images.forEach((image, id) => decodedImages.set(id, image)); syncFields(); tell('Project opened. Captures and language variants restored.');
    } catch (error) { tell(`Could not open project: ${error.message}`, true); }
    event.target.value = '';
  });

  // Canvas.toBlob may produce 32-bit RGBA PNGs. Encode explicitly as 24-bit RGB.
  const crcTable = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  function crc32(bytes) { let crc = 0xffffffff; for (const byte of bytes) crc = crcTable[(crc ^ byte) & 255] ^ (crc >>> 8); return (crc ^ 0xffffffff) >>> 0; }
  function chunk(type, data) {
    const result = new Uint8Array(data.length + 12), view = new DataView(result.buffer); view.setUint32(0, data.length);
    result.set(new TextEncoder().encode(type), 4); result.set(data, 8); view.setUint32(data.length + 8, crc32(result.subarray(4, data.length + 8))); return result;
  }
  function storedDeflate(bytes) {
    const count = Math.ceil(bytes.length / 65535), result = new Uint8Array(bytes.length + count * 5 + 6); let offset = 2; result[0] = 0x78; result[1] = 0x01;
    for (let start = 0; start < bytes.length; start += 65535) {
      const size = Math.min(65535, bytes.length - start), last = start + size === bytes.length; result[offset++] = last ? 1 : 0;
      result[offset++] = size & 255; result[offset++] = size >>> 8; result[offset++] = (~size) & 255; result[offset++] = ((~size) >>> 8) & 255;
      result.set(bytes.subarray(start, start + size), offset); offset += size;
    }
    let a = 1, b = 0; for (const byte of bytes) { a = (a + byte) % 65521; b = (b + a) % 65521; }
    new DataView(result.buffer).setUint32(offset, ((b << 16) | a) >>> 0); return result;
  }
  async function rgbPNG() {
    const { width, height } = canvas, pixels = ctx.getImageData(0, 0, width, height).data, row = width * 3 + 1, raw = new Uint8Array(row * height);
    for (let y = 0; y < height; y++) { let target = y * row + 1, source = y * width * 4; for (let x = 0; x < width; x++) { raw[target++] = pixels[source++]; raw[target++] = pixels[source++]; raw[target++] = pixels[source++]; source++; } }
    let packed;
    if (typeof CompressionStream === 'function') { const stream = new Blob([raw]).stream().pipeThrough(new CompressionStream('deflate')); packed = new Uint8Array(await new Response(stream).arrayBuffer()); }
    else packed = storedDeflate(raw);
    const ihdr = new Uint8Array(13), view = new DataView(ihdr.buffer); view.setUint32(0, width); view.setUint32(4, height); ihdr[8] = 8; ihdr[9] = 2;
    return new Blob([new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ihdr), chunk('IDAT', packed), chunk('IEND', new Uint8Array())], { type: 'image/png' });
  }
  $('export').addEventListener('click', async () => {
    if (exportProblem() || exporting) return;
    exporting = true; updateExport(); tell('Rendering RGB PNG…');
    try {
      render(false);
      const index = state.captures.findIndex(item => item.id === state.selectedId) + 1;
      const name = `${slug(state.locales[state.locale].appName)}-${state.locale}-${state.format === 'screenshot' ? `phone-${String(index).padStart(2, '0')}` : 'feature-graphic'}.png`;
      const blob = await rgbPNG();
      download(blob, name); tell(`${name} saved · ${(blob.size / 1024 / 1024).toFixed(2)} MB. Composition guides are excluded.`);
    } catch (error) { tell(`Export failed: ${error.message}`, true); }
    finally { exporting = false; render(); }
  });
  syncFields();
})();
