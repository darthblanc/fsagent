# Friction — informed consent, not a human gate

[← wiki home](index.md)

`core/friction.py:StandardFriction`, the pipeline default. Friction guards
**destructive parameters**: the first attempt fails informatively
(`FrictionRequired`, recorded as a denial at `stage: "friction"`), and the
second attempt — carrying the destructive parameter, or corrected text — is
an *informed action*. No human approval is involved; the mechanism converts
accidents into decisions.

## The three confirmations

### OVERWRITE — write, move, copy

Replacing something that exists requires `overwrite=true`.

Content replacement (write) reports what would be lost:

```
'/sb/report.txt' exists (421 lines) — pass overwrite=true, or use edit
```

Relocation collisions (move/copy, dest-flavored — no line count, since a
destination may be a folder):

```
destination '/sb/b.txt' exists — pass overwrite=true
```

An existing-**folder** destination never offers `overwrite=true` — folder
clobbering isn't expressible. The handler shapes the likely intent instead:

```
'/sb/archive' is an existing folder — pass the full destination path, e.g. '/sb/archive/a.txt'
```

### UNIQUE_MATCH — edit

`old_str` must occur exactly once. The shared helper
`unique_match_failure` (also used by the handler as defense in depth)
produces the two failures that are [edit's core design](tools/edit.md):

```
no exact match — nearest occurrence at line 87: 'revenue_2024 = 100' — re-read and retry with the current text
```

```
matched 3 locations (lines 12, 87, 240) — include more surrounding context to disambiguate
```

The first catches stale context; the second catches ambiguity. Both leave the
file untouched.

### RECURSIVE — delete

Deleting a non-empty folder requires `recursive=true`; the first attempt
reports the census so the confirmation is informed:

```
'/sb/proj' contains 14 files, 3 subfolders — pass recursive=true to confirm
```

`.gitkeep` markers are excluded from the census — a folder
[list_dir](tools/list_dir.md) shows as empty must count as empty.

## Placement

Friction is a **pipeline stage**, before execute: the gate reads the
declaration's `friction` set and the call's raw arguments. Handlers carry
slimmer duplicate guards for direct (non-pipeline) use, but the shaped
messages above come from the gate. Per-tool alternative suggestions (write's
"or use edit") live in `_OVERWRITE_ALTERNATIVES`.
