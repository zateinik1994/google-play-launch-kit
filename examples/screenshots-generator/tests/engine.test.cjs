'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const E = require('../engine.js'), { parse } = require('../export.cjs');
const header = Buffer.alloc(29); Buffer.from([137,80,78,71,13,10,26,10]).copy(header); header.writeUInt32BE(13, 8); header.write('IHDR', 12); header.writeUInt32BE(320, 16); header.writeUInt32BE(640, 20);
// Header-only unit fixture; browser integration uses complete, decodable PNGs.
const source = { name: 'source.png', dataUrl: `data:image/png;base64,${header.toString('base64')}` };
const decode = async () => ({ width: 320, height: 640 });
function fixture() {
  const p = E.emptyProject(); p.locales['en-US'].appName = 'Fixture'; p.locales['en-US'].feature.headline = 'Real capture';
  p.captures = ['second', 'first'].map(id => ({ id, device: 'phone', ...source, sources: {}, copy: { 'en-US': { headline: id, subtitle: '', altText: `Screen ${id}` }, 'ru-RU': E.emptyCopy() } }));
  p.selectedId = 'second'; p.featureCaptureId = 'first'; return p;
}
test('v1 migration preserves captures, copy and order; sets phone device and explicit selection', async () => {
  const p = fixture(); p.version = 1; for (const c of p.captures) { delete c.device; delete c.sources; }
  const { project, images } = await E.validateProject(p, decode);
  assert.equal(project.version, 2); assert.deepEqual(project.captures.map(c => c.id), ['second', 'first']);
  assert.equal(project.captures[0].device, 'phone'); assert.equal(project.captures[0].width, 320); assert.equal(images.size, 2);
  assert.deepEqual(project.exportLocales, ['en-US']); assert.equal(project.captures[0].copy['en-US'].altText, 'Screen second');
});
test('v2 round trip preserves custom layout, source overrides and device order', async () => {
  const p = fixture(); p.captures[0].sources['ru-RU'] = { ...source, name: 'localized.png' };
  p.customProfiles['custom-phone'] = { device: 'phone', width: 640, height: 1280, layout: 'split', textRatio: .4, imageScale: .8 };
  p.profileId = 'custom-phone'; p.exportPresets = ['custom-phone', 'phone-landscape']; p.exportLocales = ['en-US', 'ru-RU'];
  const first = await E.validateProject(p, decode), second = await E.validateProject(JSON.parse(JSON.stringify(first.project)), decode);
  assert.deepEqual(second.project, first.project); assert.equal(E.sourceFor(second.project.captures[0], 'ru-RU').fallback, false);
  assert.equal(E.sourceFor(second.project.captures[1], 'ru-RU').fallback, true);
});
test('per-capture layouts survive save and reject device/profile mismatch', async () => {
  const p = fixture(); p.captures[0].layouts = { 'phone-portrait': { layout: 'split', textRatio: .4, imageScale: .75 } };
  const { project } = await E.validateProject(p, decode); assert.equal(project.captures[0].layouts['phone-portrait'].imageScale, .75);
  p.captures[0].layouts['tablet-7-portrait'] = { layout: 'ui-only', textRatio: .18, imageScale: 1 };
  await assert.rejects(E.validateProject(p, decode), /mismatch/);
});
test('malformed import rejects remote image and leaves supplied project unchanged', async () => {
  const p = fixture(); p.captures[1].dataUrl = 'https://example.com/a.png'; const original = JSON.stringify(p);
  await assert.rejects(E.validateProject(p, decode), /local PNG/); assert.equal(JSON.stringify(p), original);
});
test('input and device limits enforce eight captures and decoded source limits', async () => {
  const p = fixture(); p.captures = Array.from({ length: 9 }, (_, i) => ({ ...p.captures[0], id: String(i) }));
  await assert.rejects(E.validateProject(p, decode), /eight captures/);
  await assert.rejects(E.validateProject(fixture(), async () => ({ width: 8193, height: 640 })), /8192/);
  const huge = fixture(); huge.captures = Array.from({ length: 4 }, (_, i) => ({ ...huge.captures[0], id: String(i) }));
  await assert.rejects(E.validateProject(huge, async () => ({ width: 6000, height: 6000 })), /120 megapixels/);
});
test('oversized header fails before native browser decode', async () => {
  const p = fixture(), huge = Buffer.from(header); huge.writeUInt32BE(100000, 16); p.captures[0].dataUrl = `data:image/png;base64,${huge.toString('base64')}`; let decoded = false;
  await assert.rejects(E.validateProject(p, async () => { decoded = true; return { width: 100000, height: 640 }; }), /8192/);
  assert.equal(decoded, false);
});
test('custom phone dimensions and tablet aspect are constrained; output resource cap is explicit', () => {
  assert.equal(E.checkedProfile({ device: 'phone', width: 320, height: 640 }).height, 640);
  assert.throws(() => E.checkedProfile({ device: 'phone', width: 320, height: 641 }), /twice/);
  assert.throws(() => E.checkedProfile({ device: 'tablet-7', width: 1024, height: 768 }), /Tablet/);
  assert.throws(() => E.checkedProfile({ device: 'tablet-10', width: 7680, height: 4320 }), /24 megapixels/);
  assert.equal(E.profile(E.emptyProject(), 'feature-graphic').height, 500);
});
test('batch jobs retain order and avoid using phone captures for tablet profiles', () => {
  const p = fixture(); p.exportPresets = ['phone-portrait', 'tablet-7-portrait'];
  const jobs = E.jobs(p); assert.equal(jobs.length, 3); assert.equal(jobs[0].captureId, 'second'); assert.equal(jobs[1].order, 2);
  assert.ok(jobs.every(job => !job.file.includes('tablet-7')));
  assert.throws(() => E.jobs(p, { locales: ['en-US', 'en-US'] }), /distinct/);
  assert.throws(() => E.jobs(p, { presets: ['phone-portrait', 'phone-portrait'] }), /distinct/);
});
test('empty selection can be saved/reopened, but exporting no languages fails', async () => {
  const p = fixture(); p.exportLocales = []; const { project } = await E.validateProject(p, decode);
  assert.deepEqual(project.exportLocales, []); assert.throws(() => E.jobs(project), /Choose/);
});
test('UTF-8 ZIP contains CRC, STORE method and path guards', async () => {
  const data = new TextEncoder().encode('fixture'), bytes = new Uint8Array(await E.zip([{ name: 'ar/ملف.txt', data }]).arrayBuffer()), v = new DataView(bytes.buffer);
  assert.equal(v.getUint32(0, true), 0x04034b50); assert.equal(v.getUint16(6, true), 0x800); assert.equal(v.getUint16(8, true), 0);
  assert.equal(v.getUint32(14, true), E.crc32(data)); assert.equal(v.getUint32(bytes.length - 22, true), 0x06054b50);
  assert.throws(() => E.zip([{ name: '../escape', data }]), /Invalid ZIP/);
});
test('CSV preserves alt text and neutralizes spreadsheet formulas', () => {
  const csv = E.manifestCSV([{ alt_text: '=HYPERLINK("bad")', headline: 'one,two\nthree', file: 'en/01.png', order: 1 }]);
  assert.ok(csv.includes("'=")); assert.ok(csv.includes('one,two\nthree')); assert.ok(csv.includes('alt_text'));
});
test('CLI rejects unknown arguments and unsupported format before browser/network work', () => {
  assert.throws(() => parse(['--project', 'p.json', '--output', 'out', '--live']), /Unknown/);
  assert.throws(() => parse(['--project', 'p.json', '--output', 'out', '--format', 'gif']), /format/);
  assert.equal(parse(['--help']).help, true);
});
