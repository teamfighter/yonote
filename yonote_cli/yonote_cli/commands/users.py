"""User-related command wrappers."""

from .admin import (
    cmd_admin_users_list as cmd_users_list,
    cmd_admin_users_info as cmd_users_info,
    cmd_admin_users_update as cmd_users_update,
    cmd_admin_users_delete as cmd_users_delete,
)
from ..core import http_json, get_base_and_token


def cmd_users_add(args) -> None:
    """Invite one or more users by email."""
    base, token = get_base_and_token()
    payload = {"emails": args.emails}
    http_json("POST", f"{base}/users.invite", token, payload)
    for email in args.emails:
        print(f"invited {email}")

__all__ = [
    "cmd_users_list",
    "cmd_users_info",
    "cmd_users_update",
    "cmd_users_delete",
    "cmd_users_add",
]
