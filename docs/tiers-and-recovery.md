# Tiers & recovery

[← wiki home](index.md)

The harness states exactly what guarantee it can keep for every file, and
never silently pretends a guarantee holds where it doesn't.

## The tiers (`core/tiers.py`)

| Tier | Files | Guarantee |
|---|---|---|
| 1 | Text formats | Tracked, diffable, revertible — full contract |
| 2 | Ordinary binaries (null-byte sniff) | Tracked and revertible; diffs degrade to size changes |
| 3 | Over the size threshold (default 50 MB, configurable per pipeline) | **Untracked — not reversible, flagged loudly** |

Tier surfaces in four places: [inspect](tools/inspect.md) output (*before*
acting), mutation results (*after* acting — `tier 3 — this change is NOT
reversible`), every [trajectory](trajectory.md) entry, and folder summaries
(`tier_3_files` counts).

## The git stage (`core/gitstage.py`)

Tools declaring `git=True` auto-commit the whole sandbox tree after a
successful execute:

- Repo initialized in the sandbox on first commit (`user.name fsagent`).
- `git add -A`, then commit with message `{tool} [session={id} request={n}]`
  — every mutation traceable to a trajectory entry.
- **Tier-3 exclusion**: before each commit, files over the threshold are
  written into `.git/info/exclude`, so they are never tracked. (Known edge:
  a file that grows past the threshold *after* being tracked stays tracked.)
- Whole-tree staging makes moves appear as **renames** in diffs and history,
  so review reads naturally and revert restores the old path.
- `create_dir` drops a `.gitkeep` inside new folders (git cannot track empty
  directories), so rollback restores them; `list_dir` hides the marker.

## Deletion staging — `_trash/`, below the membrane

`delete` does not delete. Through the pipeline it **moves** the target to
`_trash/<relative path>` under the sandbox root (repeat deletions are
uniqued: `a.txt`, `a.txt~1`). Three properties:

1. **The model never knows.** Confirmations say `deleted '…'`; the
   description says delete; and `HIDDEN_DIRS` (`_trash`, `.git`) are filtered
   from list_dir, glob, grep, and inspect, so "deleted" files never resurface
   in searches and the git plumbing is equally invisible.
2. **The user empties at will** — manually for now (`rm -rf sandbox/_trash`);
   a `fsagent empty-trash` command is flagged for the CLI. A delete targeting
   a path already inside `_trash/` performs a *real* deletion, so emptying
   via the agent works when explicitly requested.
3. **It strictly improves the tier-3 story.** A move preserves bytes, so even
   untracked oversized files remain recoverable until the trash is emptied —
   the one case git history cannot cover. The model still sees the honest
   flag (`contents NOT recoverable from history`), because it must not rely
   on machinery it cannot observe.

Direct handler use without an injected `sandbox_root` deletes for real.

Note: the OS trash/recycle bin never applies — it is a desktop-shell
convention, and programmatic deletion via syscalls bypasses it entirely.
fsagent's git history and `_trash/` are the replacement.

## Recoverability matrix

| What happened | Tier 1/2 | Tier 3 |
|---|---|---|
| Overwritten / edited | git history (`git show`, future `fsagent history <path>`) | **gone** — flagged at mutation time |
| Deleted | `_trash/` (until emptied), else git history | `_trash/` (until emptied), else **gone** |
| Moved | history shows the rename; revert restores the old path | bytes preserved by the move itself |
