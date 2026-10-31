"""Workflow states: the groups and flags a caller may and may not set."""

from __future__ import annotations

PROJECT = "project-1"


def test_triage_is_not_a_settable_group(registered, spy):
    """Plane creates the triage state itself and the serializer refuses `group=triage`."""
    result = registered["state"].fn(
        action="create", project_id=PROJECT, name="Blocked", color="#EF4444", group="triage"
    )

    assert isinstance(result, str) and "backlog" in result
    assert "triage" not in result.removeprefix("Error: group must be one of: "), "offered triage back"
    assert not spy.recorder.calls, "asked Plane for something it would refuse"


def test_the_triage_flag_is_not_settable(registered):
    """`is_triage=True` used to be accepted, and Plane created a state that no endpoint
    could reach again: both the list and the delete queryset filter `is_triage=False`."""
    assert "is_triage" not in registered["state"].parameters["properties"]


def test_default_reaches_the_sdk(registered, spy):
    registered["state"].fn(
        action="create", project_id=PROJECT, name="Blocked", color="#EF4444", group="started", default=True
    )

    assert spy.recorder.only().kwargs["data"].default is True
