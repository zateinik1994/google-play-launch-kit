#!/usr/bin/env node
'use strict';

// Offline, local-only headless rendering using exactly the editor's engine.
const fs = require('node:fs/promises');
const path = require('node:path');
const http = require('node:http');
const E = require('./engine.js');
function parse(argv) {
  const options = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    if (key === '--help' || key === '-h') return { help: true };
    if (key === '--zip') { options.zip = true; continue; }
    if (!['--project', '--output', '--locales', '--presets', '--format', '--browser-executable'].includes(key) || !argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error(`Unknown or incomplete argument: ${key}`);
    if (options[key.slice(2)] !== undefined) throw new Error(`Duplicate argument: ${key}`);
    options[key.slice(2)] = argv[++i];
  }
  if (!options.project || !options.output) throw new Error('--project and --output are required.');
  if (options.format && !['both', 'screenshots', 'feature'].includes(options.format)) throw new Error('--format must be both, screenshots or feature.');
  return options;
}
const help = `Play Launch Studio — offline project export (Node.js 20+)
Usage: node export.cjs --project saved-project.json --output new-directory
  --locales en-US,ru-RU      Override saved language selection
  --presets phone-portrait,phone-landscape  Override saved device profiles
  --format both|screenshots|feature        Default: saved export selection
  --zip                    Include assets.zip in the destination
  --browser-executable /path/to/chromium   Optional installed browser
Output must not exist. Real embedded captures are required; no uploads.
Install optional renderer: npm install; npx playwright install chromium
`;
async function exists(file) { try { await fs.lstat(file); return true; } catch (error) { if (error.code === 'ENOENT') return false; throw error; } }
async function main(argv) {
  const options = parse(argv); if (options.help) { process.stdout.write(help); return; }
  const input = path.resolve(options.project), output = path.resolve(options.output), parent = path.dirname(output);
  if (await exists(output)) throw new Error('Output already exists; choose a new directory.');
  const stat = await fs.stat(input); if (!stat.isFile() || stat.size > E.MAX_PROJECT_BYTES) throw new Error('Project must be a JSON file no larger than 225 MB.');
  const project = JSON.parse(await fs.readFile(input, 'utf8'));
  let chromium;
  try { ({ chromium } = require('playwright')); } catch { throw new Error('Optional Playwright dependency is missing. Run npm install in the generator directory, then npx playwright install chromium.'); }
  const names = new Map([['/', 'index.html'], ['/index.html', 'index.html'], ['/engine.js', 'engine.js'], ['/studio.js', 'studio.js'], ['/studio.css', 'studio.css']]);
  const server = http.createServer(async (req, res) => {
    const file = names.get(req.url);
    if (!file || req.method !== 'GET') { res.writeHead(404); res.end(); return; }
    try { const bytes = await fs.readFile(path.join(__dirname, file)); res.writeHead(200, { 'Content-Type': file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html', 'Cache-Control': 'no-store' }); res.end(bytes); } catch { res.writeHead(500); res.end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  let browser, staging;
  try {
    browser = await chromium.launch({ headless: true, ...(options['browser-executable'] ? { executablePath: path.resolve(options['browser-executable']) } : {}) });
    const context = await browser.newContext();
    await context.route('**/*', route => route.request().url().startsWith(url + '/') ? route.continue() : route.abort());
    const page = await context.newPage(); page.setDefaultTimeout(60000);
    await page.goto(url); await page.waitForFunction(() => !!window.PlayStudioEditor);
    await page.evaluate(async value => { await window.PlayStudioEditor.loadProject(value); }, project);
    const selection = {};
    if (options.locales) selection.locales = options.locales.split(',');
    if (options.presets) selection.presets = options.presets.split(',');
    if (options.format) { selection.feature = options.format !== 'screenshots'; if (options.format === 'feature') selection.presets = []; }
    const jobs = await page.evaluate(value => window.PlayStudioEditor.exportJobs(value), selection);
    // Preflight all copy/device/layout jobs before writing any exports.
    await page.evaluate(batch => window.PlayStudioEditor.preflightJobs(batch), jobs);
    await fs.mkdir(parent, { recursive: true }); staging = await fs.mkdtemp(path.join(parent, '.playstudio-'));
    const assets = [], zipEntries = []; let totalBytes = 0;
    for (const job of jobs) {
      const result = await page.evaluate(job => window.PlayStudioEditor.exportJob(job), job), bytes = Buffer.from(result.base64, 'base64');
      const target = path.resolve(staging, job.file); if (!target.startsWith(staging + path.sep)) throw new Error('Unsafe export path.');
      await fs.mkdir(path.dirname(target), { recursive: true }); await fs.writeFile(target, bytes, { flag: 'wx' }); assets.push(result.asset);
      if (options.zip) { totalBytes += bytes.length; if (totalBytes > 256 * 1024 * 1024) throw new Error('ZIP exceeds 256 MB. Export a smaller batch or omit --zip.'); zipEntries.push({ name: job.file, data: bytes }); }
    }
    const manifest = JSON.stringify({ version: 1, project_version: 2, assets, note: 'Review actual UI language, visual quality, policy, counts and Console coverage.' }, null, 2), csv = E.manifestCSV(assets);
    await fs.writeFile(path.join(staging, 'assets-manifest.json'), manifest, { flag: 'wx' }); await fs.writeFile(path.join(staging, 'assets-manifest.csv'), csv, { flag: 'wx' });
    if (options.zip) { zipEntries.push({ name: 'assets-manifest.json', data: Buffer.from(manifest) }, { name: 'assets-manifest.csv', data: Buffer.from(csv) }); await fs.writeFile(path.join(staging, 'assets.zip'), Buffer.from(await E.zip(zipEntries).arrayBuffer()), { flag: 'wx' }); }
    if (await exists(output)) throw new Error('Output appeared during rendering; it was left unchanged.');
    await fs.rename(staging, output); staging = null;
    process.stdout.write(JSON.stringify({ status: 'exported-local-files', assets: assets.length, output, manifest: path.join(output, 'assets-manifest.json'), uploaded: false }) + '\n');
  } finally {
    if (staging) await fs.rm(staging, { recursive: true, force: true });
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
}
if (require.main === module) main(process.argv.slice(2)).catch(error => { process.stderr.write(`Export failed: ${error.message}\n`); process.exitCode = 1; });
module.exports = { parse, main };
