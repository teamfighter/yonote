"""Group-related command wrappers."""

from .admin import (
    cmd_admin_groups_list as cmd_groups_list,
    cmd_admin_groups_create as cmd_groups_create,
    cmd_admin_groups_update as cmd_groups_update,
    cmd_admin_groups_delete as cmd_groups_delete,
    cmd_admin_groups_memberships as cmd_groups_memberships,
    cmd_admin_groups_add_user as cmd_groups_add_user,
    cmd_admin_groups_remove_user as cmd_groups_remove_user,
)

__all__ = [
    "cmd_groups_list",
    "cmd_groups_create",
    "cmd_groups_update",
    "cmd_groups_delete",
    "cmd_groups_memberships",
    "cmd_groups_add_user",
    "cmd_groups_remove_user",
]
