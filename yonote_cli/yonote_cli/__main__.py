"""Command line entry point for yonote CLI."""

from __future__ import annotations

import argparse
import os
import sys

# Prefer absolute imports so the module works when installed as a package.
# When running directly from a source checkout fall back to relative imports so
# tests can invoke it using ``python -m``. If ``__package__`` is ``None`` we set
# it and add this file's directory to ``sys.path`` before importing.
try:  # pragma: no cover - exercised indirectly in tests
    from yonote_cli.core import DEFAULT_BASE
    from yonote_cli.commands import (
        cmd_auth_set,
        cmd_auth_info,
        cache_info,
        cache_clear,
        cmd_export,
        cmd_import,
        cmd_admin_users_list,
        cmd_admin_users_info,
        cmd_admin_users_update,
        cmd_admin_users_promote,
        cmd_admin_users_demote,
        cmd_admin_users_suspend,
        cmd_admin_users_activate,
        cmd_admin_users_delete,
        cmd_admin_groups_list,
        cmd_admin_groups_create,
        cmd_admin_groups_update,
        cmd_admin_groups_delete,
        cmd_admin_groups_memberships,
        cmd_admin_groups_add_user,
        cmd_admin_groups_remove_user,
        cmd_admin_collections_add_user,
        cmd_admin_collections_remove_user,
        cmd_admin_collections_memberships,
        cmd_admin_collections_add_group,
        cmd_admin_collections_remove_group,
        cmd_admin_collections_group_memberships,
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
        cmd_admin_users_list,
        cmd_admin_users_info,
        cmd_admin_users_update,
        cmd_admin_users_promote,
        cmd_admin_users_demote,
        cmd_admin_users_suspend,
        cmd_admin_users_activate,
        cmd_admin_users_delete,
        cmd_admin_groups_list,
        cmd_admin_groups_create,
        cmd_admin_groups_update,
        cmd_admin_groups_delete,
        cmd_admin_groups_memberships,
        cmd_admin_groups_add_user,
        cmd_admin_groups_remove_user,
        cmd_admin_collections_add_user,
        cmd_admin_collections_remove_user,
        cmd_admin_collections_memberships,
        cmd_admin_collections_add_group,
        cmd_admin_collections_remove_group,
        cmd_admin_collections_group_memberships,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="yonote", description="Yonote CLI")
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
    p_exp.add_argument("--workers", type=int, default=20, help="Parallel workers")
    p_exp.add_argument("--use-ids", action="store_true", help="Name files by document/collection IDs instead of titles")
    p_exp.add_argument("--refresh-cache", action="store_true", help="Ignore cache and refetch collections/documents")
    p_exp.set_defaults(func=cmd_export)

    # import
    p_imp = sub.add_parser("import", help="Import Markdown files into Yonote")
    p_imp.add_argument("--src-dir", required=True, help="Directory with .md files")
    p_imp.add_argument("--workers", type=int, default=20, help="Parallel workers")
    p_imp.add_argument("--refresh-cache", action="store_true", help="Ignore cache and refetch collections/documents")
    p_imp.set_defaults(func=cmd_import)

    # admin
    p_admin = sub.add_parser("admin", help="Administrative operations")
    sub_admin = p_admin.add_subparsers(dest="admin_cmd")

    # admin users
    p_admin_users = sub_admin.add_parser("users", help="Manage users")
    sub_admin_users = p_admin_users.add_subparsers(dest="admin_users_cmd")

    p_admin_users_list = sub_admin_users.add_parser("list", help="List users")
    p_admin_users_list.add_argument("--query")
    p_admin_users_list.set_defaults(func=cmd_admin_users_list)

    p_admin_users_info = sub_admin_users.add_parser("info", help="Show user info")
    p_admin_users_info.add_argument("user", help="User id or email")
    p_admin_users_info.set_defaults(func=cmd_admin_users_info)

    p_admin_users_update = sub_admin_users.add_parser("update", help="Update a user")
    p_admin_users_update.add_argument("user", help="User id or email")
    p_admin_users_update.add_argument("--name")
    p_admin_users_update.add_argument("--email")
    p_admin_users_update.add_argument("--avatar-url")
    p_admin_users_update.set_defaults(func=cmd_admin_users_update)

    for name, func in [
        ("promote", cmd_admin_users_promote),
        ("demote", cmd_admin_users_demote),
        ("suspend", cmd_admin_users_suspend),
        ("activate", cmd_admin_users_activate),
        ("delete", cmd_admin_users_delete),
    ]:
        p = sub_admin_users.add_parser(name, help=f"{name.capitalize()} user(s)")
        p.add_argument("users", nargs="+", help="User ids or emails")
        p.set_defaults(func=func)

    # admin groups
    p_admin_groups = sub_admin.add_parser("groups", help="Manage groups")
    sub_admin_groups = p_admin_groups.add_subparsers(dest="admin_groups_cmd")

    p_ag_list = sub_admin_groups.add_parser("list", help="List groups")
    p_ag_list.set_defaults(func=cmd_admin_groups_list)

    p_ag_create = sub_admin_groups.add_parser("create", help="Create group")
    p_ag_create.add_argument("name")
    p_ag_create.set_defaults(func=cmd_admin_groups_create)

    p_ag_update = sub_admin_groups.add_parser("update", help="Update group")
    p_ag_update.add_argument("group", help="Group id or name")
    p_ag_update.add_argument("name")
    p_ag_update.set_defaults(func=cmd_admin_groups_update)

    p_ag_delete = sub_admin_groups.add_parser("delete", help="Delete group")
    p_ag_delete.add_argument("group")
    p_ag_delete.set_defaults(func=cmd_admin_groups_delete)

    p_ag_memberships = sub_admin_groups.add_parser("memberships", help="List group members")
    p_ag_memberships.add_argument("group")
    p_ag_memberships.add_argument("--query")
    p_ag_memberships.set_defaults(func=cmd_admin_groups_memberships)

    p_ag_add_user = sub_admin_groups.add_parser("add_user", help="Add user to group")
    p_ag_add_user.add_argument("group")
    p_ag_add_user.add_argument("user")
    p_ag_add_user.set_defaults(func=cmd_admin_groups_add_user)

    p_ag_remove_user = sub_admin_groups.add_parser("remove_user", help="Remove user from group")
    p_ag_remove_user.add_argument("group")
    p_ag_remove_user.add_argument("user")
    p_ag_remove_user.set_defaults(func=cmd_admin_groups_remove_user)

    # admin collections
    p_admin_collections = sub_admin.add_parser("collections", help="Manage collection access")
    sub_admin_collections = p_admin_collections.add_subparsers(dest="admin_collections_cmd")

    p_ac_add_user = sub_admin_collections.add_parser("add_user", help="Add user to collection")
    p_ac_add_user.add_argument("collection")
    p_ac_add_user.add_argument("user")
    p_ac_add_user.set_defaults(func=cmd_admin_collections_add_user)

    p_ac_remove_user = sub_admin_collections.add_parser("remove_user", help="Remove user from collection")
    p_ac_remove_user.add_argument("collection")
    p_ac_remove_user.add_argument("user")
    p_ac_remove_user.set_defaults(func=cmd_admin_collections_remove_user)

    p_ac_memberships = sub_admin_collections.add_parser("memberships", help="List collection user memberships")
    p_ac_memberships.add_argument("collection")
    p_ac_memberships.add_argument("--query")
    p_ac_memberships.add_argument("--permission", choices=["read", "read_write", "maintainer"])
    p_ac_memberships.set_defaults(func=cmd_admin_collections_memberships)

    p_ac_add_group = sub_admin_collections.add_parser("add_group", help="Add group to collection")
    p_ac_add_group.add_argument("collection")
    p_ac_add_group.add_argument("group")
    p_ac_add_group.set_defaults(func=cmd_admin_collections_add_group)

    p_ac_remove_group = sub_admin_collections.add_parser("remove_group", help="Remove group from collection")
    p_ac_remove_group.add_argument("collection")
    p_ac_remove_group.add_argument("group")
    p_ac_remove_group.set_defaults(func=cmd_admin_collections_remove_group)

    p_ac_group_memberships = sub_admin_collections.add_parser(
        "group_memberships", help="List collection group memberships"
    )
    p_ac_group_memberships.add_argument("collection")
    p_ac_group_memberships.add_argument("--query")
    p_ac_group_memberships.add_argument("--permission", choices=["read", "read_write", "maintainer"])
    p_ac_group_memberships.set_defaults(func=cmd_admin_collections_group_memberships)

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
    if args.cmd == "admin" and not getattr(args, "admin_cmd", None):
        p_admin.print_help()
        return 0
    if args.cmd == "admin" and args.admin_cmd == "users" and not getattr(args, "admin_users_cmd", None):
        p_admin_users.print_help()
        return 0
    if args.cmd == "admin" and args.admin_cmd == "groups" and not getattr(args, "admin_groups_cmd", None):
        p_admin_groups.print_help()
        return 0
    if args.cmd == "admin" and args.admin_cmd == "collections" and not getattr(args, "admin_collections_cmd", None):
        p_admin_collections.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
