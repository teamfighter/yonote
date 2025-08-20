"""Administrative commands for Yonote CLI."""

from __future__ import annotations

import json
import re
import sys
from typing import Iterable

from ..core import (
    fetch_all_concurrent,
    format_rows,
    get_base_and_token,
    http_json,
)
from ..core.config import API_MAX_LIMIT


# --- helpers ---------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _is_uuid(value: str) -> bool:
    return bool(_UUID_RE.fullmatch(value))


def _resolve_user_id(base: str, token: str, ident: str) -> str:
    if _is_uuid(ident):
        return ident
    data = http_json(
        "POST",
        f"{base}/users.list",
        token,
        {"limit": 100, "query": ident, "filter": "all"},
    )
    for user in data.get("data", []):
        if user.get("email", "").lower() == ident.lower():
            return user["id"]
    print(f"User not found: {ident}", file=sys.stderr)
    sys.exit(1)


def _resolve_group_id(base: str, token: str, ident: str) -> str:
    if _is_uuid(ident):
        return ident
    groups = fetch_all_concurrent(
        base,
        token,
        "/groups.list",
        params={},
        desc=None,
    )
    for group in groups:
        if group.get("name") == ident:
            return group["id"]
    print(f"Group not found: {ident}", file=sys.stderr)
    sys.exit(1)


def _apply_user_action(path: str, idents: Iterable[str]) -> None:
    base, token = get_base_and_token()
    for ident in idents:
        uid = _resolve_user_id(base, token, ident)
        http_json("POST", f"{base}/{path}", token, {"id": uid})
        print(f"{path.split('.')[1]} {ident}")


# --- user commands --------------------------------------------------------


def cmd_admin_users_list(args) -> None:
    base, token = get_base_and_token()
    params: dict = {}
    if args.filter:
        params["filter"] = args.filter
    if args.query:
        params["query"] = args.query
    users = fetch_all_concurrent(
        base,
        token,
        "/users.list",
        params=params,
        desc=None,
    )
    format_rows(users, ["id", "email", "name", "isAdmin", "isSuspended"])


def cmd_admin_users_info(args) -> None:
    base, token = get_base_and_token()
    uid = _resolve_user_id(base, token, args.user)
    data = http_json("POST", f"{base}/users.info", token, {"id": uid})
    print(json.dumps(data.get("data"), ensure_ascii=False, indent=2))


def cmd_admin_users_update(args) -> None:
    base, token = get_base_and_token()
    uid = _resolve_user_id(base, token, args.user)
    payload = {"id": uid}
    if args.name:
        payload["name"] = args.name
    if args.email:
        payload["email"] = args.email
    if args.avatar_url:
        payload["avatarUrl"] = args.avatar_url
    data = http_json("POST", f"{base}/users.update", token, payload)
    print(json.dumps(data.get("data"), ensure_ascii=False, indent=2))


def cmd_admin_users_promote(args) -> None:
    _apply_user_action("users.promote", args.users)


def cmd_admin_users_demote(args) -> None:
    _apply_user_action("users.demote", args.users)


def cmd_admin_users_suspend(args) -> None:
    _apply_user_action("users.suspend", args.users)


def cmd_admin_users_activate(args) -> None:
    _apply_user_action("users.activate", args.users)


def cmd_admin_users_delete(args) -> None:
    _apply_user_action("users.delete", args.users)


# --- group commands -------------------------------------------------------


def cmd_admin_groups_list(_args) -> None:
    base, token = get_base_and_token()
    groups = fetch_all_concurrent(
        base,
        token,
        "/groups.list",
        params={},
        desc=None,
    )
    format_rows(groups, ["id", "name", "memberCount"])


def cmd_admin_groups_create(args) -> None:
    base, token = get_base_and_token()
    data = http_json("POST", f"{base}/groups.create", token, {"name": args.name})
    print(json.dumps(data.get("data"), ensure_ascii=False, indent=2))


def cmd_admin_groups_update(args) -> None:
    base, token = get_base_and_token()
    gid = _resolve_group_id(base, token, args.group)
    data = http_json(
        "POST",
        f"{base}/groups.update",
        token,
        {"id": gid, "name": args.name},
    )
    print(json.dumps(data.get("data"), ensure_ascii=False, indent=2))


