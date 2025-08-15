import argparse, json, os, sys, uuid, mimetypes
from pathlib import Path
from typing import Any, Dict
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CONFIG_PATH = Path(os.path.expanduser("~")) / ".yonote.json"
DEFAULT_BASE = "https://practicum.yonote.ru/api"

# ---------- utils ----------

def load_config() -> Dict[str, Any]:
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
    cfg = load_config()
    if base_url is not None:
        cfg["base_url"] = base_url.rstrip("/")
    if token is not None:
        cfg["token"] = token
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved config to {CONFIG_PATH}")

def get_base_and_token() -> tuple[str, str]:
    cfg = load_config()
    base = cfg.get("base_url") or DEFAULT_BASE
    token = cfg.get("token")
    if not token:
        print("Missing token. Run: yonote auth set --token <JWT>", file=sys.stderr)
        sys.exit(2)
    return base, token

def http_json(method: str, url: str, token: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any] | bytes:
    headers = {"Accept":"application/json","Authorization":f"Bearer {token}"}
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
        print(f"[HTTP {e.code}] {body}", file=sys.stderr); sys.exit(2)
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr); sys.exit(2)

def http_multipart_post(url: str, token: str, fields: Dict[str, object]) -> Dict[str, Any] | bytes:
    boundary = f"----yonotecli{uuid.uuid4().hex}"
    def to_b(x): return x if isinstance(x,(bytes,bytearray)) else str(x).encode("utf-8")
    parts: list[bytes] = []
    for name, value in (fields or {}).items():
        parts.append(f"--{boundary}\r\n".encode())
        if isinstance(value, tuple):
            filename, content, ctype = value
            if ctype is None:
                import mimetypes as _mt
                ctype = _mt.guess_type(filename)[0] or "application/octet-stream"
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
        "Accept":"application/json",
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
        print(f"[HTTP {e.code}] {body}", file=sys.stderr); sys.exit(2)
    except URLError as e:
        print(f"Network error: {e.reason}", file=sys.stderr); sys.exit(2)

def paginate(base: str, token: str, endpoint: str, *, limit: int = 100, params: Dict[str, Any] | None = None):
    offset = 0
    params = dict(params or {})
    while True:
        params.update({"limit": limit, "offset": offset})
        data = http_json("POST", f"{base}{endpoint}", token, params)  # RPC-style
        yield data
        items = (isinstance(data, dict) and (data.get("data") or data.get("results") or data.get("rows"))) or []
        total = (isinstance(data, dict) and ((data.get("pagination") or {}).get("total") or data.get("total")))
        if total is not None:
            offset += limit
            if offset >= int(total):
                break
        else:
            if len(items) < limit:
                break
            offset += limit

def format_rows(rows, fields):
    if not rows:
        print("(no data)"); return
    widths = [max(len(str(r.get(f, ""))) for r in rows + [dict(zip(fields, fields))]) for f in fields]
    header = " | ".join(f.ljust(w) for f, w in zip(fields, widths))
    sep = "-+-".join("-" * w for w in widths)
    print(header); print(sep)
    for r in rows:
        print(" | ".join(str(r.get(f, "")).ljust(w) for f, w in zip(fields, widths)))

# ---------- commands ----------

def cmd_auth_set(args):
    save_config(args.base_url, args.token)

def cmd_auth_info(_args):
    base, token = get_base_and_token()
    data = http_json("POST", f"{base}/auth.info", token, {})
    print(json.dumps(data, ensure_ascii=False, indent=2))

def cmd_collections_list(args):
    base, token = get_base_and_token()
    rows = []
    for page in paginate(base, token, "/collections.list", limit=args.limit, params={}):
        items = page.get("data") or []
        for it in items:
            rows.append({
                "id": it.get("id"),
                "name": it.get("name"),
                "index": it.get("index"),
                "permission": it.get("permission") or "",
                "createdAt": it.get("createdAt") or "",
                "updatedAt": it.get("updatedAt") or "",
            })
        if len(items) < args.limit:
            break
    if args.json:
        print(json.dumps({"total": len(rows), "data": rows}, ensure_ascii=False, indent=2))
    else:
        format_rows(rows, ["id","name","index","permission","createdAt","updatedAt"])

