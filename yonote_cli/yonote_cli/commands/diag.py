"""Diagnostic commands for listing collections and documents."""

from __future__ import annotations

import json

from ..core import get_base_and_token, list_collections, list_documents_in_collection


def cmd_diag_collections(args):
    base, token = get_base_and_token()
    cols = list_collections(
        base,
        token,
        use_cache=False,
        refresh_cache=True,
        workers=getattr(args, "workers", 4),
    )
    print(json.dumps(cols, ensure_ascii=False, indent=2))


def cmd_diag_documents(args):
    base, token = get_base_and_token()
    docs = list_documents_in_collection(
        base,
        token,
        args.collection_id,
        use_cache=False,
        refresh_cache=True,
        workers=getattr(args, "workers", 4),
    )
    print(json.dumps(docs, ensure_ascii=False, indent=2))
