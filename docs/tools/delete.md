# delete — remove (the sharpest tool)

[← tool index](index.md) · `tools/delete.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| mutate-structure | both | primitive | mutate-structure | ✓ | — | recursive |

> Delete a file or folder. Deleting a non-empty folder requires
> recursive=true — the first attempt will tell you what's inside.

## Args

`path` (required) · `recursive` (default false).

## Returns

Confirmation (+ census for recursive deletions) + tier flag:

```
deleted '/sb/proj' (14 files, 3 subfolders)
tier 3 — contents NOT recoverable from history
```

## Friction-as-informed-consent

A non-empty folder fails first with the census, so the `recursive=true`
retry is an informed action — no human gate needed
([Friction](../friction.md)):

```
'/sb/proj' contains 14 files, 3 subfolders — pass recursive=true to confirm
```

`.gitkeep`-only folders count as empty — a folder
[list_dir](list_dir.md) shows as empty must not demand confirmation over a
marker the model can't see.

## Recoverability

- **Tier 1/2**: content lives in git history (the auto-commit *before* each
  mutation; future `fsagent history <path>` retrieves it).
- **Tier 3**: flagged loudly at the moment of loss — `contents NOT
  recoverable from history` — computed *before* the bytes disappear.
- **Below the membrane**, deletion is actually staged to `_trash/` — the
  model never knows, read/search tools can't see it, and the user empties at
  will. See [Tiers & recovery](../tiers-and-recovery.md) for the full
  design (uniquing, real-deletion inside `_trash/`, why the OS recycle bin
  never applies).

## Failure shaping

```
'/sb/reprot.txt' not found — similar paths: /sb/report.txt
```
