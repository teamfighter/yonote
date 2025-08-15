"""Collection related commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..core import (
    API_MAX_LIMIT,
    get_base_and_token,
    fetch_all_concurrent,
    format_rows,
    http_json,
    list_documents_in_collection,
    safe_name,
    ensure_text,
    tqdm,
)


def cmd_collections_list(args):
    base, token = get_base_and_token()
    items = fetch_all_concurrent(
        base,
        token,
        "/collections.list",
        params={},
        limit=min(args.limit, API_MAX_LIMIT),
        workers=args.workers,
        desc="Collections",
    )
    rows = [
        {
            "id": it.get("id"),
            "name": it.get("name"),
            "index": it.get("index"),
            "permission": it.get("permission") or "",
            "createdAt": it.get("createdAt") or "",
            "updatedAt": it.get("updatedAt") or "",
        }
        for it in items
    ]
    if args.json:
        print(json.dumps({"total": len(rows), "data": rows}, ensure_ascii=False, indent=2))
    else:
        format_rows(rows, ["id", "name", "index", "permission", "createdAt", "updatedAt"])


def cmd_collections_export(args):
    base, token = get_base_and_token()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    docs = list_documents_in_collection(
        base,
        token,
        args.collection_id,
        use_cache=not args.refresh_cache,
        refresh_cache=args.refresh_cache,
        workers=args.workers,
    )
    if not docs:
        print("No documents found in the collection.")
        return

    by_id = {d.get("id"): d for d in docs}
    ext = args.format if args.format != "markdown" else "md"

    def build_path(doc: dict) -> Path:
        title = safe_name(doc.get("title") or doc.get("id"))
        if not args.tree:
            return out_dir / f"{title}.{ext}"
        parts = [f"{title}.{ext}"]
        seen = set()
        cur = doc
        while True:
            pid = cur.get("parentDocumentId")
            if not pid or pid in seen:
                break
            seen.add(pid)
            parent = by_id.get(pid)
            if not parent:
                break
            parts.insert(0, safe_name(parent.get("title") or parent.get("id")))
            cur = parent
        return out_dir.joinpath(*parts)

    def export_one(doc: dict) -> Tuple[str, str | None]:
        doc_id = doc.get("id")
        if not doc_id:
            return ("", "missing id")
        data = http_json("POST", f"{base}/documents.export", token, {"id": doc_id})
        content = data.get("data") if isinstance(data, dict) else data
        text = ensure_text(content)
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
