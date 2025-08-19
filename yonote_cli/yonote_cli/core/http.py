"""HTTP helpers for yonote CLI."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

import requests


def http_json(method: str, url: str, token: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any] | bytes:
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        # Using a global ``requests.Session`` can lead to deadlocks when these
        # helpers are used from multiple threads.  The export command fetches
        # many documents concurrently, so we issue standalone requests instead
        # of sharing a session which is not thread-safe.
        resp = requests.request(
            method.upper(),
            url,
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "application/json" in ctype:
            try:
                return resp.json()
            except Exception:
                return resp.content
        return resp.content
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else ""
        print(f"[HTTP {e.response.status_code if e.response else '??'}] {body}", file=sys.stderr)
        sys.exit(2)
    except requests.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        sys.exit(2)


def http_multipart_post(url: str, token: str, fields: Dict[str, object]) -> Dict[str, Any] | bytes:
    data: Dict[str, Any] = {}
    files: Dict[str, Any] = {}
    for name, value in (fields or {}).items():
        if isinstance(value, tuple):
            filename, content, ctype = value
            files[name] = (filename, content, ctype)
        else:
            data[name] = value
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        resp = requests.post(url, headers=headers, data=data, files=files, timeout=120)
        resp.raise_for_status()
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "application/json" in ctype:
            try:
                return resp.json()
            except Exception:
                return resp.content
        return resp.content
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else ""
        print(f"[HTTP {e.response.status_code if e.response else '??'}] {body}", file=sys.stderr)
        sys.exit(2)
    except requests.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        sys.exit(2)
