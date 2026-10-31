"""The agent tool: linking is hc labelling, and ask leaves a question where a person will see it."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from plane_mcp.tools import agent


def _page(*labels, more=False):
    return SimpleNamespace(results=list(labels), next_page_results=more, next_cursor="100:1:0")


def _label(name, id_):
    return SimpleNamespace(name=name, id=id_)


@pytest.fixture
def unlinked(hc):
    hc.labels = {"plane.session": "s1"}
    return hc


def test_link_labels_the_terminal_with_the_resolved_work_item(registered, spy, unlinked):
    spy.returns["work_items.retrieve_by_identifier"] = SimpleNamespace(id="w1", project="p1", name="Fix login")

    result = registered["agent"].fn(action="link", workitem_identifier="agent-7")

    call = spy.recorder.only()
    assert (call.kwargs["project_identifier"], call.kwargs["issue_identifier"]) == ("AGENT", 7)
    assert unlinked.commands[-1] == ("label", "t9", "plane.issue=w1", "plane.ref=AGENT-7", "plane.project=p1")
    assert result["workitem_identifier"] == "AGENT-7" and result["name"] == "Fix login"


def test_link_refuses_a_malformed_identifier_before_touching_anything(registered, spy, unlinked):
    result = registered["agent"].fn(action="link", workitem_identifier="AGENT")

    assert result.startswith("Error:") and "PROJECT-N" in result
    assert not spy.recorder.calls
    assert not any(command[0] == "label" for command in unlinked.commands)


def test_create_and_link_links_the_new_item_by_its_project_identifier(registered, spy, unlinked):
    spy.returns["work_items.create"] = SimpleNamespace(id="w2", sequence_id=12, name="New")
    spy.returns["projects.retrieve"] = SimpleNamespace(identifier="AGENT")

    result = registered["agent"].fn(action="create_and_link", project_id="p1", name="New")

    assert spy.recorder.methods == ["work_items.create", "projects.retrieve"]
    assert unlinked.labels["plane.ref"] == "AGENT-12"
    assert unlinked.labels["plane.issue"] == "w2"
    assert result["linked"] is True


def test_unlink_clears_the_link_and_leaves_the_bridges_session_label(registered, hc):
    hc.labels["plane.session"] = "s1"

    result = registered["agent"].fn(action="unlink")

    assert hc.labels == {"plane.session": "s1"}
    assert result == {"terminal": "t9", "linked": False}


def test_status_reports_the_link_from_the_labels(registered, hc):
    result = registered["agent"].fn(action="status")

    assert result["linked"] is True
    assert (result["workitem_identifier"], result["workitem_id"], result["project_id"]) == ("ENG-1", "w", "p")


def test_status_of_an_unlinked_session(registered, unlinked):
    assert registered["agent"].fn(action="status") == {"terminal": "t9", "linked": False}


def test_ask_needs_a_linked_session(registered, spy, unlinked):
    result = registered["agent"].fn(action="ask", question="Which colour?")

    assert result.startswith("Error:") and "agent link" in result
    assert not spy.recorder.calls


def test_ask_posts_the_question_creates_needs_you_and_flags_the_item(registered, spy, hc):
    spy.returns["labels.list"] = _page(_label("bug", "l1"))
    spy.returns["labels.create"] = _label("needs-you", "ny")
    spy.returns["work_items.retrieve"] = SimpleNamespace(labels=["l1"])

    result = registered["agent"].fn(action="ask", question="Red <or> blue?")

    comment = next(c for c in spy.recorder.calls if c.method == "work_items.comments.create")
    assert (comment.kwargs["project_id"], comment.kwargs["work_item_id"]) == ("p", "w")
    assert "Red &lt;or&gt; blue?" in comment.kwargs["data"].comment_html
    assert "@claude" not in comment.kwargs["data"].comment_html.lower()
    created = next(c for c in spy.recorder.calls if c.method == "labels.create")
    assert created.kwargs["data"].name == "needs-you"
    update = next(c for c in spy.recorder.calls if c.method == "work_items.update")
    assert update.kwargs["data"].labels == ["l1", "ny"]
    assert "End your turn" in result


def test_ask_reuses_an_existing_needs_you_label_on_a_later_page(registered, spy, hc):
    pages = iter([_page(_label("bug", "l1"), more=True), _page(_label("Needs-You", "ny"))])
    original = spy.labels.list

    def paged(**kwargs):
        original(**kwargs)
        return next(pages)

    spy.labels.__dict__["_cache"]["list"] = paged
    spy.returns["work_items.retrieve"] = SimpleNamespace(labels=[])

    registered["agent"].fn(action="ask", question="?")

    assert "labels.create" not in spy.recorder.methods
    assert spy.recorder.methods.count("labels.list") == 2
    update = next(c for c in spy.recorder.calls if c.method == "work_items.update")
    assert update.kwargs["data"].labels == ["ny"]


def test_ask_does_not_rewrite_labels_already_flagged(registered, spy, hc):
    spy.returns["labels.list"] = _page(_label("needs-you", "ny"))
    spy.returns["work_items.retrieve"] = SimpleNamespace(labels=["ny"])

    registered["agent"].fn(action="ask", question="?")

    assert "work_items.update" not in spy.recorder.methods


def test_refused_outside_an_hc_terminal(registered, spy, hc, monkeypatch):
    monkeypatch.delenv("HC_TERMINAL_ID")

    result = registered["agent"].fn(action="status")

    assert result.startswith("Error:") and "HC_TERMINAL_ID" in result
    assert not hc.commands


def test_refused_over_http_even_inside_an_hc_terminal(registered, spy, hc, monkeypatch):
    """Over HTTP the terminal is the server's, not the caller's."""
    monkeypatch.setattr(agent, "is_local", lambda: False)

    result = registered["agent"].fn(action="unlink")

    assert result.startswith("Error:")
    assert not hc.commands
