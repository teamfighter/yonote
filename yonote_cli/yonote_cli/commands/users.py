"""User command wrappers for Yonote CLI."""

from __future__ import annotations

import json
import sys

from .admin import (
    _apply_user_action,
    _resolve_user_id,
    cmd_admin_users_list as cmd_users_list,
    cmd_admin_users_info as cmd_users_info,
    cmd_admin_users_add as cmd_users_add,
)
from ..core import get_base_and_token, http_json


def cmd_users_update(args) -> None:
    """Update a user's profile fields."""
    base, token = get_base_and_token()
    if not args.name and not args.avatar_url:
        print("No update parameters provided", file=sys.stderr)
        sys.exit(1)
    uid = _resolve_user_id(base, token, args.user)
    payload = {"id": uid}
    if args.name:
        payload["name"] = args.name
    if args.avatar_url:
        payload["avatarUrl"] = args.avatar_url
    data = http_json("POST", f"{base}/users.update", token, payload)
    print(json.dumps(data.get("data"), ensure_ascii=False, indent=2))


def cmd_users_promote(args) -> None:
    _apply_user_action("users.promote", args.users)


def cmd_users_demote(args) -> None:
    _apply_user_action("users.demote", args.users)


def cmd_users_suspend(args) -> None:
    _apply_user_action("users.suspend", args.users)


def cmd_users_activate(args) -> None:
    _apply_user_action("users.activate", args.users)


def cmd_users_delete(args) -> None:
    _apply_user_action("users.delete", args.users)


__all__ = [
    "cmd_users_list",
    "cmd_users_info",
    "cmd_users_add",
    "cmd_users_update",
    "cmd_users_promote",
    "cmd_users_demote",
    "cmd_users_suspend",
    "cmd_users_activate",
    "cmd_users_delete",
]
