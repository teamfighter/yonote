"""Cache management commands."""

from __future__ import annotations

import json
from ..core import CACHE_PATH


def cache_info(_args):
    p = CACHE_PATH
    if p.exists():
        print(f"Cache file: {p}  ({p.stat().st_size} bytes)")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            keys = list(data.keys())
            print(f"Keys: {len(keys)}")
            if keys:
                print("Sample keys:", ", ".join(keys[:5]))
        except Exception as e:
            print(f"Cannot parse cache: {e}")
    else:
        print(f"No cache file at: {p}")


def cache_clear(_args):
    p = CACHE_PATH
    if p.exists():
        p.unlink()
        print(f"Removed {p}")
    else:
        print("Nothing to clear.")
