"""Server instructions, sent to a client before it lists the tools.

The recipes name the tools that do each step, so `test_references.py` follows
every one of them and fails if a name stops resolving.
"""

from __future__ import annotations

SERVER_INSTRUCTIONS = """
## Plane Community Edition

This server talks to Plane Community Edition. There are no work item types, epics,
pages, milestones, releases or query filters (PQL).

- Work items always belong to a project; ask which if one is not named.
- Find a work item across projects: `workitem search` with query=... .
- List a project's work items: `workitem list` with project_id, then filter the
  results yourself — the listing takes no filter.
- Nest a work item: `workitem update` with parent=<work item id>.
"""
