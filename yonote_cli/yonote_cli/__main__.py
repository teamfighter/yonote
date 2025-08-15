import argparse, json, os, sys, uuid, mimetypes, re
from pathlib import Path
from typing import Any, Dict, Tuple, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- progress (tqdm) ---
try:
    from tqdm import tqdm
except Exception:  # fallback
    class tqdm:  # type: ignore
        def __init__(self, *a, **kw): self.n=0
        def update(self, x=1): self.n+=x
        def set_postfix(self, **kw): pass
        def close(self): pass
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): self.close()

# --- interactive (InquirerPy) ---
try:
    from InquirerPy import inquirer
    HAVE_INQUIRER = True
except Exception:
    HAVE_INQUIRER = False

CONFIG_PATH = Path(os.path.expanduser("~")) / ".yonote.json"
CACHE_PATH  = Path(os.path.expanduser("~")) / ".yonote-cache.json"
DEFAULT_BASE = "https://practicum.yonote.ru/api"
API_MAX_LIMIT = 100  # лимит API для limit

# ---------- basic utils ----------

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

def get_base_and_token() -> Tuple[str, str]:
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

# ---------- dynamic concurrent pagination (no total needed) ----------

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
    desc: str = "Loading"
) -> List[dict]:
    """Качаем первую страницу; если полная — продолжаем батчами по workers, пока не встретим короткую страницу."""
    limit = min(limit, API_MAX_LIMIT)
    params = dict(params or {})

    # первая страница
    first = _post_page(base, token, endpoint, params, limit, 0)
    items = list(first.get("data") or [])
    n_first = len(items)

    # если короткая — всё
    if n_first < limit:
        with tqdm(total=1, unit="pg", desc=desc) as bar:
            bar.update(1)
        return items

    # иначе батчи по workers
    results: List[dict] = items
    next_offset = limit
    with tqdm(total=None, unit="pg", desc=desc) as bar:
        bar.update(1)  # первая страница
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

# ---------- table formatting ----------

def format_rows(rows: List[Dict[str, Any]], fields: List[str]):
    if not rows:
        print("(no data)")
        return
    widths = [max(len(str(r.get(f, ""))) for r in rows + [dict(zip(fields, fields))]) for f in fields]
    header = " | ".join(f.ljust(w) for f, w in zip(fields, widths))
    sep = "-+-".join("-" * w for w in widths)
    print(header); print(sep)
    for r in rows:
        print(" | ".join(str(r.get(f, "")).ljust(w) for f, w in zip(fields, widths)))

def _safe_name(name: str, maxlen: int = 120) -> str:
    name = (name or "").strip()
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name)
    if len(name) > maxlen:
        name = name[:maxlen].rstrip()
    return name or "untitled"

# ---------- cache utils ----------

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

def list_documents_in_collection(base: str, token: str, collection_id: str, *, use_cache: bool, refresh_cache: bool, workers: int) -> List[dict]:
    cache = load_cache() if use_cache else {}
    coll_key = f"collection:{collection_id}"
    if use_cache and not refresh_cache and coll_key in cache:
        return cache[coll_key]
    docs = fetch_all_concurrent(
        base, token, "/documents.list",
        params={"collectionId": collection_id},
        limit=API_MAX_LIMIT,
        workers=workers,
        desc="Fetch docs"
    )
    if use_cache:
        cache[coll_key] = docs
        save_cache(cache)
    return docs

# ---------- interactive helpers ----------

def _build_breadcrumbs(doc: dict, by_id: Dict[str, dict]) -> str:
    parts = [doc.get("title") or "(untitled)"]
    seen = set(); cur = doc
    while True:
        pid = cur.get("parentDocumentId")
        if not pid or pid in seen:
            break
        seen.add(pid)
        p = by_id.get(pid)
        if not p:
            break
        parts.insert(0, p.get("title") or "(untitled)")
        cur = p
    return " / ".join(parts)

