"""The tool names this server exposed before consolidation.

A frozen record, not a live enumeration: the flat surface that produced these is
gone, and the point of the list is to hold the alias table to the names that were
once public. Nothing may be added -- a new tool gets a current name.

Names whose tool or action was removed outright, rather than renamed, are not
here: this fork keeps only what Plane Community Edition supports, so there is
nothing left for them to resolve to.

`test_conformance.py` asserts every one of these is still accounted for: aliased,
declared unmappable with a replacement, or still registered under the same name.
"""

from __future__ import annotations

RETIRED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "complete_cycle",
        "create_cycle",
        "create_intake_work_item",
        "create_label",
        "create_module",
        "create_project",
        "create_state",
        "create_work_item",
        "create_work_item_comment",
        "create_work_item_link",
        "create_work_item_relation",
        "delete_cycle",
        "delete_intake_work_item",
        "delete_label",
        "delete_module",
        "delete_project",
        "delete_state",
        "delete_work_item",
        "delete_work_item_attachment",
        "delete_work_item_comment",
        "delete_work_item_link",
        "get_me",
        "get_project_members",
        "get_work_item_attachment_download_url",
        "get_workspace_members",
        "list_cycle_work_items",
        "list_cycles",
        "list_intake_work_items",
        "list_labels",
        "list_module_work_items",
        "list_modules",
        "list_projects",
        "list_states",
        "list_work_item_activities",
        "list_work_item_attachments",
        "list_work_item_comments",
        "list_work_item_links",
        "list_work_item_relations",
        "list_work_items",
        "manage_cycle_archive",
        "manage_cycle_work_items",
        "manage_module_archive",
        "manage_module_work_items",
        "manage_project_archive",
        "manage_work_item_assignee",
        "manage_work_item_label",
        "read_work_item_attachment",
        "retrieve_cycle",
        "retrieve_intake_work_item",
        "retrieve_label",
        "retrieve_module",
        "retrieve_project",
        "retrieve_state",
        "retrieve_work_item",
        "retrieve_work_item_activity",
        "retrieve_work_item_by_identifier",
        "retrieve_work_item_comment",
        "retrieve_work_item_link",
        "search_work_items",
        "transfer_cycle_work_items",
        "update_cycle",
        "update_intake_work_item",
        "update_label",
        "update_module",
        "update_project",
        "update_state",
        "update_work_item",
        "update_work_item_comment",
        "update_work_item_link",
        "upload_work_item_attachment_from_url",
    }
)
