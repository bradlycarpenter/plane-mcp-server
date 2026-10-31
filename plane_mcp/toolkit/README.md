# toolkit

Shared building blocks for the tool surface, split by *when* they act. All re-exported from `__init__.py`, so a resource module needs one import.

| Module | Acts at | Provides |
|---|---|---|
| `spec.py` | declaration | `Action`, `build_description`, `build_annotations` |
| `runtime.py` | call | `missing`, `needs`, `require`, `one_of`, `opt`, `coerce_list`, `page_params`, `as_params`, `ids_of` |
| `mentions.py` | call | `render_mentions`, `tokenize_mentions`, `mention_user_ids`, `project_mention_error` |
| `paging.py` | response | `envelope`, `dump_results`, `workitem_page` |
| `transforms.py` | listing | `StripOutputSchemas` |

Nothing here knows which catalogue is calling it. Anything encoding this server's own history — the `RESOURCES` tuple, retired names — lives under `tools/`.