def interactive_select_documents(docs: List[dict], multiselect: bool = True) -> List[str]:
    if not HAVE_INQUIRER:
        print("Interactive mode requires InquirerPy. Install:\n  pip install InquirerPy", file=sys.stderr)
        sys.exit(2)
    by_id = {d.get("id"): d for d in docs}
    choices = []
    for d in docs:
        bc = _build_breadcrumbs(d, by_id)
        label = f"{bc}  [{d.get('id')}]"
        choices.append({"name": label, "value": d.get("id")})
    choices.sort(key=lambda x: x["name"].lower())
    if multiselect:
        result = inquirer.checkbox(
            message="Выберите документы (Space — выбрать, Enter — подтвердить):",
            choices=choices,
            instruction="↑/↓, PgUp/PgDn, Search: /",
            transformer=lambda res: f"{len(res)} selected",
            height="90%",
            validate=lambda ans: (len(ans) > 0) or "Нужно выбрать хотя бы один документ",
        ).execute()
        return list(result or [])
    else:
        result = inquirer.select(
            message="Выберите документ:",
            choices=choices,
            instruction="↑/↓, Search: /",
            height="90%",
        ).execute()
        return [result] if result else []

def interactive_pick_parent(docs: List[dict], allow_none: bool = True) -> Optional[str]:
    if not HAVE_INQUIRER:
        print("Interactive mode requires InquirerPy. Install:\n  pip install InquirerPy", file=sys.stderr)
        sys.exit(2)
    by_id = {d.get("id"): d for d in docs}
    choices = []
    if allow_none:
        choices.append({"name": "(no parent) — в корень коллекции", "value": None})
    for d in docs:
        bc = _build_breadcrumbs(d, by_id)
        label = f"{bc}  [{d.get('id')}]"
        choices.append({"name": label, "value": d.get("id")})
    choices.sort(key=lambda x: (x["name"] or "").lower())
    parent = inquirer.select(
        message="Куда импортировать (родительский документ)?",
        choices=choices,
        instruction="↑/↓, Search: /",
        height="90%",
    ).execute()
    return parent

# ---------- cache commands ----------

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

# ---------- commands: auth ----------

def cmd_auth_set(args):
    save_config(args.base_url, args.token)

def cmd_auth_info(_args):
    base, token = get_base_and_token()
    data = http_json("POST", f"{base}/auth.info", token, {})
    print(json.dumps(data, ensure_ascii=False, indent=2))

# ---------- commands: collections ----------

def cmd_collections_list(args):
    base, token = get_base_and_token()
    items = fetch_all_concurrent(
        base, token, "/collections.list",
        params={}, limit=min(args.limit, API_MAX_LIMIT),
        workers=args.workers, desc="Collections"
    )
    rows = [{
        "id": it.get("id"),
        "name": it.get("name"),
        "index": it.get("index"),
        "permission": it.get("permission") or "",
        "createdAt": it.get("createdAt") or "",
        "updatedAt": it.get("updatedAt") or "",
    } for it in items]
    if args.json:
        print(json.dumps({"total": len(rows), "data": rows}, ensure_ascii=False, indent=2))
    else:
        format_rows(rows, ["id","name","index","permission","createdAt","updatedAt"])

