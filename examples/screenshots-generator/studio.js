'use strict';

(() => {
  const E = window.PlayStudio, $ = id => document.getElementById(id), canvas = $('preview');
  const palettes = {
    mint: { background: '#e5f6ef', accent: '#3a9475', foreground: '#12382a' },
    ink: { background: '#172e32', accent: '#66cca6', foreground: '#edfaf4' },
    apricot: { background: '#fff0df', accent: '#d98253', foreground: '#562e24' }
  };
  let state = E.emptyProject(), images = new Map(), busy = false, problem = '';
  const selected = () => state.captures.find(c => c.id === state.selectedId);
  const currentCopy = () => state.format === 'feature-graphic' ? state.locales[state.locale].feature : selected()?.copy[state.locale] || state.locales[state.locale].draft;
  const tell = (message, error = false) => { $('status').textContent = message; $('status').classList.toggle('error', error); };
  const decoder = url => new Promise((resolve, reject) => { const image = new Image(); image.onload = () => resolve(image); image.onerror = () => reject(new Error('Could not decode the PNG/JPEG source.')); image.src = url; });
  const readFile = file => new Promise((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.onerror = () => reject(new Error('Could not read local file.')); r.readAsDataURL(file); });
  const clone = () => JSON.parse(JSON.stringify(state));
  function setBusy(value) { busy = value; document.querySelector('main').inert = value; $('export').disabled = value || !!problem; $('export-batch').disabled = value || !state.captures.length; }
  async function installProject(input) { const result = await E.validateProject(input, decoder); state = result.project; images = result.images; syncFields(); return state; }
  function options() { return { ...E.presets, ...state.customProfiles }; }
  function currentJob() { return { locale: state.locale, profileId: state.format === 'feature-graphic' ? 'feature-graphic' : state.profileId, captureId: state.selectedId, kind: state.format, order: selected() ? state.captures.filter(c => c.device === selected().device).findIndex(c => c.id === state.selectedId) + 1 : 0 }; }
  function checkboxList(id, values, selection, change) {
    $(id).replaceChildren(...values.map(value => {
      const label = document.createElement('label'); label.className = 'check';
      const box = document.createElement('input'); box.type = 'checkbox'; box.checked = selection.includes(value); box.addEventListener('change', () => change(value, box.checked));
      label.append(box, document.createTextNode(value)); return label;
    }));
  }
  function toggle(field, value, enabled) { state[field] = enabled ? [...new Set([...state[field], value])] : state[field].filter(v => v !== value); }
  function syncFields() {
    $('locale').replaceChildren(...Object.keys(state.locales).map(code => { const o = document.createElement('option'); o.value = code; o.textContent = code; return o; }));
    $('locale').value = state.locale;
    $('app-name').value = state.locales[state.locale].appName;
    $('headline').value = currentCopy().headline; $('subtitle').value = currentCopy().subtitle; $('alt-text').value = currentCopy().altText;
    $('headline-scope').textContent = state.format === 'screenshot' ? 'for this capture' : 'for the feature graphic';
    for (const key of ['background', 'accent', 'foreground']) $(key).value = state.palette[key];
    for (const button of document.querySelectorAll('[data-format]')) { const active = button.dataset.format === state.format; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); }
    $('profile').replaceChildren(...Object.entries(options()).map(([id, p]) => { const o = document.createElement('option'); o.value = id; o.textContent = `${id} · ${p.width}×${p.height}`; return o; }));
    $('profile').value = state.profileId; $('profile').disabled = state.format === 'feature-graphic';
    const p = { ...E.profile(state, state.format === 'feature-graphic' ? 'feature-graphic' : state.profileId), ...(state.format === 'screenshot' ? selected()?.layouts?.[state.profileId] || {} : {}) };
    $('layout').value = p.layout; $('text-ratio').value = Math.round(p.textRatio * 100); $('image-scale').value = Math.round(p.imageScale * 100);
    $('text-ratio-value').textContent = `${Math.round(p.textRatio * 100)}%`; $('image-scale-value').textContent = `${Math.round(p.imageScale * 100)}%`;
    $('custom-width').value = E.profile(state).width; $('custom-height').value = E.profile(state).height;
    checkboxList('batch-locales', Object.keys(state.locales), state.exportLocales, (code, on) => toggle('exportLocales', code, on));
    checkboxList('batch-presets', Object.keys(options()), state.exportPresets, (id, on) => toggle('exportPresets', id, on));
    $('batch-feature').checked = state.exportFeature;
    renderCaptures(); render();
  }
  function renderCaptures() {
    $('capture-count').textContent = `${state.captures.length} / 24`;
    $('capture-list').replaceChildren(...state.captures.map((capture, index) => {
      const item = document.createElement('div'); item.className = 'capture-item';
      const button = document.createElement('button'); button.className = `capture-select${capture.id === state.selectedId ? ' selected' : ''}`;
      button.setAttribute('aria-label', `Select capture ${index + 1}: ${capture.name}`); button.setAttribute('aria-pressed', String(capture.id === state.selectedId));
      const image = document.createElement('img'); image.src = E.sourceFor(capture, state.locale).source.dataUrl; image.alt = '';
      const label = document.createElement('span'); label.textContent = `${index + 1} · ${capture.device}`; button.append(image, label);
      button.addEventListener('click', () => { state.selectedId = capture.id; if (state.format === 'feature-graphic') state.featureCaptureId = capture.id; else if (E.profile(state).device !== capture.device) state.profileId = Object.keys(options()).find(id => options()[id].device === capture.device); syncFields(); tell(''); });
      const actions = document.createElement('div'); actions.className = 'capture-actions';
      for (const [text, direction] of [['↑', -1], ['↓', 1]]) {
        const move = document.createElement('button'); move.textContent = text; move.setAttribute('aria-label', `Move capture ${index + 1} ${direction < 0 ? 'earlier' : 'later'}`);
        let other = index + direction; while (other >= 0 && other < state.captures.length && state.captures[other].device !== capture.device) other += direction;
        move.disabled = other < 0 || other >= state.captures.length;
        move.addEventListener('click', () => { [state.captures[index], state.captures[other]] = [state.captures[other], state.captures[index]]; syncFields(); tell('Order updated. Save the project to preserve it.'); }); actions.append(move);
      }
      const remove = document.createElement('button'); remove.textContent = '×'; remove.setAttribute('aria-label', `Remove capture ${index + 1}`);
      remove.addEventListener('click', () => { state.captures = state.captures.filter(c => c.id !== capture.id); for (const key of [...images.keys()]) if (key.startsWith(`${capture.id}:`)) images.delete(key); if (state.selectedId === capture.id) state.selectedId = state.captures[0]?.id || null; if (state.featureCaptureId === capture.id) state.featureCaptureId = state.selectedId; syncFields(); });
      actions.append(remove); item.append(button, actions); return item;
    }));
    const c = selected(), source = c && E.sourceFor(c, state.locale);
    $('source-info').textContent = c ? `${source.source.name} · ${source.source.width}×${source.source.height} · ${c.device} · ${source.fallback ? 'default UI source: verify language' : `${state.locale} UI override`}. Full capture preserved.` : 'Use real captures from the current Android app.';
    $('clear-locale-source').disabled = !c?.sources?.[state.locale]; $('locale-image').disabled = !c;
    $('feature-source').textContent = state.captures.find(item => item.id === state.featureCaptureId)?.name || 'No feature capture selected. Select a capture in Feature graphic mode.';
  }
  function render() {
    problem = '';
    const p = E.profile(state, state.format === 'feature-graphic' ? 'feature-graphic' : state.profileId);
    $('preview-title').textContent = state.format === 'feature-graphic' ? 'Feature graphic' : `${p.device} screenshot`;
    $('size-label').textContent = `${p.width} × ${p.height} · ${p.layout}`; canvas.classList.toggle('feature', p.width > p.height);
    if (!selected()) {
      canvas.width = p.width; canvas.height = p.height; const ctx = canvas.getContext('2d'); ctx.fillStyle = state.palette.background; ctx.fillRect(0, 0, p.width, p.height); ctx.fillStyle = state.palette.foreground; ctx.font = `${Math.min(p.width, p.height) * .04}px system-ui`; ctx.textAlign = 'center'; ctx.fillText('Upload your real Android capture', p.width / 2, p.height / 2); problem = 'Add a real capture to enable export.';
    } else {
      try { E.render(canvas, state, images, currentJob(), $('guides').checked, true); const offscreen = document.createElement('canvas'); E.render(offscreen, state, images, currentJob()); } catch (error) { problem = error.message; }
    }
    $('export-note').textContent = problem || 'Ready. Review source UI, language, alt text and device coverage before upload.';
    $('export').disabled = busy || !!problem; $('export-batch').disabled = busy || !state.captures.length;
  }
  async function sourceFromFile(file) {
    if (!['image/png', 'image/jpeg'].includes(file.type) || file.size > 20 * 1024 * 1024) throw new Error('Choose a PNG/JPEG up to 20 MB.');
    return { name: file.name, dataUrl: await readFile(file) };
  }
  $('images').addEventListener('change', async event => {
    const files = [...event.target.files]; if (!files.length) return; setBusy(true);
    try { const candidate = clone(), device = $('upload-device').value; for (const file of files) { const source = await sourceFromFile(file), translations = {}; for (const code of Object.keys(candidate.locales)) translations[code] = { ...candidate.locales[code].draft }; const id = crypto.randomUUID(); candidate.captures.push({ id, device, ...source, sources: {}, copy: translations }); candidate.selectedId ||= id; candidate.featureCaptureId ||= id; } await installProject(candidate); tell(`${files.length} real capture(s) added.`); } catch (error) { tell(`Upload failed; project unchanged: ${error.message}`, true); } finally { event.target.value = ''; setBusy(false); }
  });
  $('locale-image').addEventListener('change', async event => {
    const file = event.target.files[0]; if (!file || !selected()) return; setBusy(true);
    try { const candidate = clone(); candidate.captures.find(c => c.id === candidate.selectedId).sources[candidate.locale] = await sourceFromFile(file); await installProject(candidate); tell(`Localized UI source saved for ${state.locale}.`); } catch (error) { tell(`Override failed; project unchanged: ${error.message}`, true); } finally { event.target.value = ''; setBusy(false); }
  });
  $('clear-locale-source').addEventListener('click', async () => { const candidate = clone(); delete candidate.captures.find(c => c.id === candidate.selectedId).sources[candidate.locale]; await installProject(candidate); tell('Localized override cleared. Default source is used.'); });
  $('app-name').addEventListener('input', e => { state.locales[state.locale].appName = e.target.value; render(); });
  for (const [field, key] of [['headline', 'headline'], ['subtitle', 'subtitle'], ['alt-text', 'altText']]) $(field).addEventListener('input', e => { currentCopy()[key] = e.target.value; render(); });
  $('locale').addEventListener('change', e => { state.locale = e.target.value; syncFields(); tell(''); });
  for (const key of ['background', 'accent', 'foreground']) $(key).addEventListener('input', e => { state.palette[key] = e.target.value; render(); });
  for (const button of document.querySelectorAll('[data-palette]')) button.addEventListener('click', () => { state.palette = { ...palettes[button.dataset.palette] }; syncFields(); });
  for (const button of document.querySelectorAll('[data-format]')) button.addEventListener('click', () => { state.format = button.dataset.format; if (state.format === 'feature-graphic') state.selectedId = state.featureCaptureId; syncFields(); });
  $('profile').addEventListener('change', e => { state.profileId = e.target.value; const device = E.profile(state).device; if (selected()?.device !== device) state.selectedId = state.captures.find(c => c.device === device)?.id || null; syncFields(); });
  for (const id of ['layout', 'text-ratio', 'image-scale']) $(id).addEventListener('input', () => { const key = state.format === 'feature-graphic' ? 'feature-graphic' : state.profileId, config = { layout: $('layout').value, textRatio: Number($('text-ratio').value) / 100, imageScale: Number($('image-scale').value) / 100 }; if (state.format === 'screenshot' && selected() && $('layout-scope').value === 'capture') { selected().layouts ||= {}; selected().layouts[key] = config; } else state.profileOptions[key] = config; $('text-ratio-value').textContent = `${$('text-ratio').value}%`; $('image-scale-value').textContent = `${$('image-scale').value}%`; render(); });
  $('apply-custom').addEventListener('click', () => { try { const base = E.profile(state), id = `custom-${base.device}`, config = E.checkedProfile({ ...base, width: Number($('custom-width').value), height: Number($('custom-height').value) }); state.customProfiles[id] = config; state.profileId = id; if (!state.exportPresets.includes(id)) state.exportPresets.push(id); syncFields(); tell('Custom dimensions added to export profiles.'); } catch (error) { tell(error.message, true); } });
  $('guides').addEventListener('change', render);
  $('batch-feature').addEventListener('change', e => { state.exportFeature = e.target.checked; });
  $('all-locales').addEventListener('click', () => { state.exportLocales = Object.keys(state.locales); syncFields(); });
  $('theme').addEventListener('click', () => { const dark = document.body.classList.toggle('dark'); $('theme').textContent = dark ? 'Light mode' : 'Dark mode'; });
  $('add-locale').addEventListener('click', () => { $('locale-code').value = ''; $('locale-dialog').showModal(); });
  $('confirm-locale').addEventListener('click', e => { const code = $('locale-code').value.trim(); if (!/^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/.test(code) || Object.keys(state.locales).length >= 50) { e.preventDefault(); tell('Use a language tag; maximum 50 languages.', true); return; } if (!state.locales[code]) { state.locales[code] = E.emptyLocale(); for (const c of state.captures) c.copy[code] = E.emptyCopy(); } state.locale = code; if (!state.exportLocales.includes(code)) state.exportLocales.push(code); syncFields(); tell(`Add ${code} copy and, where needed, a localized UI source.`); });
  function download(blob, name) { const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = name; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000); }
  $('save-config').addEventListener('click', () => { download(new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' }), `${E.slug(state.locales[state.locale].appName)}-play-project.json`); tell('Version 2 project saved: captures, source overrides, order, layouts and export selection.'); });
  $('load-config').addEventListener('change', async e => { const file = e.target.files[0]; if (!file) return; setBusy(true); try { if (file.size > E.MAX_PROJECT_BYTES) throw new Error('Project exceeds 225 MB.'); await installProject(JSON.parse(await file.text())); tell('Project opened. Version 1 projects migrate to version 2.'); } catch (error) { tell(`Could not open project; current session unchanged: ${error.message}`, true); } finally { e.target.value = ''; setBusy(false); } });
  $('export').addEventListener('click', async () => { if (problem || busy) return; setBusy(true); try { const output = document.createElement('canvas'), job = currentJob(); E.render(output, state, images, job); download(await E.rgbPNG(output), `${E.slug(state.locales[state.locale].appName)}-${state.locale}-${job.profileId}-${String(job.order).padStart(2, '0')}.png`); tell('RGB PNG saved. Use ZIP export for manifest and alt text.'); } catch (error) { tell(`Export failed: ${error.message}`, true); } finally { setBusy(false); } });
  $('export-batch').addEventListener('click', async () => {
    if (busy) return; setBusy(true);
    try {
      const batch = E.jobs(state), output = document.createElement('canvas'), assets = [], entries = []; let size = 0;
      // Preflight every job before encoding/downloading any file.
      for (const job of batch) E.render(output, state, images, job);
      for (const [index, job] of batch.entries()) { tell(`Rendering ${index + 1} / ${batch.length}: ${job.locale} · ${job.profileId}`); const asset = E.render(output, state, images, job); const data = new Uint8Array(await (await E.rgbPNG(output)).arrayBuffer()); size += data.length; if (size > 256 * 1024 * 1024) throw new Error('ZIP exceeds 256 MB. Select fewer languages/profiles.'); entries.push({ name: job.file, data }); assets.push(asset); }
      const manifest = { version: 1, project_version: 2, assets, note: 'Technical rendering only. Confirm visual quality, real UI language, counts and Console coverage.' };
      entries.push({ name: 'assets-manifest.json', data: new TextEncoder().encode(JSON.stringify(manifest, null, 2)) }, { name: 'assets-manifest.csv', data: new TextEncoder().encode(E.manifestCSV(assets)) });
      download(E.zip(entries), `${E.slug(state.locales[state.locale].appName)}-play-assets.zip`); tell(`${assets.length} RGB PNGs + JSON/CSV manifests saved. No uploads performed.`);
    } catch (error) { tell(`Batch failed; no archive downloaded: ${error.message}`, true); } finally { setBusy(false); }
  });
  window.PlayStudioEditor = {
    loadProject: installProject,
    getProject: () => clone(),
    exportJobs: options => E.jobs(state, options),
    preflightJobs: batch => { const output = document.createElement('canvas'); for (const job of batch) E.render(output, state, images, job); },
    exportJob: async job => { const output = document.createElement('canvas'), asset = E.render(output, state, images, job), bytes = new Uint8Array(await (await E.rgbPNG(output)).arrayBuffer()); let binary = ''; for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768)); return { asset, base64: btoa(binary) }; }
  };
  syncFields();
})();
