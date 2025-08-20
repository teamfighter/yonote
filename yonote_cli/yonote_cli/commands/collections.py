"""Collection-related command wrappers."""

from .admin import (
    cmd_admin_collections_add_user as cmd_collections_add_user,
    cmd_admin_collections_remove_user as cmd_collections_remove_user,
    cmd_admin_collections_memberships as cmd_collections_memberships,
    cmd_admin_collections_add_group as cmd_collections_add_group,
    cmd_admin_collections_remove_group as cmd_collections_remove_group,
    cmd_admin_collections_group_memberships as cmd_collections_group_memberships,
)

__all__ = [
    "cmd_collections_add_user",
    "cmd_collections_remove_user",
    "cmd_collections_memberships",
    "cmd_collections_add_group",
    "cmd_collections_remove_group",
    "cmd_collections_group_memberships",
]
