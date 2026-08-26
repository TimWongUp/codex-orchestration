# Remove legacy cleanup from installation

**Status:** accepted

## Context

The project no longer installs a Hook, but routine setup still carried authenticated cleanup for
older Agent profiles, Hook scripts, and `hooks.json` registrations. That compatibility branch had
to parse platform-specific shell commands, infer path aliases, maintain historical hashes, plan
deletions, and prove that unrelated user configuration survived. Most installer and validator
complexity existed only to support that retired runtime rather than the current projection.

The installation trust boundary should be smaller than the user configuration it enters. A current
release can prove the files it owns without permanently interpreting every historical form that may
still exist in a Codex home.

## Decision

The deterministic installer manages only the current named Skill files, Agent profiles, saved task
language, and marker-delimited global-rules block. Its normal plan contains create and update
writes; it does not plan deletion of pre-existing files, parse `hooks.json`, inspect the Hook
directory, or classify extra Agent profiles. Rollback may still remove a managed file created by the
failed transaction.

Runtime validation likewise checks only the current managed projection. Unmanaged Agent and Hook
assets, including files left by earlier project versions, are ignored. The source contract still
keeps this project Hook-free.

Legacy cleanup becomes a separate user-directed maintenance action. It must resolve the live
targets, present the exact removal plan, and obtain explicit approval independently of installation.
Successful setup or runtime validation makes no claim that historical assets are absent.

This decision supersedes the authenticated-cleanup portions of
[ADR 0008](0008-deterministic-installer-and-global-rules.md) and
[ADR 0010](0010-retire-orchestration-hook-and-rigid-briefs.md). It does not reverse the decision to
keep Hooks out of the current suite.

## Consequences

Ordinary installation loses its cleanup deletions, historical hashes, Hook JSON and shell command
parsers, and the tests dedicated to those compatibility paths. The retained suite focuses on
current projection integrity, transactions, path safety, cross-platform behavior, and active policy
contracts. [ADR 0013](0013-safe-current-projection-uninstall.md) later adds an explicit uninstall
for the byte-matching current projection without restoring historical cleanup.

An upgrade may leave an older Agent or Hook active until the user chooses to remove it. This is an
explicitly unmanaged runtime condition rather than an installation failure. Operators who need a
clean legacy cutover perform and verify that cleanup as its own maintenance task.
