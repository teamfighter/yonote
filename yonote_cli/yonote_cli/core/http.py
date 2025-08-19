"""HTTP helpers for yonote CLI."""

from __future__ import annotations

import json
import uuid
import sys
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http_json(method: str, url: str, token: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any] | bytes:
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = Request(url=url, method=method.upper(), headers=headers, data=data)
    try:
        with urlopen(req, timeout=60) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            raw = resp.read()
            if "application/json" in ctype:
                try:
                    return json.loads(raw.decode("utf-8"))
                except Exception:
                    return raw
            return raw
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"[HTTP {e.code}] {body}", file=sys.stderr)
        sys.exit(2)
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(2)


def http_multipart_post(url: str, token: str, fields: Dict[str, object]) -> Dict[str, Any] | bytes:
    boundary = f"----yonotecli{uuid.uuid4().hex}"

    def to_b(x):
        return x if isinstance(x, (bytes, bytearray)) else str(x).encode("utf-8")

    parts: list[bytes] = []
    for name, value in (fields or {}).items():
        parts.append(f"--{boundary}\r\n".encode())
        if isinstance(value, tuple):
            filename, content, ctype = value
            if ctype is None:
                import mimetypes
                ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            parts.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
            parts.append(f"Content-Type: {ctype}\r\n\r\n".encode())
            parts.append(to_b(content))
            parts.append(b"\r\n")
        else:
            parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            parts.append(to_b(value))
            parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = Request(url=url, method="POST", headers=headers, data=body)
    try:
        with urlopen(req, timeout=120) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            raw = resp.read()
            if "application/json" in ctype:
                try:
                    return json.loads(raw.decode("utf-8"))
                except Exception:
                    return raw
            return raw
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"[HTTP {e.code}] {body}", file=sys.stderr)
        sys.exit(2)
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(2)

