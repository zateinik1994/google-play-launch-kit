'use strict';
// Synthetic capture fixtures test rendering; they are not production store assets.
const test = require('node:test'), assert = require('node:assert/strict'), fs = require('node:fs/promises'), os = require('node:os'), path = require('node:path'), http = require('node:http'), zlib = require('node:zlib'), { spawn } = require('node:child_process');
const { chromium } = require('playwright'), E = require('../engine.js');
const root = path.resolve(__dirname, '..');
function png(width, height, color) {
  function chunk(type, payload) { const t = Buffer.from(type), out = Buffer.alloc(payload.length + 12); out.writeUInt32BE(payload.length); t.copy(out, 4); payload.copy(out, 8); out.writeUInt32BE(E.crc32(Buffer.concat([t, payload])), payload.length + 8); return out; }
  const header = Buffer.alloc(13); header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 2;
  const raw = Buffer.alloc((width * 3 + 1) * height); for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) for (let c = 0; c < 3; c++) raw[y * (width * 3 + 1) + 1 + x * 3 + c] = color[c];
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR', header), chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
function unzip(bytes) {
  const entries = new Map(); let offset = 0;
  while (bytes.readUInt32LE(offset) === 0x04034b50) { const size = bytes.readUInt32LE(offset + 18), nameLength = bytes.readUInt16LE(offset + 26), extra = bytes.readUInt16LE(offset + 28), name = bytes.subarray(offset + 30, offset + 30 + nameLength).toString('utf8'), start = offset + 30 + nameLength + extra, data = bytes.subarray(start, start + size); assert.equal(bytes.readUInt16LE(offset + 8), 0); assert.equal(E.crc32(data), bytes.readUInt32LE(offset + 14)); entries.set(name, data); offset = start + size; }
  assert.equal(bytes.readUInt32LE(offset), 0x02014b50); return entries;
}
function pngPixels(bytes) { let offset = 8; const chunks = []; while (offset < bytes.length) { const n = bytes.readUInt32BE(offset), type = bytes.toString('ascii', offset + 4, offset + 8); if (type === 'IDAT') chunks.push(bytes.subarray(offset + 8, offset + 8 + n)); offset += n + 12; } return zlib.inflateSync(Buffer.concat(chunks)); }
function command(argv) { return new Promise(resolve => { const child = spawn(process.execPath, [path.join(root, 'export.cjs'), ...argv], { env: process.env }); let stdout = '', stderr = ''; child.stdout.on('data', b => stdout += b); child.stderr.on('data', b => stderr += b); child.on('close', code => resolve({ code, stdout, stderr })); }); }

