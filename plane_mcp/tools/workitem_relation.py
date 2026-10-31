"""Relations between work items.

Community Edition exposes one relations endpoint with fixed relation types; it can
list and create relations but has no route for removing one.
"""

from __future__ import annotations

from typing import Any, Literal, get_args

from fastmcp import FastMCP
from plane.models.enums import WorkItemRelationTypeEnum
from plane.models.work_items import CreateWorkItemRelation

from plane_mcp.client import get_plane_client_context
from plane_mcp.toolkit import Action, build_annotations, build_description, coerce_list, missing, needs, one_of

NAME = "workitem_relation"
TITLE = "Work item relations"

RELATION_TYPES: tuple[str, ...] = get_args(WorkItemRelationTypeEnum)

ACTIONS = (
    Action(
        "list",
        ("project_id", "workitem_id"),
        note="related {project_id, issue_id} pairs, grouped by relation type",
        read=True,
    ),
    Action(
        "create",
        ("project_id", "workitem_id", "workitem_ids", "relation_type"),
        note="workitem_ids takes one id or several; related items may be in other projects",
    ),
)

FOOTER = (
    f"relation_type is one of: {', '.join(RELATION_TYPES)}. It reads from workitem_id's side: "
    "blocked_by means workitem_id is blocked by each of workitem_ids. Relations cannot be removed "
    "through this server, and a pair holds one relation: the first one created is kept."
)

LEGACY = {
    "list_work_item_relations": "list",
    "create_work_item_relation": "create",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name=NAME,
        description=build_description("Relations between work items.", ACTIONS, FOOTER),
        annotations=build_annotations(TITLE, ACTIONS),
    )
    def workitem_relation(
        action: Literal["list", "create"],
        project_id: str = "",
        workitem_id: str = "",
        workitem_ids: list[str] | None = None,
        relation_type: str = "",
    ) -> dict[str, Any] | str | None:
        client, workspace_slug = get_plane_client_context()

        if error := needs(action, project_id=project_id, workitem_id=workitem_id):
            return error

        if action == "list":
            # The SDK's WorkItemRelationResponse expects bare ids, but CE answers with
            # {project_id, issue_id} objects and the model rejects them, so read it raw.
            return client.work_items.relations._get(
                f"{workspace_slug}/projects/{project_id}/work-items/{workitem_id}/relations"
            )

        related = coerce_list(workitem_ids)
        if not related:
            return missing(action, "workitem_ids")
        if not relation_type:
            return missing(action, "relation_type")
        if error := one_of("relation_type", relation_type, RELATION_TYPES):
            return error
        client.work_items.relations.create(
            workspace_slug=workspace_slug,
            project_id=project_id,
            work_item_id=workitem_id,
            data=CreateWorkItemRelation(relation_type=relation_type, issues=related),
        )
        return None
