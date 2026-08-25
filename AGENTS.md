# Codex Orchestration Agent Entry

## Scope

- `README.md` and `README.zh-CN.md` are human-facing. Read them only when changing public usage or installation behavior.
- Runtime behavior is defined by `SKILL.md`, `skills/`, `agents/`, `references/`, and `scripts/`.
- This repository is the source of truth for portable runtime behavior. Installed Skills, Agents,
  and global rules are deployment artifacts; task-package language, machine-specific routing, and unrelated Hook registration stay outside the repository.
- The target local platforms are macOS and native Windows. Claim support only after both CI
  runners pass for the release candidate.
- When asked to install, update, repair, or verify this project, read `INSTALL.md` completely
  before changing user configuration. `INSTALL.md` defines the contract and `scripts/install.py`
  is its deterministic implementation for planning, ownership checks, writes, rollback, and
  verification. Agents use its non-interactive dry run before `--apply`; do not reproduce
  installation with ad hoc copies.

## Commands

- Use the Python interpreter command available on the host (`python3`, `py -3`, or `python`) for `<python>` below.
- Source validation: `<python> scripts/validate.py`
- Tests: `<python> -m unittest discover -s tests -v`
- Lint: `ruff check .`
- Format check: `ruff format --check .`
- Type check: `pyright`
- Runtime validation: `<python> scripts/validate.py --runtime --codex-home <path> --skills-root <path>`
- Interactive install: `<python> scripts/install.py`
- Non-interactive install dry run: `<python> scripts/install.py --language <en|zh-CN>`

## Constraints

- Keep agent profiles model-neutral. User model routes live outside the repository.
- Keep delegation prose language local while role names, paths, and external protocol literals remain portable.
- Deterministic installation writes only the current named projection. Preserve all unmanaged
  Agent profiles, Hook registrations, Hook files, and other user content; legacy cleanup is a
  separate user-directed maintenance action.
- Keep the managed global-rules block canonical in `examples/global-agents-block.md`; installation
  injects it into the active global `AGENTS.md` or `AGENTS.override.md` without owning surrounding
  user content.
- Runtime verification checks only current managed copies and ignores unmanaged Agent and Hook
  assets. This repository installs no Hook; shared context, memory-routing, and closeout Hooks
  remain external runtimes.
- Preserve author, source, revision, license metadata, and `THIRD_PARTY_NOTICES.md` when updating bundled third-party Skills.
- Each root task owns orchestration and its local Git; writable workers require the canonical lease
  in `references/worker-writing.md`. The Integration Root alone owns cross-worktree integration and
  final delivery under `references/worktree-roots.md`.
- Public files must not contain personal paths, private endpoints, credentials, or machine-specific model IDs.
- Do not back-port edits from an installed runtime wholesale. Classify drift, preserve portable behavior here,
  and move host-specific choices into local configuration.

## Docs

- Architecture: `docs/architecture.md`
- Configuration: `docs/configuration.md`
- Hooks and prompt integration: `docs/hooks-and-prompts.md`
- Hook and brief-format decision: `docs/adr/0010-retire-orchestration-hook-and-rigid-briefs.md`
- Installation ownership decision: `docs/adr/0008-deterministic-installer-and-global-rules.md`
- Worktree-root decision: `docs/adr/0009-coordinate-independent-worktree-roots.md`
- Delivery Review boundary decision: `docs/adr/0011-separate-delivery-review-from-orchestration.md`
- Legacy cleanup boundary decision: `docs/adr/0012-remove-legacy-cleanup-from-installation.md`
- Decisions: create `docs/adr/` only when a hard-to-reverse choice needs a durable record.

## Update gate

- Commands, installation behavior, or repository constraints changed: update this file.
- Public behavior changed: update both README files in the same change.
- A hard-to-reverse design decision changed: add or update an ADR.
- One-off validation output and current task status do not belong in durable docs.
