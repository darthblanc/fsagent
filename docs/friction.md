# Friction — informed consent, with a human gate on top

[← wiki home](index.md)

`core/friction.py:StandardFriction`, the pipeline default. Friction guards
**destructive parameters**: the first attempt fails informatively
(`FrictionRequired`, recorded as a denial at `stage: "friction"`), and the
second attempt — carrying the destructive parameter, or corrected text — is
an *informed action*. The pipeline stage itself never blocks on a human; it's
purely mechanical — is the flag true, and if not, does the precondition that
needs it hold. The **agent layer** ([Agent & sub-agents](agent.md)) is what
actually pauses for a human: every `FrictionRequired` carries a `kwarg` (set
here, at the only place that knows which check fired) naming the parameter a
human's approval should force to `True` on retry, or `None` when there's
nothing to force and the model must self-correct instead. The model can never
set any of these flags itself — `overwrite`, `recursive`, and `replace_all`
are excluded from its tool schema (`agent/schema.py`), so the *only* way one
becomes `True` is a human-approved retry.

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
produces the message text for the two failures that are
[edit's core design](tools/edit.md), but the friction gate (`_check_unique_match`)
independently inspects the match count to decide whether a human gets
involved — the two failures aren't symmetric:

**Zero matches** — catches stale context, stays autonomous (`kwarg=None`):
there's no flag a human's "yes" could set, since the text genuinely isn't in
the file. The model re-reads and retries on its own, no gate:

```
no exact match — nearest occurrence at line 87: 'revenue_2024 = 100' — re-read and retry with the current text
```

**2+ matches** — catches ambiguity, and *is* gated (`kwarg="replace_all"`):
a human can sensibly approve "replace every one of them," so this pauses for
a decision exactly like OVERWRITE/RECURSIVE. Unlike those two, "always"
never persists for `replace_all` — every ambiguous edit re-asks, since each
one is a fresh decision about a different string in a different file:

```
matched 3 locations (lines 12, 87, 240) — pass replace_all=true to replace all of them, or include more surrounding context to disambiguate one
```

Both leave the file untouched on denial.

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
