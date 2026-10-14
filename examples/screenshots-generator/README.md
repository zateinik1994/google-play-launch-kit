# Play Launch Studio

Local Google Play artwork from your actual Android captures. The browser editor has no build step, CDN dependency, accounts or uploads. It preserves each full capture without stretching, cropping, hardware frames or generated UI.

## Run the editor

From the repository root:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory examples/screenshots-generator
```

Open [localhost](http://127.0.0.1:8000) in a modern browser. An installed screenshot skill includes the same files under `references/generator`; point `--directory` there instead. Stop the server with Ctrl+C. Files stay in your browser; changes are not auto-saved.

## Create and export a package

1. Select the actual source device: phone, 7-inch tablet or 10-inch tablet. Upload real PNG/JPEG captures, up to eight per device. A resized phone capture does not demonstrate tablet UI. Use the ↑/↓ buttons to arrange the sequence for each device.
2. Select a capture and edit its headline, supporting line and alt text. App name and copy are per language; screenshot copy is per capture. New languages start empty. `UI only` layouts can export plain captures without marketing copy.
3. Add languages and upload a **UI source override for the selected language/capture** when the actual UI differs. Without an override, the default capture is used and clearly identified in the manifest; review whether its UI language matches your listing promises.
4. Choose portrait/landscape phone or tablet profiles. Set stacked, split or UI-only layout, text region and relative UI size. Changes can apply to the selected capture or profile defaults. Custom phone sizes allow 320–3840 px and aspect ≤2:1; tablet sizes allow 1080–7680 px, 9:16/16:9, subject to the renderer's 24-megapixel cap. Feature graphics remain exactly 1024×500. Tablet presets use UI-only composition.
5. Use **Apply colors to** for a project palette or an override for the selected screenshot/feature graphic. Contrast slides can differ without changing neighboring assets; **Use project palette** removes the override. Palettes survive save/open and are recorded in both manifests.
6. Text direction follows the locale script, including explicit tags such as `az-Arab` or `ar-Latn`; split composition mirrors for RTL. The source image is never flipped. Check native glyphs, mixed numbers/names and the app's genuine RTL capture. Locale data comes from the browser's `Intl.Locale`; structurally invalid and equivalent duplicate tags are rejected.
7. Switch to Feature graphic, choose its source capture and edit the feature copy for each language. Feature source selection is saved in the project and used consistently by the preview and batch exporter.
8. Save project. Version 2 JSON embeds default/localized captures, device labels, order, copy, layouts, palette overrides and export selection. Version 1 projects open through migration; saving creates v2. Invalid imports leave the current session intact.
9. Select batch languages/profiles and optional feature graphic. **Export ZIP + manifests** renders all matching captures, in device order, into one archive with RGB PNGs plus `assets-manifest.json` and `.csv`. Missing copy or overflow blocks the entire batch before download. Individual PNG export remains available.

Export profiles are alternative sets. If you export both portrait and landscape, choose the final sequence within Play's limit of eight screenshots per device; do not upload every alternative automatically. Profiles with no matching captures produce no screenshots. Review device coverage in the manifest and ensure the intended device sets are present.

PNG output is explicitly **24-bit RGB without alpha**. Preview guides are excluded. Native `CompressionStream` is used when available, with a stored-DEFLATE fallback. The local ZIP writer needs no external package. Alt text and order are in the manifests, not embedded as Play listing metadata inside PNG. CSV escapes spreadsheet formula prefixes.

## Headless rendering from a saved project

Optional CLI requires Node.js 20+ and Playwright/Chromium. The editor above does not require npm. Install the locked renderer dependencies in this directory:

```sh
npm ci --ignore-scripts
npx playwright install chromium
node export.cjs --project /absolute/path/project.json --output /absolute/path/new-assets --zip
```

Or from an installed skill, run `npm ci` inside `references/generator` and execute its `export.cjs`. Use `--help` for options:

```sh
node export.cjs --project /absolute/path/project.json --output /absolute/path/new-assets \
  --locales en-US,ar --presets phone-portrait,phone-landscape --format screenshots
```

`--format both|screenshots|feature` overrides saved selection; otherwise the project selection is used. `--browser-executable /absolute/path/chromium` can use an existing browser instead of a downloaded Playwright browser. Assets are rendered with the same `engine.js` as the editor, through a temporary localhost server; external requests are blocked. No Google accounts, API access or uploads are involved.

The output directory must not exist. The CLI validates the whole project and preflights chosen layouts before rendering, writes into a temporary sibling folder and exposes the destination only after the whole batch succeeds. On failure, temporary exports are cleaned up. Existing output is never deliberately overwritten. JSON stdout names the final destination and manifest; it never prints embedded captures.

System fonts are used. Pixel appearance can vary by OS/browser/font installation, including text antialiasing between browser processes; reproduce the browser environment for stable artwork. Every export still needs visual review.

Direction uses the script's RTL flag from [Unicode CLDR script metadata](https://github.com/unicode-org/cldr/blob/main/common/properties/scriptMetadata.txt), checked 2026-10-14, and the runtime's likely script when a tag omits it. [Intl locale direction](https://tc39.es/proposal-intl-locale-info/#sec-Intl.Locale.prototype.getTextInfo) gives the model; glyph and locale support still depend on the environment and store.

## Limits and verification

Source limits: 20 MB each, 8192 px per side, 40 megapixels each, 120 megapixels decoded across the project. JSON limit: 225 MB. Batch: 400 assets; ZIP: 256 MB. These are local memory limits, not Google Play upload rules. Split large locale/device projects when needed. Browser decoding/Canvas support is required.

Run technical checks from the repository root:

```sh
python3 scripts/validate_images.py --kind screenshot /absolute/path/phone-assets
python3 scripts/validate_images.py --kind tablet-screenshot /absolute/path/tablet-assets
python3 scripts/validate_images.py --kind feature-graphic /absolute/path/feature-graphic.png
```

`screenshot` preserves the original phone profile; `tablet-screenshot` validates the specific large-screen 1080–7680 px, 9:16/16:9 profile. The publisher maps 7-inch and 10-inch uploads to that profile. A successful file check does not establish real-app accuracy, translation quality, screenshot counts, policy approval or Console coverage. Check [official preview asset requirements](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en-GB), last reviewed 2026-10-14. Wear, TV, Automotive and XR require their own capture/profile workflow.

Use the creative workflow in repository `knowledge/play-creatives.md`, or installed skill `references/knowledge/play-creatives.md`, for storyboard and review. Projects embed source captures: protect account/customer information and keep them in the product output folder.

## Tests

```sh
npm test
npm run test:browser
```

Pure engine tests require only Node. Browser integration uses synthetic PNG fixtures to verify file upload, edits, ordering, localized sources, RTL geometry, transactional import, project round trip, ZIP/manifest contents, RGB dimensions, CLI parity and refusal to overwrite. Synthetic fixtures are not store-ready app assets. Set `PLAYSTUDIO_BROWSER_EXECUTABLE` to use an installed Chromium executable during tests.