def cmd_collections_export(args):
    base, token = get_base_and_token()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = list_documents_in_collection(
        base, token, args.collection_id,
        use_cache=not args.refresh_cache,
        refresh_cache=args.refresh_cache,
        workers=args.workers
    )
    if not docs:
        print("No documents found in the collection.")
        return

    by_id = {d.get("id"): d for d in docs}
    ext = args.format if args.format != "markdown" else "md"

    def build_path(doc: dict) -> Path:
        title = _safe_name(doc.get("title") or doc.get("id"))
        if not args.tree:
            return out_dir / f"{title}.{ext}"
        parts = [f"{title}.{ext}"]
        seen = set(); cur = doc
        while True:
            pid = cur.get("parentDocumentId")
            if not pid or pid in seen:
                break
            seen.add(pid)
            parent = by_id.get(pid)
            if not parent:
                break
            parts.insert(0, _safe_name(parent.get("title") or parent.get("id")))
            cur = parent
        return out_dir.joinpath(*parts)

    def export_one(doc: dict) -> Tuple[str, str | None]:
        doc_id = doc.get("id")
        if not doc_id:
            return ("", "missing id")
        data = http_json("POST", f"{base}/documents.export", token, {"id": doc_id})
        content = data.get("data") if isinstance(data, dict) else data
        text = content if isinstance(content, str) else content.decode("utf-8")
        path = build_path(doc)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return (str(path), None)

    total = len(docs)
    errors: List[Tuple[str, str]] = []
    written = 0

    with tqdm(total=total, unit="doc", desc="Exporting") as bar, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(export_one, d): d for d in docs}
        for fut in as_completed(futures):
            d = futures[fut]
            try:
                path, err = fut.result()
                if err:
                    errors.append((d.get("id"), err))
                else:
                    written += 1
            except Exception as e:
                errors.append((d.get("id"), str(e)))
            finally:
                bar.update(1)

    print(f"Exported {written}/{total} documents to {out_dir}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for doc_id, err in errors[:10]:
            print(f"  {doc_id}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more")

# ---------- commands: documents ----------

def cmd_docs_list(args):
    base, token = get_base_and_token()
    params: Dict[str, Any] = {}
    if args.collection_id:
        params["collectionId"] = args.collection_id
    items = fetch_all_concurrent(
        base, token, "/documents.list",
        params=params, limit=min(args.limit, API_MAX_LIMIT),
        workers=args.workers, desc="Documents"
    )
    rows = [{
        "id": it.get("id"),
        "title": it.get("title"),
        "collectionId": it.get("collectionId"),
        "parentDocumentId": it.get("parentDocumentId") or "",
        "urlId": it.get("urlId") or "",
        "updatedAt": it.get("updatedAt") or "",
    } for it in items]
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

def _read_ids_from_file(path: Path) -> List[str]:
    ids: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        ids.append(s)
    return ids

def cmd_docs_export_batch(args):
    base, token = get_base_and_token()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    ids: List[str] = []
    ids.extend(args.id or [])

    if args.interactive:
        if not args.collection_id:
            print("Interactive export requires --collection-id.", file=sys.stderr)
            sys.exit(2)
        docs = list_documents_in_collection(
            base, token, args.collection_id,
            use_cache=True, refresh_cache=args.refresh_cache, workers=args.workers
        )
        picked = interactive_select_documents(docs, multiselect=True)
        ids.extend(picked)

    if args.from_file:
        ids.extend(_read_ids_from_file(Path(args.from_file)))

    # dedup preserving order
    seen = set(); unique_ids = []
    for i in ids:
        if i and i not in seen:
            unique_ids.append(i); seen.add(i)

    if not unique_ids:
        print("No document IDs provided/selected. Use --interactive with --collection-id or --id/--from-file.", file=sys.stderr)
        sys.exit(2)

    ext = args.format if args.format != "markdown" else "md"

    def name_for_id(doc_id: str) -> str:
        if not args.use_titles:
            return f"{doc_id}.{ext}"
        try:
            info = http_json("POST", f"{base}/documents.info", token, {"id": doc_id})
            title = (isinstance(info, dict) and (info.get("data") or {}).get("title")) or None
            safe = _safe_name(title or doc_id)
            return f"{safe}.{ext}"
        except SystemExit:
            raise
        except Exception:
            return f"{doc_id}.{ext}"

    def export_one(doc_id: str) -> Tuple[str, str | None]:
        data = http_json("POST", f"{base}/documents.export", token, {"id": doc_id})
        content = data.get("data") if isinstance(data, dict) else data
        text = content if isinstance(content, str) else content.decode("utf-8")
        fname = name_for_id(doc_id)
        path = out_dir / fname
        path.write_text(text, encoding="utf-8")
        return (str(path), None)

    total = len(unique_ids)
    errors: List[Tuple[str, str]] = []
    written = 0

    with tqdm(total=total, unit="doc", desc="Exporting") as bar, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(export_one, d_id): d_id for d_id in unique_ids}
        for fut in as_completed(futures):
            d_id = futures[fut]
            try:
                path, err = fut.result()
                if err:
                    errors.append((d_id, err))
                else:
                    written += 1
            except Exception as e:
                errors.append((d_id, str(e)))
            finally:
                bar.update(1)

    print(f"Exported {written}/{total} documents to {out_dir}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for doc_id, err in errors[:10]:
            print(f"  {doc_id}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more")

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

def _iter_markdown_files(root: Path) -> List[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".md", ".markdown")]

