"""Unified export command with interactive navigation."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from ..core import (
    get_base_and_token,
    list_collections,
    list_documents_in_collection,
    interactive_browse_for_export,
    export_document_content,
    safe_name,
    tqdm,
    http_json,
)


def cmd_export(args):
    base, token = get_base_and_token()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # pick docs/collections interactively
    doc_ids, col_ids = interactive_browse_for_export(
        base,
        token,
        workers=args.workers,
        refresh_cache=args.refresh_cache,
    )

    # include documents from selected collections
    collections = list_collections(
        base,
        token,
        use_cache=True,
        refresh_cache=args.refresh_cache,
        workers=args.workers,
    )
    cols_by_id = {c.get("id"): c for c in collections}
    all_ids = set(doc_ids)
    for cid in col_ids:
        docs = list_documents_in_collection(
            base,
            token,
            cid,
            use_cache=True,
            refresh_cache=args.refresh_cache,
            workers=args.workers,
        )
        for d in docs:
            did = d.get("id")
            if did:
                all_ids.add(did)

    if not all_ids:
        print("Ничего не выбрано для экспорта")
        return

    ext = args.format if args.format != "markdown" else "md"
    info_cache: Dict[str, dict] = {}

    def get_info(doc_id: str) -> dict:
        if doc_id not in info_cache:
            try:
                data = http_json("POST", f"{base}/documents.info", token, {"id": doc_id})
                info_cache[doc_id] = data.get("data") if isinstance(data, dict) else {}
            except Exception:
                info_cache[doc_id] = {}
        return info_cache.get(doc_id, {})

    def build_path(doc_id: str) -> Path:
        info = get_info(doc_id)
        if args.use_ids:
            name = doc_id
        else:
            name = safe_name(info.get("title") or "(без названия)")
        parts = [f"{name}.{ext}"]
        seen = {doc_id}
        cur = info
        while True:
            pid = cur.get("parentDocumentId")
            if not pid or pid in seen:
                break
            seen.add(pid)
            parent = get_info(pid)
            if not parent:
                break
            if args.use_ids:
                seg = pid
            else:
                seg = safe_name(parent.get("title") or "(без названия)")
            parts.insert(0, seg)
            cur = parent
        coll = cols_by_id.get(info.get("collectionId"), {})
        coll_name = info.get("collectionId") if args.use_ids else safe_name(
            coll.get("name") or "(без названия)"
        )
        parts.insert(0, coll_name)
        return out_dir.joinpath(*parts)

    def export_one(doc_id: str) -> Tuple[str, str | None]:
        try:
            text = export_document_content(base, token, doc_id)
            path = build_path(doc_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            return (str(path), None)
        except Exception as e:
            return ("", str(e))

    total = len(all_ids)
    errors: List[Tuple[str, str]] = []
    written = 0
    with tqdm(total=total, unit="doc", desc="Exporting") as bar:
        for doc_id in all_ids:
            path, err = export_one(doc_id)
            if err:
                errors.append((doc_id, err))
            else:
                written += 1
            bar.update(1)

    print(f"Exported {written}/{total} documents to {out_dir}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for did, err in errors[:10]:
            print(f"  {did}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more")
