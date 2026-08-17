[English](README.md) | [简体中文](README.zh-CN.md)

# Codex Orchestration

A macOS-first orchestration kit for Codex custom subagents: one main orchestrator, one active writer, explicit task packages, configurable model routing, and risk-based review.

It exists to make multi-agent coding predictable without turning every task into a committee. Simple work stays with the main agent; delegation is reserved for work with a clear payoff.

## Who it is for

Use this project if you run Codex on macOS and want reusable custom agents for exploration, research, implementation, prototypes, debugging, and focused review.

The current release intentionally supports macOS only. Windows packaging and runtime behavior are not documented as supported yet.

## Install from a checkout

Requirements: macOS, Codex with custom subagents enabled, and Python 3.9 or newer.

```bash
python3 scripts/validate.py
python3 scripts/install.py
python3 scripts/install.py --apply --with-hooks
```

The first installer run is a dry run. Before writing anything, it checks all three Skill names and every managed Agent, Hook, and routing target. A valid existing same-named Skill is reused without modification; a conflict or unapproved drift stops the install without applying the plan. Existing unrelated agents and hooks are preserved. Reviewed managed-file drift requires an explicit `--replace`.

### Let an agent install it

Open a Codex task in this repository and use the complete [agent-assisted installation prompt](docs/agent-install.md). It makes the agent inspect the checkout, dry-run every change, request decisions for hooks and model routing, and verify the installed runtime.

## First successful use

Start a new Codex task after installation, then ask:

```text
Use the explorer subagent to map the execution path for this feature, then summarize the evidence before proposing changes.
```

For a broader feature discussion, ask Codex to use `web-researcher` for public implementation patterns or `reference-researcher` for official documentation.

## What is included

- A main-agent orchestration Skill with `coverage`, `panel`, and `hybrid` read-only collaboration modes.
- The complete `diagnosing-bugs` and `prototype` method Skills used by their workers.
- Read-only explorer, research, design, and review agents.
- Writable implementation, debugging, and prototype workers governed by a single-writer lease.
- Optional `UserPromptSubmit` and `SubagentStart` hooks.
- A local, optional model-routing file. No model IDs are pinned in the repository.
- A macOS installer that preserves unrelated Codex configuration.

The write lease is an orchestration contract, not an operating-system ACL. The main agent remains responsible for Git, validation, review selection, and final delivery.

## Continue reading

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Hooks and long-lived prompts](docs/hooks-and-prompts.md)
- [Agent-assisted installation](docs/agent-install.md)
- [Contributing](CONTRIBUTING.md)

The bundled method Skills were originally authored by Matt Pocock and are distributed under the MIT License. See [third-party notices](THIRD_PARTY_NOTICES.md).

## License

Codex Orchestration is [MIT licensed](LICENSE). Bundled third-party material retains its original notice and license.