def cmd_docs_import_dir(args):
    base, token = get_base_and_token()
    src_dir = Path(args.dir).resolve()
    if not src_dir.exists() or not src_dir.is_dir():
        print(f"Directory not found: {src_dir}", file=sys.stderr); sys.exit(2)

    parent_id = args.parent_id
    if args.interactive or parent_id == "__pick__":
        docs = list_documents_in_collection(
            base, token, args.collection_id,
            use_cache=True, refresh_cache=args.refresh_cache, workers=args.workers
        )
        parent_id = interactive_pick_parent(docs, allow_none=True)

    files = _iter_markdown_files(src_dir)
    if not files:
        print("No Markdown files found in the directory.", file=sys.stderr); sys.exit(2)

    def import_one(path: Path) -> Tuple[str, Optional[str]]:
        rel = path.relative_to(src_dir).as_posix()
        fields: Dict[str, object] = {
            "file": (path.name, path.read_bytes(), "text/markdown"),
            "collectionId": args.collection_id,
        }
        if parent_id:
            fields["parentDocumentId"] = parent_id
        data = http_multipart_post(f"{base}/documents.import", token, fields)
        ok = isinstance(data, dict) and data.get("ok") is True
        return (rel, None if ok else json.dumps(data, ensure_ascii=False))

    total = len(files)
    errors: List[Tuple[str, str]] = []
    imported = 0

    with tqdm(total=total, unit="file", desc="Importing") as bar, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(import_one, p): p for p in files}
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                rel, err = fut.result()
                if err:
                    errors.append((rel, err))
                else:
                    imported += 1
            except Exception as e:
                errors.append((p.name, str(e)))
            finally:
                bar.update(1)

    print(f"Imported {imported}/{total} files into collection {args.collection_id} (parent={parent_id or 'ROOT'})")
    if errors:
        print(f"Errors ({len(errors)}):")
        for rel, err in errors[:10]:
            print(f"  {rel}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more")

def cmd_docs_tree(args):
    base, token = get_base_and_token()

    docs: List[dict] = []
    use_cache = not getattr(args, "refresh_cache", False)
    if use_cache:
        cache = load_cache()
        coll_key = f"collection:{args.collection_id}"
        if coll_key in cache:
            docs = cache[coll_key]

    if not docs:
        docs = fetch_all_concurrent(
            base, token, "/documents.list",
            params={"collectionId": args.collection_id},
            limit=API_MAX_LIMIT,
            workers=args.workers,
            desc="Fetch docs"
        )
        cache = load_cache()
        cache[f"collection:{args.collection_id}"] = docs
        save_cache(cache)

    if not docs:
        print("No documents in collection.")
        return

    by_id = {d.get("id"): d for d in docs}
    children: Dict[str | None, List[dict]] = {}
    with tqdm(total=len(docs), unit="doc", desc="Indexing") as bar:
        for d in docs:
            pid = d.get("parentDocumentId")
            children.setdefault(pid, []).append(d)
            bar.update(1)

    for k in list(children.keys()):
        children[k].sort(key=lambda x: (x.get("title") or "").lower())

    if args.root_id:
        root = by_id.get(args.root_id)
        if not root:
            print(f"Root id not found in this collection: {args.root_id}", file=sys.stderr)
            sys.exit(2)
        roots = [root]
    else:
        roots = [d for d in docs if not d.get("parentDocumentId") or d.get("parentDocumentId") not in by_id]
        roots.sort(key=lambda x: (x.get("title") or "").lower())

    if args.json:
        def to_node(d: dict, depth: int = 0):
            node = {
                "id": d.get("id"),
                "title": d.get("title"),
                "urlId": d.get("urlId"),
                "updatedAt": d.get("updatedAt"),
                "children": []
            }
            if args.max_depth and depth >= args.max_depth:
                return node
            for ch in children.get(d.get("id"), []):
                node["children"].append(to_node(ch, depth+1))
            return node
        data = [to_node(r) for r in roots]
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    def line_for(d: dict) -> str:
        title = d.get("title") or "(untitled)"
        if args.show_ids:
            return f"{title}  [{d.get('id')}]"
        return title

    def render(d: dict, prefix: str, depth: int):
        kids = children.get(d.get("id"), [])
        if args.max_depth and depth >= args.max_depth:
            kids = []
        for i, ch in enumerate(kids):
            last = (i == len(kids) - 1)
            branch = "└─ " if last else "├─ "
            print(prefix + branch + line_for(ch))
            more_prefix = prefix + ("   " if last else "│  ")
            render(ch, more_prefix, depth + 1)

    for idx, r in enumerate(roots):
        print(line_for(r))
        render(r, "", 1)
        if idx < len(roots) - 1:
            print()

