# Testing

[← wiki home](index.md)

The suite (303 tests, `tests/`) was written strictly test-first: every
feature's tests were written and confirmed failing before its implementation
existed; refactors happen only under green.

## Run it

```sh
uv venv && uv pip install -e ".[dev]"
uv run pytest -q
```

The one expected warning is `ComposedPolicyWarning` from the schema test
that proves a composed tool *without* a policy map still surfaces the
cartesian-fallback note.

## Conventions

- **Exact-string assertions for shaped messages.** Failure shaping is the
  product, so its strings are pinned verbatim —
  `tests/test_edit_tool.py` asserts the unique-match failures
  character-for-character, `tests/test_grep_tool.py` asserts that the capped
  notice contains no `offset=`. Changing a shaped message is a deliberate,
  test-visible act.
- **One test file per tool** (`test_<tool>_tool.py`): a `TestDefinition`
  class pinning the declaration to the spec table, then behavior classes
  (happy paths, pagination, failure shaping, tier flags).
- **Layer tests**: `test_functions.py` (primitives), `test_tool_definition.py`
  (schema validation), `test_sandbox`-behavior inside `test_pipeline.py`,
  `test_policy.py` (rule engine against the canonical YAML), `test_friction.py`
  (the gate in isolation), `test_gitstage.py` (real git subprocess),
  `test_tiers.py`.
- **Pipeline integration** (`test_pipeline.py`): end-to-end calls through all
  six stages with stub or YAML policies — including the invariants that are
  easy to break silently: anti-exfiltration, trash invisibility
  (`list_dir` of a sandbox containing only `.git` and `_trash` returns
  `(empty folder)`), recoverability (`git show HEAD^:r.txt` after a delete),
  and friction-deny-then-informed-retry sequences.
- **Handlers are unit-tested directly** with `tmp_path` (no pipeline), since
  they receive plain resolved `Path`s; pipeline-only behavior (injection,
  staging, policy) is tested through `Pipeline.call`.

## Invariants worth knowing before you touch code

- The model-facing surface of delete must never mention `_trash`
  ([Tiers & recovery](tiers-and-recovery.md)).
- `HIDDEN_DIRS` filtering in the four read/search tools.
- A primitive's `policy_union` equals `{group}`; composed maps union to
  exactly `policy_union`.
- Friction failures must leave the target untouched (asserted everywhere).
