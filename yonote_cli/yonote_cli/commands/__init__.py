"""Command handlers for yonote CLI."""

from .auth import cmd_auth_set, cmd_auth_info
from .cache import cache_info, cache_clear
from .export import cmd_export
from .import_cmd import cmd_import
from .admin import (
    cmd_admin_users_list,
    cmd_admin_users_info,
    cmd_admin_users_add,
    cmd_admin_users_update,
    cmd_admin_users_delete,
    cmd_admin_groups_list,
    cmd_admin_groups_create,
    cmd_admin_groups_update,
    cmd_admin_groups_delete,
    cmd_admin_groups_memberships,
    cmd_admin_groups_add_user,
    cmd_admin_groups_remove_user,
    cmd_admin_collections_list,
    cmd_admin_collections_add_user,
    cmd_admin_collections_remove_user,
    cmd_admin_collections_memberships,
    cmd_admin_collections_add_group,
    cmd_admin_collections_remove_group,
    cmd_admin_collections_group_memberships,
)

__all__ = [
    "cmd_auth_set",
    "cmd_auth_info",
    "cache_info",
    "cache_clear",
    "cmd_export",
    "cmd_import",
    "cmd_admin_users_list",
    "cmd_admin_users_info",
    "cmd_admin_users_add",
    "cmd_admin_users_update",
    "cmd_admin_users_delete",
    "cmd_admin_groups_list",
    "cmd_admin_groups_create",
    "cmd_admin_groups_update",
    "cmd_admin_groups_delete",
    "cmd_admin_groups_memberships",
    "cmd_admin_groups_add_user",
    "cmd_admin_groups_remove_user",
    "cmd_admin_collections_list",
    "cmd_admin_collections_add_user",
    "cmd_admin_collections_remove_user",
    "cmd_admin_collections_memberships",
    "cmd_admin_collections_add_group",
    "cmd_admin_collections_remove_group",
    "cmd_admin_collections_group_memberships",
]
