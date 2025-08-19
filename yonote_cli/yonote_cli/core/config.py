"""Configuration helpers for yonote CLI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

CONFIG_PATH = Path(os.path.expanduser("~")) / ".yonote.json"
CACHE_PATH = Path(os.path.expanduser("~")) / ".yonote-cache.json"
# Default API endpoint used when no base URL is configured
DEFAULT_BASE = "https://app.yonote.ru/api"
# API limit for the ``limit`` parameter
API_MAX_LIMIT = 100


def load_config() -> Dict[str, Any]:
    """Load configuration from disk and environment."""
    cfg: Dict[str, Any] = {}
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    if os.getenv("YONOTE_BASE_URL"):
        cfg["base_url"] = os.getenv("YONOTE_BASE_URL")
    if os.getenv("YONOTE_TOKEN"):
        cfg["token"] = os.getenv("YONOTE_TOKEN")
    return cfg


def save_config(base_url: str | None, token: str | None) -> None:
    """Persist configuration to CONFIG_PATH."""
    cfg = load_config()
    if base_url is not None:
        cfg["base_url"] = base_url.rstrip("/")
    if token is not None:
        cfg["token"] = token
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved config to {CONFIG_PATH}")


def get_base_and_token() -> Tuple[str, str]:
    """Return API base URL and token or exit if missing.

    ``base_url`` in config may omit the trailing ``/api`` segment which the
    Yonote API expects. Normalize it here so network helpers always receive a
    base URL that already includes ``/api``.
    """
    cfg = load_config()
    base = cfg.get("base_url") or DEFAULT_BASE
    if not base.rstrip("/").endswith("/api"):
        base = base.rstrip("/") + "/api"
    token = cfg.get("token")
    if not token:
        print("Missing token. Run: yonote auth set --token <JWT>", file=sys.stderr)
        sys.exit(2)
    return base, token
