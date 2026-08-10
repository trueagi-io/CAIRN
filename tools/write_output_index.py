#!/usr/bin/env python3
"""Write output/index.json (structural + cognitive_synergy run inventory)."""

from __future__ import annotations

import sys
from pathlib import Path

CAIRN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CAIRN / "dashboard"))
import data  # noqa: E402


def main() -> int:
    out = CAIRN / "output"
    path = data.write_output_index(out)
    print(f"[write_output_index] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
