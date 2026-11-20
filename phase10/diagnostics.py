"""Write the compatibility audit to a file when someone asks for it."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

from .audit import run


def write_report(path="phase10_diagnostics.json", extra=None):
    data = {"platform": platform.platform(), "python": sys.version, "audit": run(), "extra": extra or {}}
    Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return data
