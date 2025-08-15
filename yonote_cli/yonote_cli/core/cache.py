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


def list_documents_in_collection(
    base: str,
    token: str,
    collection_id: str,
    *,
    use_cache: bool,
    refresh_cache: bool,
    workers: int,
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
        limit=API_MAX_LIMIT,
        workers=workers,
        desc="Fetch docs",
    )
    if use_cache:
        cache[coll_key] = docs
        save_cache(cache)
    return docs
