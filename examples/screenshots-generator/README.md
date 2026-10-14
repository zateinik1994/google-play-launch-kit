# Play Launch Studio

A local Canvas editor for Google Play phone screenshots (1080 × 1920) and feature graphics (1024 × 500). It uses the screenshots you upload and preserves the entire capture without cropping or stretching. It does not create app UI.

## Run

From this repository:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory examples/screenshots-generator
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Use a modern browser with Canvas `roundRect` support. There are no build steps, CDN requests, accounts, dependencies or uploads. Files are processed in your browser. Stop the server with Ctrl+C when finished. Opening `index.html` directly also works in modern browsers, but localhost is the recommended path.

## Create assets

1. Upload 1–8 real PNG or JPEG app captures. Select a thumbnail to edit its copy. Input captures are limited to 20 MB, 8192 px per side and 40 megapixels.
2. Enter an app name and a brief headline. An optional supporting line and alt text are saved in your project. Empty previews contain labelled placeholders; export stays disabled until a real capture, app name and headline are present. Long copy that does not fit also disables export.
3. Choose a color preset or edit the background, accent and text colors. Light/dark mode changes the studio, while the selected palette changes your assets.
4. Select a listing language or add a locale such as `de-DE`. App names and feature copy are per language; screenshot copy is per capture and per language. New languages begin empty. If actual UI captures differ by locale, save a separate project for each locale.
5. Switch between Phone and Feature graphic. Feature copy is edited separately. The selected capture is used in both layouts. Export the current asset as PNG; repeat for every capture and language you need.
6. Save project to download a JSON file embedding all source captures and copy. Open project restores it. Changes are not auto-saved; keep your project file as the editable source. Opening a project replaces the editor session only after successful validation.

Exports are explicitly **24-bit RGB PNG**, with no alpha channel. Native Canvas PNG exports can be RGBA even when all pixels look opaque, so the studio includes a small RGB encoder. Modern browsers use the built-in `CompressionStream`; a stored-DEFLATE fallback works without it. Preview guides are always excluded from downloads.

## Verify

```sh
python3 scripts/validate_images.py --kind screenshot path/to/phone-assets
python3 scripts/validate_images.py --kind feature-graphic path/to/feature-graphic.png
```

Run those commands from the repository root. The validator needs only Python's standard library. `--json` emits machine-readable results. Exit codes: `0` all technical checks pass, `1` at least one asset fails, `2` invalid invocation or no supported files found. Directories are searched recursively for PNG/JPEG; every file in a single invocation is treated as the selected `--kind`.

Phone dimensions are a recommendation preset, not the only permitted upload size. The studio targets ordinary phone listing artwork. It is not a replacement for dedicated tablet, Wear OS, TV, Automotive or XR capture workflows. Feature graphic composition guides are a local editorial inset, not an official guarantee against every crop.

Review legibility, accurate app content, translated copy, screenshot counts and device coverage before uploading. The validator does not assess these. Google may change its rules; check the [official preview asset guidance](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en-GB). Requirements last reviewed: 2026-10-14.

## Plan and hand off a complete package

Use the creative workflow in `knowledge/play-creatives.md` at the repository root, or `references/knowledge/play-creatives.md` in the installed screenshot skill, before assembling a new sequence: one clear user outcome per capture, UI that demonstrates it, short localized copy, and a locale/device coverage matrix. A typical phone set uses 4–8 frames; the publication minimum and recommendation eligibility are different rules. Planning copy and story does not require building a new Next.js project.

This editor has three color presets with editable colors and one layout for each output type. It exports the selected capture individually. It does not batch-export, reorder captures, upload to Console, create arbitrary slide layouts, or generate device-specific tablet/watch/TV artwork. Define the final sequence in a storyboard or manifest, name exports `phone-01-...`, `phone-02-...`, and set the intended order when uploading.

The locale controls change copy, not the captured UI. RTL languages set Canvas text direction; the feature layout remains text on the left and capture on the right. Review Arabic/Hebrew shaping and mixed numbers/names. If the composition needs mirroring, make an adapted layout in a suitable editor and use an actual RTL app capture; do not horizontally flip the UI image. Different UI language captures require separate projects.

Alt text is stored in the project JSON; it is not transmitted to Console or embedded as listing metadata in the PNG. Hand off the alt text separately with each file. App name and headline are this studio's export prerequisites, not universal Google Play rules; another compliant workflow can use plain in-app captures.

Keep project JSON, source captures, final PNGs and an asset manifest in the product's output folder. Record locale, device, order, source capture/build, headline, alt text and technical/visual/Console verification status. The project embeds full source captures; use sample data when captures contain account information. A saved project is the editable source and changes are not auto-saved.