def cmd_docs_list(args):
    base, token = get_base_and_token()
    params: Dict[str, Any] = {}
    if args.collection_id:
        params["collectionId"] = args.collection_id
    rows = []
    for page in paginate(base, token, "/documents.list", limit=args.limit, params=params):
        items = page.get("data") or []
        for it in items:
            rows.append({
                "id": it.get("id"),
                "title": it.get("title"),
                "collectionId": it.get("collectionId"),
                "parentDocumentId": it.get("parentDocumentId") or "",
                "urlId": it.get("urlId") or "",
                "updatedAt": it.get("updatedAt") or "",
            })
        if len(items) < args.limit:
            break
    if args.json:
        print(json.dumps({"total": len(rows), "data": rows}, ensure_ascii=False, indent=2))
    else:
        format_rows(rows, ["id","title","collectionId","parentDocumentId","urlId","updatedAt"])

def cmd_docs_export(args):
    base, token = get_base_and_token()
    data = http_json("POST", f"{base}/documents.export", token, {"id": args.id})
    content = data.get("data") if isinstance(data, dict) else data
    Path(args.out).write_text(content if isinstance(content, str) else content.decode("utf-8"), encoding="utf-8")
    print(f"Wrote {args.out}")

def cmd_docs_import(args):
    base, token = get_base_and_token()
    fpath = Path(args.file)
    if not fpath.exists():
        print(f"File not found: {fpath}", file=sys.stderr); sys.exit(2)
    fields: Dict[str, object] = {
        "file": (fpath.name, fpath.read_bytes(), "text/markdown"),
        "collectionId": args.collection_id,
    }
    if args.parent_id:
        fields["parentDocumentId"] = args.parent_id
    data = http_multipart_post(f"{base}/documents.import", token, fields)
    print(json.dumps(data, ensure_ascii=False, indent=2))

# ---------- main ----------

def main(argv=None):
    parser = argparse.ArgumentParser(prog="yonote", description="Yonote CLI (import/export)")
    sub = parser.add_subparsers(dest="cmd")

    p_auth = sub.add_parser("auth", help="Authentication")
    sub_auth = p_auth.add_subparsers(dest="auth_cmd")
    p_auth_set = sub_auth.add_parser("set", help="Save base URL and token to ~/.yonote.json")
    p_auth_set.add_argument("--base-url", help=f"Base API URL (default: {DEFAULT_BASE})")
    p_auth_set.add_argument("--token", help="Bearer token (JWT)")
    p_auth_set.set_defaults(func=cmd_auth_set)
    p_auth_info = sub_auth.add_parser("info", help="Show auth info")
    p_auth_info.set_defaults(func=cmd_auth_info)

    p_cols = sub.add_parser("collections", help="Collections")
    sub_cols = p_cols.add_subparsers(dest="cols_cmd")
    p_cols_list = sub_cols.add_parser("list", help="List collections")
    p_cols_list.add_argument("--limit", type=int, default=100, help="Page size")
    p_cols_list.add_argument("--json", action="store_true", help="Raw JSON output")
    p_cols_list.set_defaults(func=cmd_collections_list)

    p_docs = sub.add_parser("documents", help="Documents")
    sub_docs = p_docs.add_subparsers(dest="docs_cmd")
    p_docs_list = sub_docs.add_parser("list", help="List documents")
    p_docs_list.add_argument("--collection-id", help="Filter by collectionId")
    p_docs_list.add_argument("--limit", type=int, default=100, help="Page size")
    p_docs_list.add_argument("--json", action="store_true", help="Raw JSON output")
    p_docs_list.set_defaults(func=cmd_docs_list)
    p_docs_export = sub_docs.add_parser("export", help="Export document to Markdown")
    p_docs_export.add_argument("--id", required=True)
    p_docs_export.add_argument("--out", required=True)
    p_docs_export.set_defaults(func=cmd_docs_export)
    p_docs_import = sub_docs.add_parser("import", help="Import Markdown file")
    p_docs_import.add_argument("--file", required=True)
    p_docs_import.add_argument("--collection-id", required=True)
    p_docs_import.add_argument("--parent-id")
    p_docs_import.set_defaults(func=cmd_docs_import)

    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help(); return 0
    if args.cmd == "auth" and not getattr(args, "auth_cmd", None):
        p_auth.print_help(); return 0
    if args.cmd == "collections" and not getattr(args, "cols_cmd", None):
        p_cols.print_help(); return 0
    if args.cmd == "documents" and not getattr(args, "docs_cmd", None):
        p_docs.print_help(); return 0
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
