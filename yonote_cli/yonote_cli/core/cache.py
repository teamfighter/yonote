"""Cache helpers for yonote CLI."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .config import CACHE_PATH, API_MAX_LIMIT
from .utils import fetch_all_concurrent


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def list_collections(
    base: str,
    token: str,
    *,
    use_cache: bool,
    refresh_cache: bool,
    workers: int,
    desc: str | None = "Fetch collections",
) -> List[dict]:
    cache = load_cache() if use_cache else {}
    if use_cache and not refresh_cache and "collections" in cache:
        return cache["collections"]
    cols = fetch_all_concurrent(
        base,
        token,
        "/collections.list",
        params={},
        limit=API_MAX_LIMIT,
        workers=workers,
        desc=desc,
    )
    if use_cache:
        cache["collections"] = cols
        save_cache(cache)
    return cols


def list_documents_in_collection(
    base: str,
    token: str,
    collection_id: str,
    *,
    use_cache: bool,
    refresh_cache: bool,
    workers: int,
    desc: str | None = "Fetch docs",
) -> List[dict]:
    cache = load_cache() if use_cache else {}
    coll_key = f"collection:{collection_id}"
    if use_cache and not refresh_cache and coll_key in cache:
        return cache[coll_key]
    docs = fetch_all_concurrent(
        base,
        token,
        "/documents.list",
        params={"collectionId": collection_id},
        workers=workers,
        desc=desc,
    )
    if use_cache:
        cache[coll_key] = docs
        save_cache(cache)
    return docs


def refresh_document_branch(
    base: str,
    token: str,
    collection_id: str,
    parent_id: str | None,
    *,
    workers: int,
    desc: str | None = "Refresh docs",
) -> List[dict]:
    """Refresh cached documents under *parent_id* within *collection_id*.

    Returns the updated list of all documents for the collection.
    """

    cache = load_cache()
    coll_key = f"collection:{collection_id}"
    docs: List[Dict[str, Any]] = cache.get(coll_key, [])

    params: Dict[str, Any] = {"collectionId": collection_id}
    if parent_id is not None:
        params["parentDocumentId"] = parent_id
    else:
        params["parentDocumentId"] = None

    new_children = fetch_all_concurrent(
        base,
        token,
        "/documents.list",
        params=params,
        workers=workers,
        desc=desc,
    )

    to_remove: set[str] = set()
    stack = [d.get("id") for d in docs if d.get("parentDocumentId") == parent_id]
    while stack:
        cur = stack.pop()
        to_remove.add(cur)
        stack.extend(d.get("id") for d in docs if d.get("parentDocumentId") == cur)

    docs = [d for d in docs if d.get("id") not in to_remove]
    docs.extend(new_children)

    cache[coll_key] = docs
    save_cache(cache)
    return docs
