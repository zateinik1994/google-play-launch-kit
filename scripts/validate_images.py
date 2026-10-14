#!/usr/bin/env python3
"""Compatibility entry point for canonical shared image validation."""
from pathlib import Path
import sys

# Clone scripts/ and a dereferenced installed references/validator both work.
for directory in (Path(__file__).resolve().parent.parent / "shared", Path(__file__).resolve().parent / "shared"):
    if (directory / "image_validation.py").is_file():
        sys.path.insert(0, str(directory))
        break
from image_validation import *

if __name__ == "__main__":
    raise SystemExit(main())
