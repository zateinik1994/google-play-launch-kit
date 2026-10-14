#!/usr/bin/env python3
"""Repository convenience wrapper for shared.cli."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.cli import main
if __name__ == "__main__":
    raise SystemExit(main())
