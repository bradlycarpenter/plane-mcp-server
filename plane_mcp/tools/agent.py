"""The Claude Code session calling this server, as the hc terminal it runs in.

Linking is labelling: the bridge reads the `plane.*` labels off the terminal and
mirrors them into an AgentSession, so nothing here writes the session row.
`plane.session` belongs to the bridge and is never set or cleared here.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Literal

from fastmcp import FastMCP
from plane.errors.errors import HttpError
from plane.models.labels import CreateLabel
from plane.models.work_items import CreateWorkItem, CreateWorkItemComment, UpdateWorkItem

from plane_mcp.client import get_plane_client_context, is_local
from plane_mcp.toolkit import (
    Action,
    build_annotations,
    build_description,
    ids_of,
    missing,
    needs,
    opt,
    page_params,
    rich_text,
)

NAME = "agent"
TITLE = "This Claude Code session"

ACTIONS = (
    Action("link", ("workitem_identifier",)),
    Action("create_and_link", ("project_id", "name"), ("description_html",), note="creates a work item and links it"),
    Action("unlink"),
    Action("status", read=True, note="the work item this session is linked to, if any"),
    Action(
        "ask",
        ("question",),
        note="posts it on the linked work item and flags needs-you; end your turn after it",
    ),
)

FOOTER = (
    "Acts on this session's hc terminal. workitem_identifier is PROJECT-N, e.g. AGENT-7. "
    "question is plain text; the reply arrives later as a message in this session."
)

LEGACY: dict[str, str] = {}

LINK_LABELS = ("plane.issue", "plane.ref", "plane.project")
NEEDS_YOU = "needs-you"
NEEDS_YOU_COLOR = "#F59E0B"
HC_TIMEOUT = 15
# Not "@claude": over Brad's token the comment is his, and the bridge forwards
# comments by anyone but Claude that mention it, so the question would echo back.
REPLY_HINT = "To answer, reply with a comment that mentions Claude."


def _hc(*args: str) -> Any:
    """Run an hc command and return its JSON output."""
    try:
        done = subprocess.run(["hc", *args, "--json"], capture_output=True, text=True, timeout=HC_TIMEOUT)
    except FileNotFoundError as exc:
        raise ValueError("hc is not installed or not on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"hc {args[0]} timed out after {HC_TIMEOUT}s") from exc
    if done.returncode != 0:
        raise ValueError(f"hc {args[0]} failed: {(done.stderr or done.stdout).strip()}")
    return json.loads(done.stdout) if done.stdout.strip() else None


def _labels(terminal: str) -> dict[str, str]:
    return (_hc("get", terminal) or {}).get("labels") or {}


def _linked(terminal: str, labels: dict[str, str]) -> dict[str, Any]:
    if not labels.get("plane.issue"):
        return {"terminal": terminal, "linked": False}
    return {
        "terminal": terminal,
        "linked": True,
        "workitem_identifier": labels.get("plane.ref", ""),
        "workitem_id": labels["plane.issue"],
        "project_id": labels.get("plane.project", ""),
        "session_id": labels.get("plane.session", ""),
    }


def _link(terminal: str, identifier: str, workitem_id: str, project_id: str, name: str | None) -> dict[str, Any]:
    _hc("label", terminal, f"plane.issue={workitem_id}", f"plane.ref={identifier}", f"plane.project={project_id}")
    return {
        "terminal": terminal,
        "linked": True,
        "workitem_identifier": identifier,
        "workitem_id": workitem_id,
        "project_id": project_id,
        "name": name,
    }


def _needs_you_label(client, workspace_slug: str, project_id: str) -> str:
    """The project's needs-you label id, created on first use."""

    def find() -> str | None:
        cursor = ""
        while True:
            page = client.labels.list(
                workspace_slug=workspace_slug,
                project_id=project_id,
                params=page_params(cursor, 100),
            )
            for label in page.results or []:
                if (label.name or "").lower() == NEEDS_YOU:
                    return str(label.id)
            if not page.next_page_results:
                return None
            cursor = page.next_cursor

    if found := find():
        return found
    try:
        created = client.labels.create(
            workspace_slug=workspace_slug,
            project_id=project_id,
            data=CreateLabel(name=NEEDS_YOU, color=NEEDS_YOU_COLOR),
        )
    except HttpError:
        # The bridge adds the same label when a session blocks; if it created it
        # between our lookup and our create, Plane refuses the duplicate name.
        if found := find():
            return found
        raise
    return str(created.id)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name=NAME,
        description=build_description("This Claude Code session and the work item it is linked to.", ACTIONS, FOOTER),
        annotations=build_annotations(TITLE, ACTIONS),
    )
    def agent(
        action: Literal["link", "create_and_link", "unlink", "status", "ask"],
        workitem_identifier: str = "",
        project_id: str = "",
        name: str = "",
        description_html: str = "",
        question: str = "",
    ) -> dict[str, Any] | str:
        terminal = os.environ.get("HC_TERMINAL_ID", "")
        if not is_local() or not terminal:
            return (
                "Error: the agent tool works only for a Claude Code session running in an hc terminal, "
                "with this server on stdio (HC_TERMINAL_ID is unset)."
            )

        if action == "unlink":
            _hc("label", terminal, *(f"{key}=" for key in LINK_LABELS))
            return {"terminal": terminal, "linked": False}

        if action == "status":
            return _linked(terminal, _labels(terminal))

        client, workspace_slug = get_plane_client_context()

        if action == "link":
            if not workitem_identifier:
                return missing(action, "workitem_identifier")
            head, _, sequence = workitem_identifier.strip().upper().rpartition("-")
            if not head or not sequence.isdigit():
                return (
                    f"Error: invalid work item identifier {workitem_identifier!r}. "
                    "Expected PROJECT-N, for example AGENT-7."
                )
            item = client.work_items.retrieve_by_identifier(
                workspace_slug=workspace_slug, project_identifier=head, issue_identifier=int(sequence)
            )
            project = item.project.get("id") if isinstance(item.project, dict) else item.project
            return _link(terminal, f"{head}-{sequence}", str(item.id), str(project), item.name)

        if action == "create_and_link":
            if error := needs(action, project_id=project_id, name=name):
                return error
            item = client.work_items.create(
                workspace_slug=workspace_slug,
                project_id=project_id,
                data=CreateWorkItem(name=name, description_html=opt(description_html)),
            )
            identifier = client.projects.retrieve(workspace_slug=workspace_slug, project_id=project_id).identifier
            return _link(terminal, f"{identifier}-{item.sequence_id}", str(item.id), project_id, item.name)

        if not question:
            return missing(action, "question")
        linked = _linked(terminal, _labels(terminal))
        if not linked["linked"] or not linked["project_id"]:
            return (
                "Error: this session is not linked to a work item. Use `agent link` or `agent create_and_link` first."
            )
        project_id, workitem_id = linked["project_id"], linked["workitem_id"]

        client.work_items.comments.create(
            workspace_slug=workspace_slug,
            project_id=project_id,
            work_item_id=workitem_id,
            data=CreateWorkItemComment(comment_html=f"{rich_text('', question)}<p><em>{REPLY_HINT}</em></p>"),
        )
        label_id = _needs_you_label(client, workspace_slug, project_id)
        current = client.work_items.retrieve(
            workspace_slug=workspace_slug, project_id=project_id, work_item_id=workitem_id
        )
        labels = ids_of(current.labels)
        if label_id not in labels:
            client.work_items.update(
                workspace_slug=workspace_slug,
                project_id=project_id,
                work_item_id=workitem_id,
                data=UpdateWorkItem(labels=[*labels, label_id]),
            )
        return (
            f"Asked on {linked['workitem_identifier'] or workitem_id} and flagged it {NEEDS_YOU}. "
            "End your turn now and wait. The reply arrives as a message in this session; do not poll for it."
        )
