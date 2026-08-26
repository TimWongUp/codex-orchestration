# Add safe current-projection uninstall

**Status:** accepted

## Context

The deterministic installer could create, update, repair, and verify the current runtime projection
but offered no symmetrical removal path. Manual deletion made every operator rediscover the same
Skill, Agent, preference, and global-rule targets and increased the chance of deleting unrelated
local content.

ADR 0012 removed historical cleanup from ordinary installation. That boundary remains useful:
current releases can prove their named projection, but they cannot safely infer ownership of every
asset left by older releases.

## Decision

Add explicit `scripts/install.py --uninstall` planning and apply behavior. It removes the current
named Skill files, Agent profiles, and rendered task-language preference only when their bytes match
the current checkout. It removes a single well-formed global-rules block from either global
instruction candidate by its exact ownership markers, including when the block content is stale.
Changed managed files, linked targets, and malformed or duplicate markers fail closed and block the
whole plan. A selected runtime root that overlaps the source checkout also fails closed so managed
target mapping cannot delete repository sources; filesystem identity covers case aliases on
case-insensitive hosts. There is no force-delete mode.

Uninstall preserves all unmanaged files, model routing, Hooks, surrounding global instructions,
project rules, and extra files inside managed directories. It removes an owned directory only when
that directory becomes empty. Assets not present in the current source projection remain legacy
cleanup and require a separate user-directed maintenance action.

The same plan/apply boundary applies to installation and uninstall. Interactive use confirms the
displayed plan; non-interactive use is a dry run until `--apply`. Deletions are staged by atomic
same-directory moves so a caught mutation or absence-verification failure can restore the original
files before the verified commit. Cleanup after that commit is best effort: a failure leaves the
runtime absent, returns success with a warning, and identifies the recoverable staged copy instead
of attempting a partial rollback after other staged copies may already be gone.

## Consequences

Users gain one cross-platform command for global removal without broad directory deletion or manual
global-rule editing. Safe uninstall from a different or modified checkout may report byte conflicts;
the operator must use the matching checkout or first reconcile the managed runtime instead of
forcing deletion.

Successful uninstall proves only that the current named projection and owned global-rules block are
absent. It does not claim that historical Agents, Hooks, or other retired assets are absent, so it
does not reverse [ADR 0012](0012-remove-legacy-cleanup-from-installation.md).
