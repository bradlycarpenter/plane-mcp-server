"""Projects in a workspace, and the feature flags that govern them.

Community Edition has no features endpoint; the flags are fields on the project
itself, and cycles, modules and intake start disabled.
"""

from __future__ import annotations

from typing import Literal, get_args

from fastmcp import FastMCP
from plane.models.enums import TimezoneEnum
from plane.models.projects import (
    CreateProject,
    PaginatedProjectLiteResponse,
    PaginatedProjectMemberResponse,
    Project,
    UpdateProject,
)
from plane.models.query_params import ProjectLiteListQueryParams

from plane_mcp.client import get_plane_client_context
from plane_mcp.toolkit import Action, build_annotations, build_description, missing, needs, opt, rich_text

NAME = "project"
TITLE = "Projects"

TIMEZONES = get_args(TimezoneEnum)

DEFAULT_PER_PAGE = 100

ACTIONS = (
    Action(
        "list", (), ("cursor", "per_page", "order_by"), note="trimmed fields; use retrieve for full detail", read=True
    ),
    Action("retrieve", ("project_id",), read=True),
    Action(
        "create",
        ("name", "identifier"),
        (
            "description",
            "description_html",
            "project_lead",
            "default_assignee",
            "emoji",
            "cover_image",
            "timezone",
            "archive_in",
            "close_in",
            "modules",
            "cycles",
            "views",
            "pages",
            "intakes",
            "external_source",
            "external_id",
        ),
    ),
    Action(
        "update",
        ("project_id",),
        (
            "name",
            "description",
            "description_html",
            "identifier",
            "project_lead",
            "default_assignee",
            "emoji",
            "cover_image",
            "network",
            "timezone",
            "archive_in",
            "close_in",
            "default_state",
            "estimate",
            "modules",
            "cycles",
            "views",
            "pages",
            "intakes",
            "external_source",
            "external_id",
        ),
        note="only the fields you pass are changed",
    ),
    Action("delete", ("project_id",), destructive=True),
    Action("archive", ("project_id",)),
    Action("unarchive", ("project_id",)),
)

FOOTER = (
    "identifier is the short work item prefix, such as ENG. network is 0 for secret or 2 for public. "
    "project_lead and default_assignee are member ids -- get them from `member list_workspace`. "
    "modules, cycles, views, pages and intakes are feature toggles: booleans, and omitted ones are left as "
    "they are. Cycles, modules and intake start disabled, so enable them before creating one."
)

LEGACY = {
    "list_projects": "list",
    "retrieve_project": "retrieve",
    "create_project": "create",
    "update_project": "update",
    "delete_project": "delete",
}

LEGACY_UNMAPPED = {
    "manage_project_archive": "took archive=bool, which spans two actions: use archive or unarchive",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name=NAME,
        description=build_description("Projects in a workspace.", ACTIONS, FOOTER),
        annotations=build_annotations(TITLE, ACTIONS),
    )
    def project(
        action: Literal[
            "list",
            "retrieve",
            "create",
            "update",
            "delete",
            "archive",
            "unarchive",
        ],
        project_id: str = "",
        name: str = "",
        identifier: str = "",
        description: str = "",
        description_html: str = "",
        project_lead: str = "",
        default_assignee: str = "",
        emoji: str = "",
        cover_image: str = "",
        # 0 is a real value (secret), so network cannot use the 0 sentinel.
        network: int | None = None,
        timezone: str = "",
        archive_in: int = 0,
        close_in: int = 0,
        default_state: str = "",
        estimate: str = "",
        external_source: str = "",
        external_id: str = "",
        # Feature toggles are tri-state: False disables, unset leaves alone.
        modules: bool | None = None,
        cycles: bool | None = None,
        views: bool | None = None,
        pages: bool | None = None,
        intakes: bool | None = None,
        cursor: str = "",
        per_page: int = 0,
        order_by: str = "",
    ) -> Project | PaginatedProjectLiteResponse | PaginatedProjectMemberResponse | str | None:
        client, workspace_slug = get_plane_client_context()

        if timezone and timezone not in TIMEZONES:
            return f"Error: {timezone!r} is not a recognised timezone."
        if network is not None and network not in (0, 2):
            return "Error: network must be 0 (secret) or 2 (public)."
        zone: TimezoneEnum | None = timezone or None  # type: ignore[assignment]

        if action == "list":
            return client.projects.list_lite(
                workspace_slug=workspace_slug,
                params=ProjectLiteListQueryParams(
                    cursor=opt(cursor),
                    per_page=per_page or DEFAULT_PER_PAGE,
                    order_by=opt(order_by),
                    include_archived=False,
                ),
            )

        if action == "create":
            if error := needs(action, name=name, identifier=identifier):
                return error
            return client.projects.create(
                workspace_slug=workspace_slug,
                data=CreateProject(
                    name=name,
                    identifier=identifier,
                    description=opt(description),
                    description_html=rich_text(description_html, description),
                    project_lead=opt(project_lead),
                    default_assignee=opt(default_assignee),
                    emoji=opt(emoji),
                    cover_image=opt(cover_image),
                    module_view=modules,
                    cycle_view=cycles,
                    issue_views_view=views,
                    page_view=pages,
                    intake_view=intakes,
                    archive_in=opt(archive_in),
                    close_in=opt(close_in),
                    timezone=zone,
                    external_source=opt(external_source),
                    external_id=opt(external_id),
                ),
            )

        if not project_id:
            return missing(action, "project_id")

        if action == "retrieve":
            return client.projects.retrieve(workspace_slug=workspace_slug, project_id=project_id)

        if action == "update":
            return client.projects.update(
                workspace_slug=workspace_slug,
                project_id=project_id,
                data=UpdateProject(
                    name=opt(name),
                    description=opt(description),
                    description_html=rich_text(description_html, description),
                    identifier=opt(identifier),
                    project_lead=opt(project_lead),
                    default_assignee=opt(default_assignee),
                    emoji=opt(emoji),
                    cover_image=opt(cover_image),
                    network=network,
                    module_view=modules,
                    cycle_view=cycles,
                    issue_views_view=views,
                    page_view=pages,
                    intake_view=intakes,
                    archive_in=opt(archive_in),
                    close_in=opt(close_in),
                    timezone=zone,
                    external_source=opt(external_source),
                    external_id=opt(external_id),
                    default_state=opt(default_state),
                    estimate=opt(estimate),
                ),
            )

        if action == "delete":
            client.projects.delete(workspace_slug=workspace_slug, project_id=project_id)
            return None

        if action == "archive":
            client.projects.archive(workspace_slug=workspace_slug, project_id=project_id)
            return None

        client.projects.unarchive(workspace_slug=workspace_slug, project_id=project_id)
        return None
