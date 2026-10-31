# The tool surface

**14 tools**, one per Plane resource plus `agent`, each taking an `action` parameter that selects the operation. 79 actions in total. Only resources Plane Community Edition supports are exposed.

```python
workitem(action="create", project_id=..., name="Fix login")
workitem(action="list", project_id=...)
cycle(action="archive", project_id=..., cycle_id=...)
```

A compact catalogue — 14 tools, ~25k characters — loads fully in every MCP client and leaves the context budget to the conversation.

Five parts, in this order:

```python
NAME = "label"                       # 1. identity
TITLE = "Labels"

ACTIONS = (                          # 2. the declaration -- single source of truth
    Action("list", ("project_id",), ("cursor", "per_page"), read=True),
    Action("create", ("project_id", "name"), ("color", "description")),
    Action("delete", ("project_id", "label_id"), destructive=True),
)

FOOTER = "color is a hex code such as #EF4444."   # 3. cross-cutting notes
LEGACY = {"list_labels": "list", ...}             # 4. retired name -> action

def register(mcp):                                # 5. dispatch
    @mcp.tool(
        name=NAME,
        description=build_description("Labels within a project.", ACTIONS, FOOTER),
        annotations=build_annotations(TITLE, ACTIONS),
    )
    def label(action: Literal["list", "create", "delete"], project_id: str = "", ...):
        ...
```

`ACTIONS` generates the description, the MCP annotations *and* argument validation, so documentation cannot drift from behaviour. Add the module, add one entry to `registry.py`, done.

## Conventions

| Rule | Why |
|---|---|
| Parameters are plain typed defaults (`= ""`, `= 0`) | `X \| None` renders a verbose `anyOf`-with-null block. Use `bool \| None` only where `False`/`0` is a real value distinct from unset — and say so in a comment |
| Validate enums with `one_of()` | They are `str` in the schema; an unchecked value is dropped from the payload and the write reports success |
| Declare every parameter an action takes, and only those | `ValidateActionArguments` checks calls against it. `query` is a real `workitem` parameter but useless to `list` — sent there it would validate cleanly and answer a different question |
| Use `needs()` for multi-parameter guards | It names only what is absent. `if not a or not b` blames both, so a caller that supplied `a` is told to send it again |
| An action accepting `cursor` must return `envelope(response)` | Returning `response.results` lets a caller page in but never page on |
| Match the SDK's `params` type: `page_params` vs `as_params` | Some endpoints take a `Mapping`, others a Pydantic model they call `.model_dump()` on. The wrong one raises at call time |
| Declare the type you mean | `CoerceArguments` repairs `'["uuid"]'` before validation, so type a list as a list. `coerce_list` is for parameters genuinely declared `str`, where a comma separates |
| The surface spells it `workitem`; `plane-sdk` spells it `work_item` | Tool names, actions and parameters use `workitem`; SDK namespaces and kwargs keep `work_item`. `test_vocabulary.py` pins both directions |

## Layout

| Path | Contents |
|---|---|
| `<resource>.py` | one module per resource |
| `registry.py` | `RESOURCES` in advertised order, plus the alias tables |
| `legacy.py` | `LegacyNames` — resolves retired tool names |
| `../toolkit/` | shared helpers — see [`../toolkit/README.md`](../toolkit/README.md) |

`RESOURCES` is an explicit tuple, not a directory scan. Its order is the advertised order and therefore a wire-format guarantee: tool definitions head a client's prompt cache, so reordering invalidates live conversations. `test_resource_order_is_pinned` holds it to a literal list.

## Listing transforms

Both implement `list_tools`/`get_tool` only, so execution keeps the full schema and results are unchanged.

| Transform | Effect |
|---|---|
| `StripOutputSchemas` | Drops `outputSchema` from the listing — roughly two-thirds of the wire payload, for a field no client forwards to a model |
| `LegacyNames` | Resolves a retired tool name to its `(tool, action)` pair, with `action` hidden and pre-filled |

