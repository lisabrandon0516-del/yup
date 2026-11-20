"""Time a page refresh. The timer does not change the company."""

from __future__ import annotations

import time


def measure(label, func, *args, **kwargs):
    start = time.perf_counter()
    value = func(*args, **kwargs)
    return {"label": label, "elapsed_ms": (time.perf_counter() - start) * 1000, "value": value}


def page_refresh_report(registry, state) -> list[dict]:
    rows = []
    pages = getattr(registry, "pages", {}) or {}
    for page_id, page in pages.items():
        start = time.perf_counter()
        error = ""
        try:
            page.load(state)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        rows.append({"page": page_id, "elapsed_ms": (time.perf_counter() - start) * 1000, "error": error})
    return rows
