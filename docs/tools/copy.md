# copy — duplicate (the canonical composed tool)

[← tool index](index.md) · `tools/copy.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| mutate-structure | both | **read ∘ write** | read(src) ∧ mutate-structure(dest) | ✓ | — | overwrite |

> Copy a file or folder to a new path. Use this to duplicate content — never
> read a file and re-write it to copy it. Replacing an existing destination
> file requires overwrite=true.

## Args

`src` (required) · `dest` (required).

Not model-settable: `overwrite`, set by the harness only after a human
approves replacing an existing destination file.

## Returns

Confirmation + tier flag: `copied '/sb/a.txt' → '/sb/b.txt'`.

## Below the membrane

The implementation is literally the declared composition:
`write_bytes(dest, read_bytes(src))`. **Zero tokens regardless of file
size, perfect fidelity** — versus ~2× file size in tokens plus
regeneration-corruption risk if content round-tripped through context.
Folder copies walk the tree composing the same two primitives.

## The anti-exfiltration policy map

```python
policy_map={"src": ToolGroup.READ, "dest": ToolGroup.MUTATE_STRUCTURE}
```

- `read(src)` — without it, copy would smuggle content out of read-*denied*
  zones.
- `mutate-structure(dest)` — and **only** on dest, so copying *out of* a
  merely read-only zone is permitted. This enables the
  duplicate-then-experiment workflow that read-only
  [policy](../policy.md) zones encourage: deny on `originals/` + copy out is
  the standard recovery from a denial.

See [Tool declarations](../tool-declarations.md#the-per-arg-policy-map) for
the mechanism.

## The worked example for the transform pattern

Every future transform is a named, parameterized composition of primitives
with a policy map, entering the registry exactly like copy did. See
[Roadmap](../roadmap.md#the-transform-group).

## Friction & failure shaping

Identical collision behavior to [move](move.md): `destination '…' exists —
pass overwrite=true` for files, full-path hint for folder destinations, plus
not-found suggestions, identical-path and into-itself refusals, and the
missing-parent `create_dir` hint.