def cmd_admin_groups_delete(args) -> None:
    base, token = get_base_and_token()
    gid = _resolve_group_id(base, token, args.group)
    http_json("POST", f"{base}/groups.delete", token, {"id": gid})
    print(f"delete {args.group}")


def _fetch_memberships(base: str, token: str, path: str, params: dict, key: str):
    """Fetch all paginated membership results for ``key``."""
    results: list = []
    offset = 0
    while True:
        payload = dict(params)
        payload.update({"limit": API_MAX_LIMIT, "offset": offset})
        data = http_json("POST", f"{base}{path}", token, payload)
        items = (data.get("data") or {}).get(key, [])
        results.extend(items)
        if len(items) < API_MAX_LIMIT:
            break
        offset += API_MAX_LIMIT
    return results


def cmd_admin_groups_memberships(args) -> None:
    base, token = get_base_and_token()
    gid = _resolve_group_id(base, token, args.group)
    params = {"id": gid}
    if args.query:
        params["query"] = args.query
    users = _fetch_memberships(base, token, "/groups.memberships", params, "users")
    format_rows(users, ["id", "email", "name"])


def cmd_admin_groups_add_user(args) -> None:
    base, token = get_base_and_token()
    gid = _resolve_group_id(base, token, args.group)
    uid = _resolve_user_id(base, token, args.user)
    http_json("POST", f"{base}/groups.add_user", token, {"id": gid, "userId": uid})
    print(f"added {args.user} to {args.group}")


def cmd_admin_groups_remove_user(args) -> None:
    base, token = get_base_and_token()
    gid = _resolve_group_id(base, token, args.group)
    uid = _resolve_user_id(base, token, args.user)
    http_json("POST", f"{base}/groups.remove_user", token, {"id": gid, "userId": uid})
    print(f"removed {args.user} from {args.group}")


# --- collection commands --------------------------------------------------


def cmd_admin_collections_add_user(args) -> None:
    base, token = get_base_and_token()
    uid = _resolve_user_id(base, token, args.user)
    http_json(
        "POST",
        f"{base}/collections.add_user",
        token,
        {"id": args.collection, "userId": uid},
    )
    print(f"added {args.user} to {args.collection}")


def cmd_admin_collections_remove_user(args) -> None:
    base, token = get_base_and_token()
    uid = _resolve_user_id(base, token, args.user)
    http_json(
        "POST",
        f"{base}/collections.remove_user",
        token,
        {"id": args.collection, "userId": uid},
    )
    print(f"removed {args.user} from {args.collection}")


def cmd_admin_collections_memberships(args) -> None:
    base, token = get_base_and_token()
    params = {"id": args.collection}
    if args.query:
        params["query"] = args.query
    if args.permission:
        params["permission"] = args.permission
    users = _fetch_memberships(
        base,
        token,
        "/collections.memberships",
        params,
        "users",
    )
    format_rows(users, ["id", "email", "name"])


def cmd_admin_collections_add_group(args) -> None:
    base, token = get_base_and_token()
    gid = _resolve_group_id(base, token, args.group)
    http_json(
        "POST",
        f"{base}/collections.add_group",
        token,
        {"id": args.collection, "groupId": gid},
    )
    print(f"added group {args.group} to {args.collection}")


def cmd_admin_collections_remove_group(args) -> None:
    base, token = get_base_and_token()
    gid = _resolve_group_id(base, token, args.group)
    http_json(
        "POST",
        f"{base}/collections.remove_group",
        token,
        {"id": args.collection, "groupId": gid},
    )
    print(f"removed group {args.group} from {args.collection}")


def cmd_admin_collections_group_memberships(args) -> None:
    base, token = get_base_and_token()
    params = {"id": args.collection}
    if args.query:
        params["query"] = args.query
    if args.permission:
        params["permission"] = args.permission
    groups = _fetch_memberships(
        base,
        token,
        "/collections.group_memberships",
        params,
        "groups",
    )
    format_rows(groups, ["id", "name", "memberCount"])
