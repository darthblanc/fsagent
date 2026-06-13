# Tool declarations

[← wiki home](index.md)

Every tool is an instance of `ToolDefinition` (`core/tool_definition.py`), a
frozen Pydantic model. The declaration is the tool's contract with the
pipeline: what it may touch, what permission classes it exercises, which
destructive parameters require confirmation, and whether it is composed.
Declarations are immutable values fixed at definition time — the model cannot
influence them.

## Fields

| Field | Type | Meaning |
|---|---|---|
| `name` | str | snake_case identifier |
| `group` | ToolGroup | `read`, `search`, `mutate-content`, `mutate-structure` (`transform` exists but is **reserved** — declaring it is rejected) |
| `friction` | frozenset[Friction] | destructive-parameter confirmations: `recursive`, `overwrite`, `unique-match` (default: none) |
| `composition` | `"primitive"` \| tuple[str, ...] | primitive, or the function names it composes |
| `policy_union` | frozenset[ToolGroup] | every permission class the tool's execution can exercise |
| `policy_map` | dict[str, ToolGroup] \| None | composed tools only: which group each path arg experiences |
| `targets` | Targets | `files`, `folders`, or `both` |
| `pagination` | bool | results are paged |
| `git` | bool | mutations auto-commit ([Tiers & recovery](tiers-and-recovery.md)) |

## Validation rules

The schema rejects, at construction time:

- non-snake_case names (tool or composed function names);
- the reserved `transform` group, in `group` or `policy_union`;
- empty `policy_union`;
- empty or duplicate-bearing composition lists;
- a **primitive** whose `policy_union ≠ {group}` — a primitive is exactly its
  own policy;
- a **composed** tool whose `policy_union` lacks its own `group`;
- a `policy_map` on a primitive, an empty map, or a map whose groups don't
  union to exactly `policy_union`.

## Primitive vs composed

A primitive tool corresponds to one function in `functions/` and one policy
group. A composed tool names the functions it composes — copy declares
`composition=("read", "write")` — and spans multiple policy groups.

### The per-arg policy map

Composed tools declare which group each path argument experiences:

```python
policy_map={"src": ToolGroup.READ, "dest": ToolGroup.MUTATE_STRUCTURE}
```

This is copy's **anti-exfiltration rule**: read is checked on `src` (so copy
cannot smuggle content out of read-denied zones) and mutate-structure on
`dest` — and *only* those, so copying out of a merely read-only zone is not
over-denied. Without a map, the pipeline falls back to the cartesian check
(every path × every group in `policy_union`), which fails closed: it can
over-deny but never under-deny.

### ComposedPolicyWarning

Declaring a composed tool **without** a `policy_map` emits
`ComposedPolicyWarning`, restating the cartesian-fallback consequences. The
fallback is never silent.

## The Tool dataclass

`core/tool.py` binds a declaration to its implementation:

```python
@dataclass(frozen=True)
class Tool:
    definition: ToolDefinition
    description: str            # the ONLY model-facing prose
    handler: Callable[..., str] # execute stage; receives resolved Paths
    conditional_groups: Callable[[dict], tuple] | None = None
```

`conditional_groups` declares args-dependent policy requirements beyond
`policy_union` — grep uses it to require `read` only when `mode="content"`.
See [Policy](policy.md#mode-conditional-requirements).

## Deferred

Reconciling a composed tool's declared `policy_union` against the actual
groups of its composed functions awaits a function→group registry — flag 4 in
[FLAGS.md](../FLAGS.md).
