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
    cmd_export,
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

    # unified export
    p_exp = sub.add_parser("export", help="Interactive export of documents/collections")
    p_exp.add_argument("--out-dir", required=True, help="Output directory")
    p_exp.add_argument("--workers", type=int, default=8, help="Parallel workers")
    p_exp.add_argument(
        "--format",
        choices=["md", "markdown", "html", "json"],
        default="md",
        help="Export format (API returns Markdown by default)",
    )
    p_exp.add_argument(
        "--use-ids",
        action="store_true",
        help="Name files by document/collection IDs instead of titles",
    )
    p_exp.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore cache and refetch collections/documents",
    )
    p_exp.set_defaults(func=cmd_export)


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
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
