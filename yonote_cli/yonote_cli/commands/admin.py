"""Administrative commands for Yonote CLI."""

from __future__ import annotations

import json
import re
import sys
from typing import Iterable, List, Tuple
from urllib.error import HTTPError

from ..core import (
    fetch_all_concurrent,
    format_rows,
    get_base_and_token,
    http_json,
)
from ..core.config import API_MAX_LIMIT
from ..core.http import _handle_http_error


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
    for ident in idents:
        uid = _resolve_user_id(base, token, ident)
        http_json("POST", f"{base}/{path}", token, {"id": uid})
        print(f"{path.split('.')[1]} {ident}")


def _error_message(e: HTTPError) -> str:
    """Extract a human-friendly error message from ``HTTPError``."""
    body = e.read().decode("utf-8", errors="ignore")
    try:
        data = json.loads(body)
        if isinstance(data, dict) and data.get("error"):
            return data["error"]
    except Exception:
        pass
    return body or e.reason


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
    """Invite one or more users by email."""
    base, token = get_base_and_token()
    invites = [
        {"email": email, "name": email.split("@")[0], "role": args.role}
        for email in args.emails
    ]
    http_json("POST", f"{base}/users.invite", token, {"invites": invites})
    for email in args.emails:
        print(f"invited {email}")


def cmd_admin_users_update(args) -> None:
    base, token = get_base_and_token()
    updates = {}
    if args.name:
        updates["name"] = args.name
    if args.avatar_url:
        updates["avatarUrl"] = args.avatar_url

    actions: List[Tuple[str, str]] = []
    if args.promote:
        actions.append(("users.promote", "promote"))
    if args.demote:
        actions.append(("users.demote", "demote"))
    if args.suspend:
        actions.append(("users.suspend", "suspend"))
    if args.activate:
        actions.append(("users.activate", "activate"))

    if not updates and not actions:
        print("No update parameters provided", file=sys.stderr)
        sys.exit(1)

    if updates and len(args.users) > 1:
        print("Profile fields can only be updated for a single user", file=sys.stderr)
        sys.exit(1)

    resolved = [
        (ident, _resolve_user_id(base, token, ident)) for ident in args.users
    ]

    if updates:
        ident, uid = resolved[0]
        payload = {"id": uid, **updates}
        data = http_json("POST", f"{base}/users.update", token, payload)
        print(json.dumps(data.get("data"), ensure_ascii=False, indent=2))

    for path, verb in actions:
        for ident, uid in resolved:
            http_json("POST", f"{base}/{path}", token, {"id": uid})
            print(f"{verb} {ident}")


def cmd_admin_users_delete(args) -> None:
    _apply_user_action("users.delete", args.users)


# --- group commands -------------------------------------------------------


def cmd_admin_groups_list(args) -> None:
    base, token = get_base_and_token()
    params = {}
    if getattr(args, "query", None):
        params["query"] = args.query
    groups = _fetch_memberships(base, token, "/groups.list", params, "groups")
    format_rows(groups, ["id", "name", "memberCount"])


def cmd_admin_groups_create(args) -> None:
    base, token = get_base_and_token()
    for name in args.names:
        data = http_json("POST", f"{base}/groups.create", token, {"name": name})
        print(json.dumps(data.get("data"), ensure_ascii=False, indent=2))


def cmd_admin_groups_rename(args) -> None:
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
    for ident in args.groups:
        gid = _resolve_group_id(base, token, ident)
        http_json("POST", f"{base}/groups.delete", token, {"id": gid})
        print(f"delete {ident}")


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
    for user in args.users:
        uid = _resolve_user_id(base, token, user)
        try:
            http_json(
                "POST",
                f"{base}/groups.add_user",
                token,
                {"id": gid, "userId": uid},
                handle_error=False,
            )
            print(f"added {user} to {args.group}")
        except HTTPError as e:
            if e.code == 400:
                print(f"skipped {user}: {_error_message(e)}")
            else:
                _handle_http_error(e)


def cmd_admin_groups_del_user(args) -> None:
    base, token = get_base_and_token()
    gid = _resolve_group_id(base, token, args.group)
    for user in args.users:
        uid = _resolve_user_id(base, token, user)
        try:
            http_json(
                "POST",
                f"{base}/groups.remove_user",
                token,
                {"id": gid, "userId": uid},
                handle_error=False,
            )
            print(f"removed {user} from {args.group}")
        except HTTPError as e:
            if e.code == 400:
                print(f"skipped {user}: {_error_message(e)}")
            else:
                _handle_http_error(e)


# --- collection commands --------------------------------------------------


def cmd_admin_collections_list(args) -> None:
    base, token = get_base_and_token()
    params = {}
    if getattr(args, "query", None):
        params["query"] = args.query
    cols = fetch_all_concurrent(
        base,
        token,
        "/collections.list",
        params=params,
        desc=None,
    )
    format_rows(cols, ["id", "name"])


def cmd_admin_collections_add_user(args) -> None:
    base, token = get_base_and_token()
    uid = _resolve_user_id(base, token, args.user)
    try:
        http_json(
            "POST",
            f"{base}/collections.add_user",
            token,
            {"id": args.collection, "userId": uid},
            handle_error=False,
        )
        print(f"added {args.user} to {args.collection}")
    except HTTPError as e:
        if e.code == 400:
            print(f"skipped {args.user}: {_error_message(e)}")
        else:
            _handle_http_error(e)


def cmd_admin_collections_remove_user(args) -> None:
    base, token = get_base_and_token()
    uid = _resolve_user_id(base, token, args.user)
    try:
        http_json(
            "POST",
            f"{base}/collections.remove_user",
            token,
            {"id": args.collection, "userId": uid},
            handle_error=False,
        )
        print(f"removed {args.user} from {args.collection}")
    except HTTPError as e:
        if e.code == 400:
            print(f"skipped {args.user}: {_error_message(e)}")
        else:
            _handle_http_error(e)


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
    try:
        http_json(
            "POST",
            f"{base}/collections.add_group",
            token,
            {"id": args.collection, "groupId": gid},
            handle_error=False,
        )
        print(f"added group {args.group} to {args.collection}")
    except HTTPError as e:
        if e.code == 400:
            print(f"skipped group {args.group}: {_error_message(e)}")
        else:
            _handle_http_error(e)


def cmd_admin_collections_remove_group(args) -> None:
    base, token = get_base_and_token()
    gid = _resolve_group_id(base, token, args.group)
    try:
        http_json(
            "POST",
            f"{base}/collections.remove_group",
            token,
            {"id": args.collection, "groupId": gid},
            handle_error=False,
        )
        print(f"removed group {args.group} from {args.collection}")
    except HTTPError as e:
        if e.code == 400:
            print(f"skipped group {args.group}: {_error_message(e)}")
        else:
            _handle_http_error(e)


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
