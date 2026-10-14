"""Behavior tests for file integrity, dimension boundaries and output contracts."""
import binascii
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_images.py"
spec = importlib.util.spec_from_file_location("validate_images", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xffffffff)


def png(width, height, color=2, transparent=False):
    channels = {2: 3, 6: 4}[color]
    data = validator.PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color, 0, 0, 0))
    if transparent:
        data += chunk(b"tRNS", struct.pack(">HHH", 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress((b"\0" + b"\x88" * width * channels) * height))
    return data + chunk(b"IEND", b"")


def jpeg_header(width, height):
    # Deliberately header-only: validator explicitly does not decode JPEG scan data.
    payload = struct.pack(">BHHB", 8, height, width, 3) + b"\x01\x11\x00\x02\x11\x00\x03\x11\x00"
    sos = b"\x03\x01\x00\x02\x00\x03\x00\x00\x3f\x00"
    return b"\xff\xd8\xff\xc0" + struct.pack(">H", len(payload) + 2) + payload + b"\xff\xda" + struct.pack(">H", len(sos) + 2) + sos + b"\xff\xd9"


class ImageValidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def check(self, data, kind="screenshot"):
        path = self.root / "asset.png"
        path.write_bytes(data)
        return validator.validate_image(path, kind)

    def test_recommended_portrait_and_landscape_pass(self):
        for width, height in ((1080, 1920), (1920, 1080)):
            with self.subTest(size=(width, height)):
                result = self.check(png(width, height))
                self.assertTrue(result["valid"], result)
                self.assertEqual(result["warnings"], [])
                self.assertEqual(result["color_type"], 2)

    def test_minimum_dimensions_and_two_to_one_are_inclusive(self):
        result = self.check(png(320, 640))
        self.assertTrue(result["valid"], result)
        self.assertTrue(result["warnings"])
        self.assertFalse(self.check(png(320, 641))["valid"])
        self.assertFalse(self.check(png(319, 600))["valid"])

    def test_maximum_boundary(self):
        self.assertTrue(self.check(png(1920, 3840))["valid"])
        self.assertFalse(self.check(png(1921, 3841))["valid"])

    def test_feature_graphic_is_exact_size(self):
        self.assertTrue(self.check(png(1024, 500), "feature-graphic")["valid"])
        self.assertFalse(self.check(png(1024, 512), "feature-graphic")["valid"])

    def test_tablet_profile_accepts_real_rgb_above_phone_maximum(self):
        data = png(4096, 2304)
        self.assertTrue(self.check(data, "tablet-screenshot")["valid"])
        self.assertFalse(self.check(data, "screenshot")["valid"])
        self.assertTrue(self.check(png(1440, 2560), "tablet-screenshot")["valid"])

    def test_tablet_boundaries_aspect_and_alpha(self):
        # Header-only JPEG boundary fixtures keep the test lightweight; RGB PNG
        # decoding/integrity is exercised in the separate tablet test above.
        for size in ((1080, 1920), (4320, 7680), (7680, 4320)):
            self.assertTrue(self.check(jpeg_header(*size), "tablet-screenshot")["valid"])
        for size in ((1071, 1904), (4329, 7696), (1440, 1440), (1280, 800)):
            self.assertFalse(self.check(jpeg_header(*size), "tablet-screenshot")["valid"])
        self.assertFalse(self.check(png(1440, 2560, color=6), "tablet-screenshot")["valid"])

    def test_tablet_cli_and_legacy_phone_default_have_distinct_results(self):
        path = self.root / "tablet.jpg"
        path.write_bytes(jpeg_header(4096, 2304))
        command = [sys.executable, str(SCRIPT), str(path), "--json"]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        result = subprocess.run(command + ["--kind", "tablet-screenshot"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["results"][0]["kind"], "tablet-screenshot")

    def test_alpha_and_transparency_rejected_even_if_opaque(self):
        self.assertFalse(self.check(png(1080, 1920, color=6))["valid"])
        self.assertFalse(self.check(png(1080, 1920, transparent=True))["valid"])

    def test_icon_requires_rgba_and_512_square(self):
        self.assertTrue(self.check(png(512, 512, color=6), "icon")["valid"])
        self.assertFalse(self.check(png(512, 512), "icon")["valid"])
        self.assertFalse(self.check(png(500, 512, color=6), "icon")["valid"])

    def test_crc_and_truncation_are_rejected(self):
        data = bytearray(png(320, 640))
        data[-1] ^= 1
        self.assertIn("CRC", self.check(bytes(data))["errors"][0])
        self.assertFalse(self.check(png(320, 640)[:-8])["valid"])

    def test_bad_png_scanline_length_is_rejected(self):
        data = validator.PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", 1080, 1920, 8, 2, 0, 0, 0))
        data += chunk(b"IDAT", zlib.compress(b"\0abc")) + chunk(b"IEND", b"")
        self.assertIn("scanline", self.check(data)["errors"][0])

    def test_wrong_type_and_missing_file_fail(self):
        self.assertFalse(self.check(b"<svg></svg>")["valid"])
        self.assertFalse(validator.validate_image(self.root / "missing.png")["valid"])

    def test_jpeg_dimensions_and_limited_integrity_are_reported(self):
        result = self.check(jpeg_header(1024, 500), "feature-graphic")
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["format"], "JPEG")
        self.assertIn("not decoded", result["warnings"][0])
        self.assertFalse(self.check(jpeg_header(1024, 500)[:-2], "feature-graphic")["valid"])

    def test_json_cli_and_exit_codes(self):
        path = self.root / "feature.png"
        path.write_bytes(png(1024, 500))
        command = [sys.executable, str(SCRIPT), str(path), "--kind", "feature-graphic", "--json"]
        success = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(success.returncode, 0)
        self.assertTrue(json.loads(success.stdout)["valid"])
        path.write_bytes(png(1000, 500))
        failure = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(failure.returncode, 1)
        self.assertFalse(json.loads(failure.stdout)["valid"])

    def test_empty_directory_is_an_input_error(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.root), "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["results"], [])


if __name__ == "__main__":
    unittest.main()
