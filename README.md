[English](README.md) | [简体中文](README.zh-CN.md)

# Codex Orchestration

A cross-platform orchestration kit for Codex custom subagents: one main orchestrator, one active writer, explicit task packages, configurable model routing, and risk-based review.

It exists to make multi-agent coding predictable without turning every task into a committee. Simple work stays with the main agent; delegation is reserved for work with a clear payoff.

## Who it is for

This release targets Codex on macOS and native Windows for reusable exploration, research, implementation, prototype, debugging, and focused-review agents. A release candidate is supported only after both platform CI jobs pass.

Installation is performed by the user's Agent from a reviewed repository contract. The contract detects the active Codex paths and applies the platform-appropriate file and Hook configuration without requiring a platform-specific installer.

## Ask an Agent to install it

Requirements: macOS or native Windows, Codex with custom subagents enabled, and Python 3.9 or newer for validation.

Open this repository in Codex and ask:

```text
Install this repository for my local Codex environment. Read INSTALL.md completely, show me the full plan, and preserve unrelated or unapproved configuration.
```

The Agent validates the checkout, detects the current platform and Codex paths, classifies every destination, and shows all proposed writes before applying them. Required Skills and Agent profiles are copied for portability. Hooks and model routing are separate, optional decisions. Existing unrelated configuration and unapproved drift are preserved.

The complete and authoritative procedure is [INSTALL.md](INSTALL.md). You can audit it before asking an Agent to perform the installation.

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
- An Agent installation contract for macOS and native Windows that preserves unrelated Codex configuration.

The write lease is an orchestration contract, not an operating-system ACL. The main agent remains responsible for Git, validation, review selection, and final delivery.

## Continue reading

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Hooks and long-lived prompts](docs/hooks-and-prompts.md)
- [Agent installation contract](INSTALL.md)
- [Contributing](CONTRIBUTING.md)

The bundled method Skills were originally authored by Matt Pocock and are distributed under the MIT License. See [third-party notices](THIRD_PARTY_NOTICES.md).

## License

Codex Orchestration is [MIT licensed](LICENSE). Bundled third-party material retains its original notice and license.