test('browser upload/edit/reorder/localized UI/RTL/ZIP and saved project headless exports agree', { timeout: 120000 }, async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'playstudio-integration-'));
  const allowed = new Set(['index.html', 'engine.js', 'studio.js', 'studio.css']);
  const server = http.createServer(async (req, res) => { const name = req.url === '/' ? 'index.html' : req.url.slice(1); if (!allowed.has(name)) { res.writeHead(404); res.end(); return; } res.writeHead(200, { 'Content-Type': name.endsWith('.js') ? 'text/javascript' : name.endsWith('.css') ? 'text/css' : 'text/html' }); res.end(await fs.readFile(path.join(root, name))); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const executablePath = process.env.PLAYSTUDIO_BROWSER_EXECUTABLE;
  let browser;
  try {
    browser = await chromium.launch({ headless: true, ...(executablePath ? { executablePath } : {}) });
    const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1050 } }), page = await context.newPage(), pageErrors = [], external = [];
    page.on('pageerror', error => pageErrors.push(error.message)); page.on('request', req => { if (!req.url().startsWith('http://127.0.0.1:')) external.push(req.url()); });
    await page.goto(`http://127.0.0.1:${server.address().port}`); await page.waitForFunction(() => !!window.PlayStudioEditor);
    const red = png(320, 640, [210, 40, 40]), green = png(320, 640, [40, 190, 60]), blue = png(720, 1280, [30, 90, 210]);
    await page.locator('#images').setInputFiles([{ name: 'one.png', mimeType: 'image/png', buffer: red }, { name: 'two.png', mimeType: 'image/png', buffer: red }]);
    await page.waitForFunction(() => window.PlayStudioEditor.getProject().captures.length === 2);
    await page.locator('#app-name').fill('Fixture'); await page.locator('#headline').fill('One clear screen'); await page.locator('#alt-text').fill('First screen');
    await page.locator('#image-scale').press('Home');
    assert.equal(await page.evaluate(() => window.PlayStudioEditor.getProject().captures[0].layouts['phone-portrait'].imageScale), .5);
    await page.locator('summary').filter({ hasText: 'Custom screenshot size' }).click(); await page.locator('#custom-width').fill('640'); await page.locator('#custom-height').fill('1280'); await page.locator('#apply-custom').click();
    assert.equal(await page.evaluate(() => window.PlayStudioEditor.getProject().customProfiles['custom-phone'].height), 1280);
    await page.locator('#batch-presets label').filter({ hasText: /^custom-phone$/ }).locator('input').uncheck(); await page.locator('#profile').selectOption('phone-portrait');
    await page.getByRole('button', { name: 'Select capture 2: two.png', exact: true }).click(); await page.locator('#headline').fill('Another clear screen'); await page.locator('#alt-text').fill('Second screen');
    await page.getByRole('button', { name: 'Move capture 2 earlier', exact: true }).click();
    assert.deepEqual(await page.evaluate(() => window.PlayStudioEditor.getProject().captures.map(c => c.name)), ['two.png', 'one.png']);
    await page.getByRole('button', { name: '+ Language', exact: true }).click(); await page.locator('#locale-code').fill('ar'); await page.locator('#confirm-locale').click();
    await page.locator('#app-name').fill('تجربة'); await page.locator('#headline').fill('شاشة واضحة'); await page.locator('#alt-text').fill('الشاشة الأولى');
    await page.locator('#locale-image').setInputFiles({ name: 'arabic-ui.png', mimeType: 'image/png', buffer: green });
    await page.waitForFunction(() => window.PlayStudioEditor.getProject().captures.some(c => c.sources.ar));
    await page.getByRole('button', { name: 'Select capture 2: one.png', exact: true }).click(); await page.locator('#headline').fill('نتيجة واضحة'); await page.locator('#alt-text').fill('الشاشة الثانية');
    await page.locator('[data-format="feature-graphic"]').click(); await page.locator('#headline').fill('تجربة واضحة'); await page.locator('#alt-text').fill('واجهة التطبيق');
    await page.locator('#locale').selectOption('en-US'); await page.locator('#headline').fill('A clear experience'); await page.locator('#alt-text').fill('App interface');
    await page.locator('[data-format="screenshot"]').click(); await page.locator('#upload-device').selectOption('tablet-7'); await page.locator('#images').setInputFiles({ name: 'tablet.png', mimeType: 'image/png', buffer: blue });
    await page.waitForFunction(() => window.PlayStudioEditor.getProject().captures.length === 3);
    await page.locator('#batch-presets label').filter({ hasText: /^phone-landscape$/ }).locator('input').check(); await page.locator('#batch-presets label').filter({ hasText: /^tablet-7-portrait$/ }).locator('input').check();
    const project = await page.evaluate(() => window.PlayStudioEditor.getProject());
    const id = project.captures.find(c => c.name === 'two.png').id;
    const rtl = await page.evaluate(job => window.PlayStudioEditor.exportJob(job).then(r => r.asset), { locale: 'ar', profileId: 'phone-landscape', captureId: id, kind: 'screenshot', order: 2 });
    const ltr = await page.evaluate(job => window.PlayStudioEditor.exportJob(job).then(r => r.asset), { locale: 'en-US', profileId: 'phone-landscape', captureId: id, kind: 'screenshot', order: 2 });
    assert.equal(rtl.rtl, true); assert.equal(rtl.source_name, 'arabic-ui.png'); assert.equal(rtl.source_fallback, false); assert.ok(rtl.image_bounds.x < ltr.image_bounds.x);
    const bad = { ...project, captures: project.captures.map((c, i) => i ? c : { ...c, dataUrl: 'https://example.com/source.png' }) };
    await page.locator('#load-config').setInputFiles({ name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(bad)) });
    await page.waitForFunction(() => document.querySelector('#status').textContent.includes('unchanged'));
    assert.deepEqual(await page.evaluate(() => window.PlayStudioEditor.getProject()), project);
    const downloadPromise = page.waitForEvent('download'); await page.locator('#export-batch').click(); const download = await downloadPromise; const zipFile = path.join(directory, 'browser.zip'); await download.saveAs(zipFile);
    const entries = unzip(await fs.readFile(zipFile)), manifest = JSON.parse(entries.get('assets-manifest.json'));
    assert.equal(manifest.assets.length, 12); assert.equal(entries.size, 14);
    for (const asset of manifest.assets) { const bytes = entries.get(asset.file); assert.equal(bytes[24], 8); assert.equal(bytes[25], 2); assert.equal(bytes.readUInt32BE(16), asset.width); assert.equal(bytes.readUInt32BE(20), asset.height); }
    assert.equal(manifest.assets.find(a => a.locale === 'ar' && a.captureId === id && a.profileId === 'phone-portrait').source_name, 'arabic-ui.png');
    const savePromise = page.waitForEvent('download'); await page.locator('#save-config').click(); const saved = await savePromise, projectFile = path.join(directory, 'project.json'); await saved.saveAs(projectFile);
    await page.locator('#load-config').setInputFiles(projectFile); await page.waitForFunction(() => document.querySelector('#status').textContent.startsWith('Project opened'));
    assert.deepEqual(await page.evaluate(() => window.PlayStudioEditor.getProject()), project);
    await page.screenshot({ path: path.join(directory, 'desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 }); await page.screenshot({ path: path.join(directory, 'mobile.png'), fullPage: true });
    const output = path.join(directory, 'cli-assets'), browserArgs = executablePath ? ['--browser-executable', executablePath] : [], cli = await command(['--project', projectFile, '--output', output, '--zip', ...browserArgs]);
    assert.equal(cli.code, 0, cli.stderr); const cliManifest = JSON.parse(await fs.readFile(path.join(output, 'assets-manifest.json')));
    assert.deepEqual(cliManifest.assets, manifest.assets);
    for (const asset of manifest.assets) {
      const a = pngPixels(await fs.readFile(path.join(output, asset.file))), b = pngPixels(entries.get(asset.file)); assert.equal(a.length, b.length);
      let differences = 0; for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) differences++;
      // Text antialiasing can differ between browser processes; source/UI pixels
      // and dimensions must agree. A substantial renderer mismatch fails.
      assert.ok(differences / a.length < .002, `${asset.file}: ${differences / a.length} differing channels`);
    }
    const repeat = await command(['--project', projectFile, '--output', output, ...browserArgs]); assert.equal(repeat.code, 1); assert.match(repeat.stderr, /already exists/);
    const badFile = path.join(directory, 'invalid.json'), missingOutput = path.join(directory, 'invalid-output'); await fs.writeFile(badFile, JSON.stringify(bad));
    const invalid = await command(['--project', badFile, '--output', missingOutput, ...browserArgs]); assert.equal(invalid.code, 1); await assert.rejects(fs.stat(missingOutput), { code: 'ENOENT' });
    assert.deepEqual(pageErrors, []); assert.deepEqual(external, []);
    console.log(`Browser QA artifacts: ${directory}`);
  } finally { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); }
});
