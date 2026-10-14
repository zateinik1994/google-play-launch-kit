#!/usr/bin/env python3
"""Check Google Play phone/tablet/feature/icon file properties, using stdlib.

This checks technical properties only, not listing policy or visual quality. PNG
CRC, scanline sizes and zlib data are checked. JPEG dimensions are read from the
header; entropy-coded image data is not decoded. See --help for usage.
"""
from __future__ import annotations

import argparse
import binascii
import json
from pathlib import Path
import struct
import sys
import zlib

SOURCE = "https://support.google.com/googleplay/android-developer/answer/9866151?hl=en-GB"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_DECODE_BYTES = 96 * 1024 * 1024


class ImageError(ValueError):
    """The file is malformed or cannot be inspected safely."""


def _png_layout(width: int, height: int, bits_per_pixel: int, interlace: int):
    passes = [(0, 0, 1, 1)] if interlace == 0 else [
        (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
        (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
    ]
    result = []
    for x, y, dx, dy in passes:
        columns = max(0, (width - x + dx - 1) // dx)
        rows = max(0, (height - y + dy - 1) // dy)
        if columns and rows:
            result.append((rows, (columns * bits_per_pixel + 7) // 8 + 1))
    return result


def _inspect_png(data: bytes) -> dict:
    offset = 8
    header = None
    image_parts = []
    transparency = False
    ended = False
    idat_finished = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ImageError("Truncated PNG chunk.")
        length = struct.unpack_from(">I", data, offset)[0]
        end = offset + 12 + length
        if end > len(data):
            raise ImageError("Truncated PNG chunk data.")
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
        if binascii.crc32(kind + payload) & 0xffffffff != crc:
            raise ImageError(f"Invalid CRC in PNG {kind.decode('ascii', errors='replace')} chunk.")
        if header is None and kind != b"IHDR":
            raise ImageError("PNG must start with IHDR.")
        if kind == b"IHDR":
            if header is not None or length != 13:
                raise ImageError("Invalid PNG IHDR.")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            if idat_finished:
                raise ImageError("PNG IDAT chunks must be consecutive.")
            image_parts.append(payload)
        else:
            if image_parts:
                idat_finished = True
            if kind == b"tRNS":
                transparency = True
            if kind == b"IEND":
                if length != 0 or end != len(data):
                    raise ImageError("Invalid PNG IEND or trailing data.")
                ended = True
                break
        offset = end
    if not header or not image_parts or not ended:
        raise ImageError("PNG needs IHDR, IDAT and IEND chunks.")
    width, height, depth, color, compression, filtering, interlace = header
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color)
    allowed_depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    if not width or not height or not channels or depth not in allowed_depths[color] or compression or filtering or interlace not in (0, 1):
        raise ImageError("Invalid or unsupported PNG header.")
    layout = _png_layout(width, height, depth * channels, interlace)
    expected = sum(rows * row_size for rows, row_size in layout)
    if expected > MAX_DECODE_BYTES:
        raise ImageError("PNG decoded data exceeds the 96 MB inspection limit.")
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(b"".join(image_parts), expected + 1)
        if len(raw) != expected or not decoder.eof or decoder.unused_data:
            raise ImageError("Invalid PNG compressed data or scanline length.")
    except zlib.error as error:
        raise ImageError(f"Invalid PNG compressed data: {error}") from error
    cursor = 0
    for rows, row_size in layout:
        for _ in range(rows):
            if raw[cursor] > 4:
                raise ImageError("Invalid PNG scanline filter.")
            cursor += row_size
    return {"format": "PNG", "width": width, "height": height, "bit_depth": depth, "color_type": color,
            "has_alpha": color in (4, 6) or transparency, "bytes": len(data), "integrity": "PNG CRC and compressed scanlines checked"}


def _inspect_jpeg(data: bytes) -> dict:
    offset = 2
    header = None
    scan = False
    # Read marker segments up to the first entropy-coded scan, including SOF.
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset < len(data):
        if data[offset] != 0xFF:
            raise ImageError("Invalid JPEG header marker.")
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker == 0xD9:
            break
        if marker in {0xD8, 0x01} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            raise ImageError("Truncated JPEG segment.")
        length = struct.unpack_from(">H", data, offset)[0]
        if length < 2 or offset + length > len(data):
            raise ImageError("Invalid JPEG segment length.")
        payload = data[offset + 2:offset + length]
        if marker in sof:
            if len(payload) < 6:
                raise ImageError("Invalid JPEG frame header.")
            depth, height, width, components = struct.unpack_from(">BHHB", payload)
            if not width or not height or not components or len(payload) != 6 + 3 * components:
                raise ImageError("Invalid JPEG dimensions or component table.")
            if header is not None:
                raise ImageError("Multiple JPEG frame headers are not supported.")
            header = (width, height, depth, components)
        if marker == 0xDA:
            scan = True
            break
        offset += length
    if not header or not scan or not data.endswith(b"\xff\xd9"):
        raise ImageError("JPEG needs a frame header, scan and end marker.")
    width, height, depth, components = header
    return {"format": "JPEG", "width": width, "height": height, "bit_depth": depth, "components": components,
            "has_alpha": False, "bytes": len(data), "integrity": "JPEG header checked; image scan is not decoded"}


def inspect_image(path: str | Path) -> dict:
    path = Path(path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ImageError("File exceeds the 64 MB inspection limit.")
    data = path.read_bytes()
    if data.startswith(PNG_SIGNATURE):
        return _inspect_png(data)
    if data.startswith(b"\xff\xd8"):
        return _inspect_jpeg(data)
    raise ImageError("Expected a PNG or JPEG file (detected by contents, not extension).")


def validate_image(path: str | Path, kind: str = "screenshot") -> dict:
    """Technical profile check. 'screenshot' remains the phone profile.

    'tablet-screenshot' applies the specific large-screen guidance (1080–7680
    pixels, 9:16/16:9), not the general phone 320–3840 profile. Counts, actual
    device/UI content and overlay rules still require review. Checked 2026-10-14.
    """
    if kind not in ("screenshot", "tablet-screenshot", "feature-graphic", "icon"):
        raise ValueError("Unknown asset kind.")
    result = {"path": str(path), "kind": kind, "valid": False, "errors": [], "warnings": []}
    try:
        info = inspect_image(path)
    except (OSError, ImageError) as error:
        result["errors"].append(str(error))
        return result
    result.update(info)
    errors = result["errors"]
    width, height = info["width"], info["height"]
    if kind == "icon":
        if info["format"] != "PNG" or info.get("color_type") != 6 or info["bit_depth"] != 8:
            errors.append("Play listing icons must be 32-bit PNG (8-bit RGBA).")
        if (width, height) != (512, 512):
            errors.append("Play listing icons must be 512 × 512 px.")
        if info["bytes"] > 1024 * 1024:
            errors.append("Play listing icons must be at most 1024 KB.")
    else:
        if info["format"] == "PNG" and (info.get("color_type") != 2 or info["bit_depth"] != 8 or info["has_alpha"]):
            errors.append("Use 24-bit RGB PNG without alpha or transparency, or JPEG.")
        if info["format"] == "JPEG" and info["bit_depth"] != 8:
            errors.append("Use an 8-bit JPEG.")
        if kind == "feature-graphic" and (width, height) != (1024, 500):
            errors.append("Feature graphics must be exactly 1024 × 500 px.")
        if kind == "screenshot":
            if min(width, height) < 320 or max(width, height) > 3840:
                errors.append("Phone screenshot dimensions must be between 320 and 3840 px.")
            if max(width, height) > 2 * min(width, height):
                errors.append("The longer side must be no more than twice the shorter side.")
            if min(width, height) < 1080 or not (width * 16 == height * 9 or width * 9 == height * 16):
                result["warnings"].append("Recommendation formats call for 9:16 or 16:9 screenshots, with a minimum short side of 1080 px.")
        if kind == "tablet-screenshot":
            if min(width, height) < 1080 or max(width, height) > 7680:
                errors.append("Tablet screenshot dimensions must be between 1080 and 7680 px for the large-screen profile.")
            if not (width * 16 == height * 9 or width * 9 == height * 16):
                errors.append("Tablet screenshots must use 9:16 portrait or 16:9 landscape for the large-screen profile.")
    if info["format"] == "JPEG":
        result["warnings"].append("JPEG scan data is not decoded. Open the image to verify rendering before upload.")
    result["valid"] = not errors
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path, help="PNG/JPEG files or directories (directories are searched recursively)")
    parser.add_argument("--kind", choices=("screenshot", "tablet-screenshot", "feature-graphic", "icon"), default="screenshot", help="All files use this profile; screenshot is phone, tablet-screenshot uses large-screen guidance")
    parser.add_argument("--json", action="store_true", help="Machine-readable results")
    args = parser.parse_args(argv)
    paths = []
    for path in args.paths:
        if path.is_dir():
            paths.extend(sorted(item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in (".png", ".jpg", ".jpeg")))
        else:
            paths.append(path)
    paths = list(dict.fromkeys(paths))
    if not paths:
        if args.json:
            print(json.dumps({"valid": False, "errors": ["No PNG/JPEG files found."], "results": []}))
        else:
            print("No PNG/JPEG files found.", file=sys.stderr)
        return 2
    results = [validate_image(path, args.kind) for path in paths]
    valid = all(result["valid"] for result in results)
    if args.json:
        print(json.dumps({"valid": valid, "source": SOURCE, "scope": "Technical file checks only; no content, screenshot count, or device-specific policy review", "results": results}, indent=2, ensure_ascii=False))
    else:
        for result in results:
            dimensions = f" {result['width']}×{result['height']} {result['format']}" if "width" in result else ""
            print(f"{'PASS' if result['valid'] else 'FAIL'} {result['path']}{dimensions}")
            for error in result["errors"]:
                print(f"  error: {error}")
            for warning in result["warnings"]:
                print(f"  note: {warning}")
        print("Technical checks only. Review real app content, required screenshot counts and device-specific rules before upload.")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
