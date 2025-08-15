"""Document related commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..core import (
    API_MAX_LIMIT,
    get_base_and_token,
    fetch_all_concurrent,
    format_rows,
    http_json,
    http_multipart_post,
    load_cache,
    save_cache,
    list_documents_in_collection,
    interactive_select_documents,
    interactive_pick_parent,
    safe_name,
    tqdm,
)


def cmd_docs_list(args):
    base, token = get_base_and_token()
    params: Dict[str, Any] = {}
    if args.collection_id:
        params["collectionId"] = args.collection_id
    items = fetch_all_concurrent(
        base,
        token,
        "/documents.list",
        params=params,
        limit=min(args.limit, API_MAX_LIMIT),
        workers=args.workers,
        desc="Documents",
    )
    rows = [
        {
            "id": it.get("id"),
            "title": it.get("title"),
            "collectionId": it.get("collectionId"),
            "parentDocumentId": it.get("parentDocumentId") or "",
            "urlId": it.get("urlId") or "",
            "updatedAt": it.get("updatedAt") or "",
        }
        for it in items
    ]
    if args.json:
        print(json.dumps({"total": len(rows), "data": rows}, ensure_ascii=False, indent=2))
    else:
        format_rows(rows, ["id", "title", "collectionId", "parentDocumentId", "urlId", "updatedAt"])


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
            base,
            token,
            args.collection_id,
            use_cache=True,
            refresh_cache=args.refresh_cache,
            workers=args.workers,
        )
        picked = interactive_select_documents(docs, multiselect=True)
        ids.extend(picked)

    if args.from_file:
        ids.extend(_read_ids_from_file(Path(args.from_file)))

    seen = set()
    unique_ids: List[str] = []
    for i in ids:
        if i and i not in seen:
            unique_ids.append(i)
            seen.add(i)

    if not unique_ids:
        print(
            "No document IDs provided/selected. Use --interactive with --collection-id or --id/--from-file.",
            file=sys.stderr,
        )
        sys.exit(2)

    ext = args.format if args.format != "markdown" else "md"

    def name_for_id(doc_id: str) -> str:
        if not args.use_titles:
            return f"{doc_id}.{ext}"
        try:
            info = http_json("POST", f"{base}/documents.info", token, {"id": doc_id})
            title = (isinstance(info, dict) and (info.get("data") or {}).get("title")) or None
            safe = safe_name(title or doc_id)
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
        print(f"File not found: {fpath}", file=sys.stderr)
        sys.exit(2)
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
        print(f"Directory not found: {src_dir}", file=sys.stderr)
        sys.exit(2)

    parent_id = args.parent_id
    if args.interactive or parent_id == "__pick__":
        docs = list_documents_in_collection(
            base,
            token,
            args.collection_id,
            use_cache=True,
            refresh_cache=args.refresh_cache,
            workers=args.workers,
        )
        parent_id = interactive_pick_parent(docs, allow_none=True)

    files = _iter_markdown_files(src_dir)
    if not files:
        print("No Markdown files found in the directory.", file=sys.stderr)
        sys.exit(2)

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

    print(
        f"Imported {imported}/{total} files into collection {args.collection_id} (parent={parent_id or 'ROOT'})"
    )
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
            base,
            token,
            "/documents.list",
            params={"collectionId": args.collection_id},
            limit=API_MAX_LIMIT,
            workers=args.workers,
            desc="Fetch docs",
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
        roots = [
            d
            for d in docs
            if not d.get("parentDocumentId") or d.get("parentDocumentId") not in by_id
        ]
        roots.sort(key=lambda x: (x.get("title") or "").lower())

    if args.json:
        def to_node(d: dict, depth: int = 0):
            node = {
                "id": d.get("id"),
                "title": d.get("title"),
                "urlId": d.get("urlId"),
                "updatedAt": d.get("updatedAt"),
                "children": [],
            }
            if args.max_depth and depth >= args.max_depth:
                return node
            for ch in children.get(d.get("id"), []):
                node["children"].append(to_node(ch, depth + 1))
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
            last = i == len(kids) - 1
            branch = "└─ " if last else "├─ "
            print(prefix + branch + line_for(ch))
            more_prefix = prefix + ("   " if last else "│  ")
            render(ch, more_prefix, depth + 1)

    for idx, r in enumerate(roots):
        print(line_for(r))
        render(r, "", 1)
        if idx < len(roots) - 1:
            print()
