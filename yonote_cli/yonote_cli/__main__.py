"""Command line entry point for yonote CLI."""

from __future__ import annotations

import argparse
import os
import sys

# Prefer absolute imports so the module works when bundled with tools like
# PyInstaller.  When the package isn't installed (for example, when running
# directly from a source checkout) fall back to relative imports so tests can

# still invoke it using ``python -m``.  When executed from a PyInstaller bundle
# ``__package__`` is ``None`` which breaks relative imports, so we set it and
# add this file's directory to ``sys.path`` before importing.
try:  # pragma: no cover - exercised indirectly in tests
    from yonote_cli.core import DEFAULT_BASE
    from yonote_cli.commands import (
        cmd_auth_set,
        cmd_auth_info,
        cache_info,
        cache_clear,
        cmd_export,
        cmd_import,
    )
except ModuleNotFoundError:  # pragma: no cover
    if __package__ in (None, ""):
        sys.path.append(os.path.dirname(__file__))
        __package__ = "yonote_cli"
    from .core import DEFAULT_BASE
    from .commands import (
        cmd_auth_set,
        cmd_auth_info,
        cache_info,
        cache_clear,
        cmd_export,
        cmd_import,
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
    p_exp.add_argument("--workers", type=int, default=4, help="Parallel workers")
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

    # import
    p_imp = sub.add_parser("import", help="Import Markdown files into Yonote")
    p_imp.add_argument("--src-dir", required=True, help="Directory with .md files")
    p_imp.add_argument("--workers", type=int, default=4, help="Parallel workers")
    p_imp.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Ignore cache and refetch collections/documents",
    )
    p_imp.set_defaults(func=cmd_import)


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
