# Roadmap

[← wiki home](index.md)

The live register of open design debts is [FLAGS.md](../FLAGS.md) at the repo
root — flags are recorded when raised in design discussion and removed when
resolved (the Resolved section keeps the history). Summary as of June 2026:

## Open flags

1. **`fsagent history <path>` + session `--scope`** (cli/) — the command that
   makes "tier-1/2 deletions are recoverable" actionable; `fsagent
   empty-trash` pairs with it; `--scope` intersects the standing
   [policy](policy.md) as a narrowing wrapper. `agent/`, `cli/`, and
   `prompts/` are otherwise built — see [Architecture](architecture.md#directory-map).
2. **Write/edit handler extensions** — format-aware write validation and
   structured edit selectors (a JSON path, a CSV cell), reusing the
   per-format handlers read/inspect already have.
3. **Grep handler-aware match modes** — e.g. CSV column-scoped search.
4. **Composed `policy_union` reconciliation** — validate declared unions
   against the actual groups of composed functions, once a function→group
   registry exists.

## The transform group

The fifth tool group, `transform`, is reserved in the schema (declaring it is
rejected). The design is already demonstrated: every future transform is a
named, parameterized composition of primitives with a per-arg
[policy map](tool-declarations.md#the-per-arg-policy-map), entering the
registry exactly like [copy](tools/copy.md) did.
