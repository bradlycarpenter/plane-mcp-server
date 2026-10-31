"""Work items: the core issue/task record.

Community Edition has no workspace-wide listing, count, archive or PQL
filtering, so every listing is per project and unfiltered.
"""

from __future__ import annotations

from typing import Any, Literal, get_args

from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger
from plane.models.enums import PriorityEnum
from plane.models.query_params import RetrieveQueryParams, WorkItemQueryParams
from plane.models.work_items import (
    CreateWorkItem,
    PaginatedWorkItemResponse,
    UpdateWorkItem,
    WorkItem,
    WorkItemDetail,
    WorkItemSearch,
)

from plane_mcp.client import get_plane_client_context
from plane_mcp.toolkit import (
    Action,
    build_annotations,
    build_description,
    coerce_list,
    envelope,
    ids_of,
    missing,
    one_of,
    opt,
    rich_text,
)

logger = get_logger(__name__)

NAME = "workitem"
TITLE = "Work items"

PRIORITIES = get_args(PriorityEnum)

WRITE_FIELDS = (
    "name",
    "assignees",
    "labels",
    "type_id",
    "point",
    "description_html",
    "description_stripped",
    "priority",
    "start_date",
    "target_date",
    "sort_order",
    "is_draft",
    "parent",
    "state",
    "estimate_point",
    "external_source",
    "external_id",
)
QUERY_FIELDS = ("order_by", "per_page", "cursor", "expand", "fields", "external_id", "external_source")

ACTIONS = (
    Action("list", ("project_id",), QUERY_FIELDS, note="use search to find work items across projects", read=True),
    Action(
        "retrieve",
        ("project_id", "workitem_id"),
        ("expand", "fields", "external_id", "external_source", "order_by"),
        read=True,
    ),
    Action(
        "retrieve_by_identifier",
        ("workitem_identifier",),
        ("expand", "fields", "external_id", "external_source", "order_by"),
        note="identifier is PROJECT-N, e.g. ENG-42",
        read=True,
    ),
    Action("search", ("query",), ("expand", "fields", "external_id", "external_source", "order_by"), read=True),
    Action("create", ("project_id", "name"), WRITE_FIELDS[1:]),
    Action("update", ("project_id", "workitem_id"), WRITE_FIELDS, note="only the fields you pass are changed"),
    Action("delete", ("project_id", "workitem_id"), destructive=True),
    Action(
        "manage_assignee",
        ("project_id", "workitem_id"),
        ("add_user_id", "remove_user_id"),
        note="each takes one id or several; the list is merged, not replaced, and removals apply first",
    ),
    Action(
        "manage_label",
        ("project_id", "workitem_id"),
        ("add_label_id", "remove_label_id"),
        note="each takes one id or several; the list is merged, not replaced, and removals apply first",
    ),
)

FOOTER = (
    f"priority: {', '.join(PRIORITIES)}.\n"
    "UUID fields (assignees, labels, state, parent, type_id) need UUIDs -- list the relevant "
    "resource first if you only have a name.\n"
    "description_stripped is plain text and is wrapped into HTML on save; description_html wins "
    "if both are given.\n"
    "To clear a field on update: assignees=[] or labels=[], and start_date=null or "
    "target_date=null. A field you leave out is not changed.\n"
    "fields is a sparse fieldset: use `project`, not project_id, and `description_html`, not "
    "description."
)

