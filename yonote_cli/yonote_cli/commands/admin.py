"""Administrative commands for Yonote CLI."""

from __future__ import annotations

import json
import re
import sys
from typing import Iterable, List, Tuple

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
    groups = _fetch_memberships(base, token, "/groups.list", {}, "groups")
    for group in groups:
        if group.get("name") == ident:
            return group["id"]
    print(f"Group not found: {ident}", file=sys.stderr)
    sys.exit(1)


def _apply_user_action(path: str, idents: Iterable[str]) -> None:
    base, token = get_base_and_token()
    had_error = False
    for ident in idents:
        try:
            uid = _resolve_user_id(base, token, ident)
        except SystemExit:
            had_error = True
            continue
        http_json("POST", f"{base}/{path}", token, {"id": uid})
        print(f"{path.split('.')[1]} {ident}")
    if had_error:
        sys.exit(1)


# --- user commands --------------------------------------------------------


def cmd_admin_users_list(args) -> None:
    base, token = get_base_and_token()
    params: dict = {"filter": "all"}
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


def cmd_admin_users_add(args) -> None:
    """Invite one or more users by email.

    The API accepts a list of email addresses in the ``emails`` field.  We
    send one request per address so that a failure for a single invite does not
    prevent processing the remaining addresses.
    """
    base, token = get_base_and_token()
    for email in args.emails:
        try:
            http_json("POST", f"{base}/users.invite", token, {"emails": [email]})
            print(f"invited {email}")
        except SystemExit:
            # http_json already printed the error message
            print(f"failed {email}", file=sys.stderr)


def cmd_admin_users_update(args) -> None:
    base, token = get_base_and_token()
    actions: List[Tuple[str, str]] = []
    if args.promote:
        actions.append(("users.promote", "promote"))
    if args.demote:
        actions.append(("users.demote", "demote"))
    if args.suspend:
        actions.append(("users.suspend", "suspend"))
    if args.activate:
        actions.append(("users.activate", "activate"))

    if not actions:
        print("No update parameters provided", file=sys.stderr)
        sys.exit(1)

    resolved = [
        (ident, _resolve_user_id(base, token, ident)) for ident in args.users
    ]

    for path, verb in actions:
        for ident, uid in resolved:
            http_json("POST", f"{base}/{path}", token, {"id": uid})
            print(f"{verb} {ident}")


def cmd_admin_users_delete(args) -> None:
    _apply_user_action("users.delete", args.users)


# --- group commands -------------------------------------------------------


def cmd_admin_groups_list(_args) -> None:
    base, token = get_base_and_token()
    groups = _fetch_memberships(base, token, "/groups.list", {}, "groups")
    norm = [g if isinstance(g, dict) else {"name": g} for g in groups]
    format_rows(norm, ["id", "name", "memberCount"])


def cmd_admin_groups_create(args) -> None:
    base, token = get_base_and_token()
    for name in args.names:
        data = http_json("POST", f"{base}/groups.create", token, {"name": name})
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


def cmd_admin_collections_list(_args) -> None:
    base, token = get_base_and_token()
    cols = fetch_all_concurrent(
        base,
        token,
        "/collections.list",
        params={},
        desc=None,
    )
    format_rows(cols, ["id", "name", "private"])


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
