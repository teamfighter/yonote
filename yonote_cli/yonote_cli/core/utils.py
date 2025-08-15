"""Utility functions for yonote CLI."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from .config import API_MAX_LIMIT
from .http import http_json

# --- progress (tqdm) ---
try:  # pragma: no cover - simple fallback
    from tqdm import tqdm  # type: ignore
except Exception:  # pragma: no cover
    class tqdm:  # type: ignore
        def __init__(self, *a, **kw): self.n=0
        def update(self, x=1): self.n+=x
        def set_postfix(self, **kw): pass
        def close(self): pass
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): self.close()


__all__ = ["fetch_all_concurrent", "format_rows", "safe_name", "tqdm"]


def _post_page(base: str, token: str, endpoint: str, params: Dict[str, Any], limit: int, offset: int) -> Dict[str, Any]:
    if limit > API_MAX_LIMIT:
        limit = API_MAX_LIMIT
    payload = dict(params or {})
    payload.update({"limit": limit, "offset": offset})
    data = http_json("POST", f"{base}{endpoint}", token, payload)
    if not isinstance(data, dict):
        return {"data": [], "pagination": {"total": 0}}
    if "data" not in data:
        data["data"] = data.get("results") or data.get("rows") or []
    return data


def fetch_all_concurrent(
    base: str,
    token: str,
    endpoint: str,
    *,
    params: Dict[str, Any] | None = None,
    limit: int = API_MAX_LIMIT,
    workers: int = 8,
    desc: str = "Loading",
) -> List[dict]:
    """Fetch all pages concurrently until a short page is received."""
    limit = min(limit, API_MAX_LIMIT)
    params = dict(params or {})

    first = _post_page(base, token, endpoint, params, limit, 0)
    items = list(first.get("data") or [])
    n_first = len(items)

    if n_first < limit:
        with tqdm(total=1, unit="pg", desc=desc) as bar:
            bar.update(1)
        return items

    results: List[dict] = items
    next_offset = limit
    with tqdm(total=None, unit="pg", desc=desc) as bar:
        bar.update(1)
        while True:
            offsets = list(range(next_offset, next_offset + limit * workers, limit))
            if not offsets:
                break
            stop = False
            with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
                futures = {ex.submit(_post_page, base, token, endpoint, params, limit, off): off for off in offsets}
                for fut in as_completed(futures):
                    data = fut.result()
                    page_items = data.get("data") or []
                    results.extend(page_items)
                    bar.update(1)
                    if len(page_items) < limit:
                        stop = True
            next_offset += limit * workers
            if stop:
                break
    return results


def format_rows(rows: List[Dict[str, Any]], fields: List[str]) -> None:
    if not rows:
        print("(no data)")
        return
    widths = [max(len(str(r.get(f, ""))) for r in rows + [dict(zip(fields, fields))]) for f in fields]
    header = " | ".join(f.ljust(w) for f, w in zip(fields, widths))
    sep = "-+-".join("-" * w for w in widths)
    print(header)
    print(sep)
    for r in rows:
        print(" | ".join(str(r.get(f, "")).ljust(w) for f, w in zip(fields, widths)))


def safe_name(name: str, maxlen: int = 120) -> str:
    """Return a filesystem-safe representation of *name*."""
    name = (name or "").strip()
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name)
    if len(name) > maxlen:
        name = name[:maxlen].rstrip()
    return name or "untitled"