LEGACY = {
    "list_work_items": "list",
    "retrieve_work_item": "retrieve",
    "retrieve_work_item_by_identifier": "retrieve_by_identifier",
    "search_work_items": "search",
    "create_work_item": "create",
    "update_work_item": "update",
    "delete_work_item": "delete",
    "manage_work_item_assignee": "manage_assignee",
    "manage_work_item_label": "manage_label",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name=NAME,
        description=build_description("Work items -- issues and tasks.", ACTIONS, FOOTER),
        annotations=build_annotations(TITLE, ACTIONS),
    )
    def workitem(  # noqa: PLR0911, PLR0912 - one branch per action is the point
        action: Literal[
            "list",
            "retrieve",
            "retrieve_by_identifier",
            "search",
            "create",
            "update",
            "delete",
            "manage_assignee",
            "manage_label",
        ],
        project_id: str = "",
        workitem_id: str = "",
        workitem_identifier: str = "",
        query: str = "",
        name: str = "",
        assignees: list[str] | None = None,
        labels: list[str] | None = None,
        type_id: str = "",
        point: int = 0,
        description_html: str = "",
        description_stripped: str = "",
        priority: str = "",
        start_date: str | None = "",
        target_date: str | None = "",
        sort_order: float = 0,
        parent: str = "",
        state: str = "",
        estimate_point: str = "",
        add_user_id: str = "",
        remove_user_id: str = "",
        add_label_id: str = "",
        remove_label_id: str = "",
        external_source: str = "",
        external_id: str = "",
        order_by: str = "",
        expand: str = "",
        fields: str = "",
        cursor: str = "",
        per_page: int = 0,
        # Tri-state: False publishes a draft, unset leaves the flag alone.
        is_draft: bool | None = None,
    ) -> WorkItem | WorkItemDetail | WorkItemSearch | dict[str, Any] | list[Any] | str | None:
        client, workspace_slug = get_plane_client_context()

        if error := one_of("priority", priority, PRIORITIES):
            return error

        def retrieve_params() -> RetrieveQueryParams:
            return RetrieveQueryParams(
                expand=opt(expand),
                fields=opt(fields),
                external_id=opt(external_id),
                external_source=opt(external_source),
                order_by=opt(order_by),
            )

        def write_payload() -> dict[str, Any]:
            """The fields the caller supplied, and no others."""
            payload = {
                "name": opt(name),
                "assignees": coerce_list(assignees),
                "labels": coerce_list(labels),
                "type_id": opt(type_id),
                "point": opt(point),
                "description_html": rich_text(description_html, description_stripped),
                "priority": opt(priority),
                "start_date": opt(start_date),
                "target_date": opt(target_date),
                "sort_order": opt(sort_order),
                "is_draft": is_draft,
                "external_source": opt(external_source),
                "external_id": opt(external_id),
                "parent": opt(parent),
                "state": opt(state),
                "estimate_point": opt(estimate_point),
            }
            supplied = {field: value for field, value in payload.items() if value is not None}
            dates = {"start_date": start_date, "target_date": target_date}
            return supplied | {field: None for field, value in dates.items() if value is None}

        if action == "list":
            if not project_id:
                return missing(action, "project_id")
            params = WorkItemQueryParams(
                order_by=opt(order_by),
                per_page=opt(per_page),
                cursor=opt(cursor),
                expand=opt(expand),
                fields=opt(fields),
                external_id=opt(external_id),
                external_source=opt(external_source),
            )
            response: PaginatedWorkItemResponse = client.work_items.list(
                workspace_slug=workspace_slug, project_id=project_id, params=params
            )
            return envelope(response, opt(fields))

        if action == "search":
            if not query:
                return missing(action, "query")
            return client.work_items.search(workspace_slug=workspace_slug, query=query, params=retrieve_params())

        if action == "retrieve_by_identifier":
            if not workitem_identifier:
                return missing(action, "workitem_identifier")
            head, _, sequence = workitem_identifier.rpartition("-")
            if not head or not sequence.isdigit():
                return (
                    f"Error: invalid work item identifier {workitem_identifier!r}. "
                    "Expected PROJECT-N, for example ENG-42."
                )
            return client.work_items.retrieve_by_identifier(
                workspace_slug=workspace_slug,
                project_identifier=head,
                issue_identifier=int(sequence),
                params=retrieve_params(),
            )

        if not project_id:
            return missing(action, "project_id")

        if action == "create":
            if not name:
                return missing(action, "name")
            return client.work_items.create(
                workspace_slug=workspace_slug,
                project_id=project_id,
                data=CreateWorkItem(**write_payload()),
            )

        if not workitem_id:
            return missing(action, "workitem_id")

        if action == "retrieve":
            return client.work_items.retrieve(
                workspace_slug=workspace_slug,
                project_id=project_id,
                work_item_id=workitem_id,
                params=retrieve_params(),
            )

        if action == "update":
            return client.work_items.update(
                workspace_slug=workspace_slug,
                project_id=project_id,
                work_item_id=workitem_id,
                data=UpdateWorkItem(**write_payload()),
            )

        if action == "delete":
            client.work_items.delete(workspace_slug=workspace_slug, project_id=project_id, work_item_id=workitem_id)
            return None

        # manage_assignee / manage_label: read the current set, mutate it, write it back.
        add, remove, field = (
            (add_user_id, remove_user_id, "assignees")
            if action == "manage_assignee"
            else (add_label_id, remove_label_id, "labels")
        )
        if not add and not remove:
            return missing(action, f"add_{field[:-1]}_id or remove_{field[:-1]}_id")
        # Either side takes one id or several, so adding three assignees is one call.
        adding, removing = coerce_list(add) or [], coerce_list(remove) or []
        current = client.work_items.retrieve(
            workspace_slug=workspace_slug, project_id=project_id, work_item_id=workitem_id
        )
        ids = [value for value in ids_of(getattr(current, field)) if value not in removing]
        ids += [value for value in adding if value not in ids]
        return client.work_items.update(
            workspace_slug=workspace_slug,
            project_id=project_id,
            work_item_id=workitem_id,
            data=UpdateWorkItem(**{field: ids}),
        )