## Retired tool names

Before consolidation this server exposed one tool per API operation. **67 still resolve**, unadvertised — so they cost nothing in the listing, but a saved prompt calling `create_work_item` keeps working, including the parameter names it shipped with (`work_item_id`, not `workitem_id`). Every resolution is logged, so the remaining callers are an observation rather than a guess.

**3 cannot be mapped.** An alias renames a tool; it cannot reshape one, and these chose between two operations with a parameter (`manage_project_archive(archive=False)`). Each is declared in its module's `LEGACY_UNMAPPED` with the replacement to use.

Names for resources and actions this Community Edition fork removed no longer resolve. `tests/tools/_retired_names.py` is the frozen record of the 70 that remain; the conformance suite asserts every one is aliased, declared unmappable, or still registered.

## Tools

| Tool | Actions |
|---|---|
| `cycle` | `list` · `retrieve` · `create` · `update` · `delete` · `list_workitems` · `manage_workitems` · `transfer_workitems` · `complete` · `archive` · `unarchive` |
| `intake` | `list` · `retrieve` · `create` · `update` · `delete` |
| `label` | `list` · `retrieve` · `create` · `update` · `delete` |
| `member` | `me` · `list_workspace` · `list_project` |
| `module` | `list` · `retrieve` · `create` · `update` · `delete` · `list_workitems` · `manage_workitems` · `archive` · `unarchive` |
| `project` | `list` · `retrieve` · `create` · `update` · `delete` · `archive` · `unarchive` |
| `state` | `list` · `retrieve` · `create` · `update` · `delete` |
| `workitem` | `list` · `retrieve` · `retrieve_by_identifier` · `search` · `create` · `update` · `delete` · `manage_assignee` · `manage_label` |
| `workitem_activity` | `list` · `retrieve` |
| `workitem_attachment` | `list` · `read` · `download_url` · `upload_from_url` · `upload_from_path` · `delete` |
| `workitem_comment` | `list` · `retrieve` · `create` · `update` · `delete` |
| `workitem_link` | `list` · `retrieve` · `create` · `update` · `delete` |
| `workitem_relation` | `list` · `create` |
| `agent` | `link` · `create_and_link` · `unlink` · `status` · `ask` |

Every tool's own description lists its actions with their required and optional
parameters; that description is generated from `ACTIONS` and is the authoritative
reference at call time.

## Tests

```bash
pytest tests/tools -q        # no network, no credentials
```

Every action of every resource runs against `SpyClient`, a stand-in that binds
each call against the genuine `plane-sdk` signature and type-checks the
arguments. Payload-shape mistakes a plain mock would accept — a flat body where
the SDK wants a nested model, a dict where it wants a Pydantic object — are
caught here rather than at runtime.

| File | Guarantees |
|---|---|
| `test_conformance.py` | Surface-wide invariants: tool count, listing size, strict-mode schemas, annotations derived from `ACTIONS`, catalogue order pinned, every retired name accounted for |
| `test_dispatch.py` | Every action reaches the SDK with well-typed arguments; called bare, it names what is missing instead of issuing a request |
| `test_guards.py` | Omitting one declared required parameter names *that* parameter and no other |
| `test_pagination.py` | An action declaring `cursor` returns a `next_cursor` |
| `test_vocabulary.py` | `workitem` everywhere a model reads; `work_item` preserved in SDK calls and retired names |
| `test_references.py` | Every backticked `tool action` in a description, and in the server instructions resolves |
| `test_state.py` | Triage can be neither created nor flagged; project-state fields reach the SDK |
| `test_attachments.py` | The image-versus-text return channel, size limits, the SSRF guard, and local-path uploads |
| `test_agent.py` | `agent` links by hc labels only, leaves `plane.session` to the bridge, and `ask` flags the item `needs-you` |
