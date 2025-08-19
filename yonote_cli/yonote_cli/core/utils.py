"""Utility functions for yonote CLI."""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

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


__all__ = [
    "fetch_all_concurrent",
    "format_rows",
    "safe_name",
    "ensure_text",
    "export_document_content",
    "tqdm",
]



def _post_page(base: str, token: str, path: str, params: Dict[str, Any], limit: int, offset: int) -> Dict[str, Any]:
    """POST a single paginated request and return the JSON payload."""
    if limit > API_MAX_LIMIT:
        limit = API_MAX_LIMIT
    payload = dict(params or {})
    payload.update({"limit": limit, "offset": offset})

    if path.startswith("http://") or path.startswith("https://"):
        url = path
    elif path.startswith("/api/"):
        root = base.split("/api")[0].rstrip("/")
        url = f"{root}{path}"
    elif path.startswith("/"):
        url = f"{base.rstrip('/')}{path}"
    else:
        url = f"{base.rstrip('/')}/{path}"

    data = http_json("POST", url, token, payload)
    if not isinstance(data, dict):
        return {"data": [], "pagination": {"total": 0}}
    if "data" not in data:
        data["data"] = data.get("results") or data.get("rows") or []
    return data


def fetch_all_concurrent(
    base: str,
    token: str,
    path: str,
    *,
    params: Dict[str, Any] | None = None,
    limit: int = API_MAX_LIMIT,
    workers: int = 8,
    desc: str = "Loading",
) -> List[dict]:
    """Fetch all pages concurrently until a short page is received."""
    limit = min(limit, API_MAX_LIMIT)
    params = dict(params or {})

    first = _post_page(base, token, path, params, limit, 0)
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
                futures = {ex.submit(_post_page, base, token, path, params, limit, off): off for off in offsets}
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

def ensure_text(value: Any) -> str:
    """Return *value* decoded to text.

    The Yonote API sometimes returns exported document content either as a
    string, raw bytes, or a JSON-serialized Node.js ``Buffer`` object of the
    form ``{"type": "Buffer", "data": [...]}``.  This helper normalizes
    those representations into a UTF-8 ``str``.
    """

    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8")
    if isinstance(value, dict):
        # handle Node.js Buffer serialization
        buf_type = value.get("type")
        buf_data = value.get("data")
        if buf_type == "Buffer" and isinstance(buf_data, list):
            try:
                return bytes(buf_data).decode("utf-8")
            except Exception:
                pass
        inner = value.get("data")
        if inner is not None and set(value.keys()) == {"data"}:
            return ensure_text(inner)
    # Fallback to JSON string representation to avoid obscure AttributeError
    return json.dumps(value, ensure_ascii=False)


def export_document_content(base: str, token: str, doc_id: str) -> str:
    """Return exported document text.

    The API may return the content directly or a ``fileOperation`` object
    that requires polling ``fileOperations.redirect`` until a presigned
    ``Location`` header is returned. This helper abstracts that logic and
    always returns the document body as UTF-8 text.
    """

    data = http_json("POST", f"{base}/documents.export", token, {"id": doc_id})

    if isinstance(data, (bytes, bytearray)):
        try:
            data = json.loads(data.decode("utf-8"))
        except Exception:
            return ensure_text(data)

    if isinstance(data, dict):
        content = data.get("data")
        if content is not None and not isinstance(content, dict):
            return ensure_text(content)
        fo = data.get("fileOperation")
        if not fo and isinstance(content, dict):
            fo = content.get("fileOperation")
        op_id = fo.get("id") if fo else None
        if op_id:
            url = f"{base}/fileOperations.redirect"
            payload = json.dumps({"id": op_id}).encode("utf-8")
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }

            class _NoRedirect(HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, hdrs, newurl):
                    return None

            opener = build_opener(_NoRedirect)
            for _ in range(6):
                req = Request(url=url, method="POST", headers=headers, data=payload)
                try:
                    resp = opener.open(req, timeout=60)
                except HTTPError as e:  # type: ignore[assignment]
                    resp = e
                location = resp.headers.get("Location")
                body = resp.read()
                if location:
                    try:
                        with urlopen(location, timeout=60) as final:
                            return ensure_text(final.read())
                    except HTTPError as e:
                        err_body = e.read().decode("utf-8", errors="ignore")
                        print(f"[HTTP {e.code}] {err_body}", file=sys.stderr)
                        sys.exit(2)
                time.sleep(1)
            raise RuntimeError("export timed out")

    return ensure_text(data)
