"""Minimal HTTP helpers for the CLI.

The implementation uses :mod:`urllib` from the Python standard library to
avoid external dependencies.  Functions are intentionally small and
well-commented so they can be modified easily if the API changes.
"""

from __future__ import annotations

import json
import uuid
import sys
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def http_json(
    method: str,
    url: str,
    token: str,
    payload: Dict[str, Any] | None = None,
    *,
    handle_error: bool = True,
) -> Dict[str, Any] | bytes:
    """Perform an HTTP request and return parsed JSON or raw bytes.

    By default HTTP errors are handled via :func:`_handle_http_error` which
    prints a message and exits the program.  Some callers may wish to deal with
    errors on a per-item basis (e.g. when adding multiple group members).  For
    those cases ``handle_error`` can be set to ``False`` so the original
    :class:`HTTPError` is raised for the caller to inspect.
    """

    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    data = None
    if payload is not None:
        # JSON body for POST/PUT requests
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
                    # Return raw bytes if the body is not valid JSON
                    return raw
            return raw
    except HTTPError as e:
        if handle_error:
            _handle_http_error(e)
        else:
            raise
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(2)


def http_multipart_post(
    url: str,
    token: str,
    fields: Dict[str, object],
    *,
    handle_error: bool = True,
) -> Dict[str, Any] | bytes:
    """Send a multipart/form-data POST request.

    ``fields`` is a mapping where each value is either a simple string/bytes or
    a tuple ``(filename, content, ctype)`` for file uploads.
    """

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
            parts.append(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
            )
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
        if handle_error:
            _handle_http_error(e)
        else:
            raise
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(2)


def _handle_http_error(e: HTTPError) -> None:
    body = e.read().decode("utf-8", errors="ignore")
    message = body
    try:
        data = json.loads(body)
        if isinstance(data, dict) and data.get("error"):
            message = data["error"]
    except Exception:
        pass

    if e.code == 401:
        print(f"Authentication failed: {message}", file=sys.stderr)
    elif e.code == 403:
        print(f"Forbidden: {message} (are you an administrator?)", file=sys.stderr)
    else:
        print(f"[HTTP {e.code}] {message}", file=sys.stderr)
    sys.exit(2)

