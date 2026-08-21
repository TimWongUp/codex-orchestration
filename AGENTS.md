# Codex Orchestration Agent Entry

## Scope

- `README.md` and `README.zh-CN.md` are human-facing. Read them only when changing public usage or installation behavior.
- Runtime behavior is defined by `SKILL.md`, `skills/`, `agents/`, `hooks/`, `references/`, and `scripts/`.
- This repository is the source of truth for portable runtime behavior. Installed Skills, Agents,
  and Hooks are deployment artifacts; task-package language, machine-specific routing, and registration stay outside the repository.
- The target local platforms are macOS and native Windows. Claim support only after both CI
  runners pass for the release candidate.
- When asked to install, update, repair, or verify this project, read `INSTALL.md` completely
  before changing user configuration. The installation contract, not a write installer, is the
  authority for target discovery, conflict handling, optional components, and verification.

## Commands

- Source validation: `python scripts/validate.py`
- Tests: `python -m unittest discover -s tests -v`
- Runtime validation: `python scripts/validate.py --runtime --codex-home <path> --skills-root <path>`

## Constraints

- Keep agent profiles model-neutral. User model routes live outside the repository.
- Keep task-package prose language local while canonical field names and control literals remain portable.
- Preserve unrelated files and hook registrations during Agent-driven installation.
- Keep `orchestration_route.py`, `subagent_scope.py`, and `subagent_guard.py` with this repository's orchestration contract; shared context, memory-routing, and closeout Hooks remain external runtimes, and machine-specific composition remains private configuration.
- Preserve author, source, revision, license metadata, and `THIRD_PARTY_NOTICES.md` when updating bundled third-party Skills.
- The main agent owns orchestration and Git; writable workers require the canonical lease in `references/worker-writing.md`.
- Public files must not contain personal paths, private endpoints, credentials, or machine-specific model IDs.
- Do not back-port edits from an installed runtime wholesale. Classify drift, preserve portable behavior here,
  and move host-specific choices into local configuration.

## Docs

- Architecture: `docs/architecture.md`
- Configuration: `docs/configuration.md`
- Hooks and prompt integration: `docs/hooks-and-prompts.md`
- Hook ownership decision: `docs/adr/0002-keep-orchestration-hooks-with-contract.md`
- Decisions: create `docs/adr/` only when a hard-to-reverse choice needs a durable record.

## Update gate

- Commands, installation behavior, or repository constraints changed: update this file.
- Public behavior changed: update both README files in the same change.
- A hard-to-reverse design decision changed: add or update an ADR.
- One-off validation output and current task status do not belong in durable docs.
