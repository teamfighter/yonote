"""Command line entry point for yonote CLI."""

from __future__ import annotations

import argparse
import sys

from .core import DEFAULT_BASE
from .commands import (
    cmd_auth_set,
    cmd_auth_info,
    cache_info,
    cache_clear,
    cmd_collections_list,
    cmd_collections_export,
    cmd_docs_list,
    cmd_docs_export,
    cmd_docs_export_batch,
    cmd_docs_import,
    cmd_docs_import_dir,
    cmd_docs_tree,
)


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
    p_cols_export.add_argument(
        "--format",
        choices=["md", "markdown", "html", "json"],
        default="md",
        help="Export format (API returns Markdown by default)",
    )
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
    p_docs_export_batch.add_argument(
        "--interactive",
        action="store_true",
        help="Interactively select documents from a collection",
    )
    p_docs_export_batch.add_argument("--collection-id", help="Collection used for interactive selection")
    p_docs_export_batch.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Refresh cache before interactive selection",
    )
    p_docs_export_batch.add_argument("--out-dir", required=True, help="Output directory")
    p_docs_export_batch.add_argument("--workers", type=int, default=8, help="Parallel workers")
    p_docs_export_batch.add_argument(
        "--format",
        choices=["md", "markdown", "html", "json"],
        default="md",
        help="Export format (API returns Markdown by default)",
    )
    p_docs_export_batch.add_argument(
        "--use-titles",
        action="store_true",
        help="Name files by document titles (extra API call per id)",
    )
    p_docs_export_batch.set_defaults(func=cmd_docs_export_batch)

    p_docs_import = sub_docs.add_parser("import", help="Import a Markdown file as a document")
    p_docs_import.add_argument("--file", required=True, help="Markdown file path")
    p_docs_import.add_argument("--collection-id", required=True, help="Target collection UUID")
    p_docs_import.add_argument("--parent-id", help="Parent document UUID")
    p_docs_import.set_defaults(func=cmd_docs_import)

    p_docs_import_dir = sub_docs.add_parser(
        "import-dir", help="Import a directory of Markdown files (recursively)"
    )
    p_docs_import_dir.add_argument("--dir", required=True, help="Directory with .md files")
    p_docs_import_dir.add_argument("--collection-id", required=True, help="Target collection UUID")
    p_docs_import_dir.add_argument("--parent-id", help="Parent document UUID (or use --interactive)")
    p_docs_import_dir.add_argument("--interactive", action="store_true", help="Pick parent interactively")
    p_docs_import_dir.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Refresh cache before interactive parent picking",
    )
    p_docs_import_dir.add_argument("--workers", type=int, default=8, help="Parallel workers")
    p_docs_import_dir.set_defaults(func=cmd_docs_import_dir)

    p_docs_tree = sub_docs.add_parser("tree", help="Print document tree of a collection")
    p_docs_tree.add_argument("--collection-id", required=True, help="Collection UUID")
    p_docs_tree.add_argument(
        "--root-id",
        help="Start from a specific document id (otherwise show all roots)",
    )
    p_docs_tree.add_argument("--max-depth", type=int, help="Limit depth of the tree")
    p_docs_tree.add_argument("--show-ids", action="store_true", help="Show document ids next to titles")
    p_docs_tree.add_argument("--json", action="store_true", help="Output as JSON instead of ASCII tree")
    p_docs_tree.add_argument(
        "--refresh-cache", action="store_true", help="Ignore cache and refetch structure"
    )
    p_docs_tree.add_argument("--workers", type=int, default=8, help="Parallel workers for API paging")
    p_docs_tree.set_defaults(func=cmd_docs_tree)

    args = parser.parse_args(argv)

    if not args.cmd:
        parser.print_help()
        return 0
    if args.cmd == "auth" and not getattr(args, "auth_cmd", None):
        p_auth.print_help()
        return 0
    if args.cmd == "cache" and not getattr(args, "cache_cmd", None):
        p_cache.print_help()
        return 0
    if args.cmd == "collections" and not getattr(args, "cols_cmd", None):
        p_cols.print_help()
        return 0
    if args.cmd == "documents" and not getattr(args, "docs_cmd", None):
        p_docs.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