# ---------- main ----------

def main(argv=None):
    parser = argparse.ArgumentParser(prog="yonote", description="Yonote CLI (import/export)")
    sub = parser.add_subparsers(dest="cmd")

    # auth
    p_auth = sub.add_parser("auth", help="Authentication")
    sub_auth = p_auth.add_subparsers(dest="auth_cmd")

    p_auth_set = sub_auth.add_parser("set", help="Save base URL and token to ~/.yonote.json")
    p_auth_set.add_argument("--base-url", help=f"Base API URL (default: {DEFAULT_BASE})")
    p_auth_set.add_argument("--token", help="Bearer token (JWT)")
    p_auth_set.set_defaults(func=cmd_auth_set)

    p_auth_info = sub_auth.add_parser("info", help="Show auth info")
    p_auth_info.set_defaults(func=cmd_auth_info)

    # cache utils
    p_cache = sub.add_parser("cache", help="Cache utilities")
    sub_cache = p_cache.add_subparsers(dest="cache_cmd")
    p_cache_info = sub_cache.add_parser("info", help="Show cache location and summary")
    p_cache_info.set_defaults(func=cache_info)
    p_cache_clear = sub_cache.add_parser("clear", help="Delete cache file")
    p_cache_clear.set_defaults(func=cache_clear)

    # collections
    p_cols = sub.add_parser("collections", help="Collections")
    sub_cols = p_cols.add_subparsers(dest="cols_cmd")

    p_cols_list = sub_cols.add_parser("list", help="List collections")
    p_cols_list.add_argument("--limit", type=int, default=100, help="Page size")
    p_cols_list.add_argument("--workers", type=int, default=8, help="Parallel workers for API paging")
    p_cols_list.add_argument("--json", action="store_true", help="Raw JSON output")
    p_cols_list.set_defaults(func=cmd_collections_list)

    p_cols_export = sub_cols.add_parser("export", help="Export all documents in a collection")
    p_cols_export.add_argument("--collection-id", required=True, help="Collection UUID")
    p_cols_export.add_argument("--out", required=True, help="Output directory")
    p_cols_export.add_argument("--format", choices=["md","markdown","html","json"], default="md", help="Export format (API returns Markdown by default)")
    p_cols_export.add_argument("--workers", type=int, default=8, help="Parallel workers for API + file writes")
    p_cols_export.add_argument("--tree", action="store_true", help="Reconstruct folder tree by parentDocumentId")
    p_cols_export.add_argument("--refresh-cache", action="store_true", help="Ignore cache and refetch structure")
    p_cols_export.set_defaults(func=cmd_collections_export)

    # documents
    p_docs = sub.add_parser("documents", help="Documents")
    sub_docs = p_docs.add_subparsers(dest="docs_cmd")

    p_docs_list = sub_docs.add_parser("list", help="List documents")
    p_docs_list.add_argument("--collection-id", help="Filter by collectionId")
    p_docs_list.add_argument("--limit", type=int, default=100, help="Page size")
    p_docs_list.add_argument("--workers", type=int, default=8, help="Parallel workers for API paging")
    p_docs_list.add_argument("--json", action="store_true", help="Raw JSON output")
    p_docs_list.set_defaults(func=cmd_docs_list)

    p_docs_export = sub_docs.add_parser("export", help="Export a document to Markdown")
    p_docs_export.add_argument("--id", required=True, help="Document id")
    p_docs_export.add_argument("--out", required=True, help="Output file path (.md)")
    p_docs_export.set_defaults(func=cmd_docs_export)

    p_docs_export_batch = sub_docs.add_parser("export-batch", help="Export multiple documents")
    p_docs_export_batch.add_argument("--id", action="append", help="Document id (use multiple times)", default=[])
    p_docs_export_batch.add_argument("--from-file", help="Path to file with one document id per line")
    p_docs_export_batch.add_argument("--interactive", action="store_true", help="Interactively select documents from a collection")
    p_docs_export_batch.add_argument("--collection-id", help="Collection used for interactive selection")
    p_docs_export_batch.add_argument("--refresh-cache", action="store_true", help="Refresh cache before interactive selection")
    p_docs_export_batch.add_argument("--out-dir", required=True, help="Output directory")
    p_docs_export_batch.add_argument("--workers", type=int, default=8, help="Parallel workers")
    p_docs_export_batch.add_argument("--format", choices=["md","markdown","html","json"], default="md", help="Export format (API returns Markdown by default)")
    p_docs_export_batch.add_argument("--use-titles", action="store_true", help="Name files by document titles (extra API call per id)")
    p_docs_export_batch.set_defaults(func=cmd_docs_export_batch)

    p_docs_import = sub_docs.add_parser("import", help="Import a Markdown file as a document")
    p_docs_import.add_argument("--file", required=True, help="Markdown file path")
    p_docs_import.add_argument("--collection-id", required=True, help="Target collection UUID")
    p_docs_import.add_argument("--parent-id", help="Parent document UUID")
    p_docs_import.set_defaults(func=cmd_docs_import)

    p_docs_import_dir = sub_docs.add_parser("import-dir", help="Import a directory of Markdown files (recursively)")
    p_docs_import_dir.add_argument("--dir", required=True, help="Directory with .md files")
    p_docs_import_dir.add_argument("--collection-id", required=True, help="Target collection UUID")
    p_docs_import_dir.add_argument("--parent-id", help="Parent document UUID (or use --interactive)")
    p_docs_import_dir.add_argument("--interactive", action="store_true", help="Pick parent interactively")
    p_docs_import_dir.add_argument("--refresh-cache", action="store_true", help="Refresh cache before interactive parent picking")
    p_docs_import_dir.add_argument("--workers", type=int, default=8, help="Parallel workers")
    p_docs_import_dir.set_defaults(func=cmd_docs_import_dir)

    p_docs_tree = sub_docs.add_parser("tree", help="Print document tree of a collection")
    p_docs_tree.add_argument("--collection-id", required=True, help="Collection UUID")
    p_docs_tree.add_argument("--root-id", help="Start from a specific document id (otherwise show all roots)")
    p_docs_tree.add_argument("--max-depth", type=int, help="Limit depth of the tree")
    p_docs_tree.add_argument("--show-ids", action="store_true", help="Show document ids next to titles")
    p_docs_tree.add_argument("--json", action="store_true", help="Output as JSON instead of ASCII tree")
    p_docs_tree.add_argument("--refresh-cache", action="store_true", help="Ignore cache and refetch structure")
    p_docs_tree.add_argument("--workers", type=int, default=8, help="Parallel workers for API paging")
    p_docs_tree.set_defaults(func=cmd_docs_tree)

    args = parser.parse_args(argv)

    if not args.cmd:
        parser.print_help(); return 0
    if args.cmd == "auth" and not getattr(args, "auth_cmd", None):
        p_auth.print_help(); return 0
    if args.cmd == "cache" and not getattr(args, "cache_cmd", None):
        p_cache.print_help(); return 0
    if args.cmd == "collections" and not getattr(args, "cols_cmd", None):
        p_cols.print_help(); return 0
    if args.cmd == "documents" and not getattr(args, "docs_cmd", None):
        p_docs.print_help(); return 0
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
