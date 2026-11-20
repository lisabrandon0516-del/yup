"""Import check for the desks already in the game. A missing module is reported, not installed."""

from __future__ import annotations

import importlib
import sys
import time
from dataclasses import asdict, dataclass

from .manifest import CORE_REQUIRED, OPTIONAL_REQUIRED, PHASES


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    elapsed_ms: float = 0.0


def module_check(name: str) -> Check:
    began = time.perf_counter()
    try:
        importlib.import_module(name)
        status = "pass"
        detail = "Imported"
    except ModuleNotFoundError as exc:
        status = "missing"
        detail = str(exc)
    except Exception as exc:
        status = "fail"
        detail = f"{type(exc).__name__}: {exc}"
    return Check(name, status, detail, (time.perf_counter() - began) * 1000)


def run() -> dict:
    checks = [module_check(name) for name in CORE_REQUIRED + OPTIONAL_REQUIRED]
    phases = {}
    for number, names in PHASES.items():
        rows = [module_check(name) for name in names]
        phases[number] = [asdict(row) for row in rows]
        checks.extend(rows)
    failures = [item for item in checks if item.status == "fail"]
    missing = [item for item in checks if item.status == "missing"]
    return {
        "python": sys.version,
        "checks": [asdict(item) for item in checks],
        "phases": phases,
        "failures": len(failures),
        "missing": len(missing),
        "ready": not failures and not missing,
    }
