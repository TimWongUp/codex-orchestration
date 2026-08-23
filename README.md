[English](README.md) | [简体中文](README.zh-CN.md)

# Codex Orchestration

A disciplined, cross-platform orchestration system for Codex custom subagents. It gives the main agent a concrete operating model for deciding when to delegate, what context every subagent receives, who may write, how results are accepted, and how much independent review a change needs.

Codex Orchestration is deliberately not a “spawn as many agents as possible” framework. Simple work stays with the main agent. Read-only agents can investigate in parallel by evidence area or independent viewpoint, while implementation follows a global single-writer lease. The main agent retains the goal, Git, validation, review selection, and final delivery, so delegation increases useful coverage without blurring ownership.

Repository: [github.com/TimWongUp/codex-orchestration](https://github.com/TimWongUp/codex-orchestration)

## Install with Codex

Requirements: macOS or native Windows, Codex with custom subagents enabled, and Python 3.9 or newer for validation.

Open the repository in Codex and paste this prompt:

```text
Install Codex Orchestration from https://github.com/TimWongUp/codex-orchestration for my local Codex environment. Read INSTALL.md completely, show me the full plan before making changes, and preserve unrelated or unapproved configuration.
```

The Agent validates the checkout, discovers the Codex home and active Skill root instead of guessing paths, classifies every managed destination, and shows all proposed writes before applying them. Required Skills and Agent profiles are copied for portability. Task-package language is chosen during initial setup; Hooks and model routing remain separate, optional decisions. Existing unrelated configuration and unapproved drift are preserved, while externally owned runtime entries are reported separately and left untouched.

The authoritative procedure is [INSTALL.md](INSTALL.md), including conflict handling and runtime verification.

The repository is the only source of truth for its portable Skill, Agent, and two orchestration Hooks: `orchestration_route.py` and `subagent_scope.py`. Installed files are replaceable runtime artifacts; model routes, executable paths, and Hook registrations stay local. Shared context, memory-routing, and closeout Hooks remain owned by their runtime repository.

## What makes it different

- **Delegation has a threshold.** Subagents are used only when parallel evidence, specialization, or a bounded worker can materially improve the result.
- **Handoffs preserve useful compression.** The main agent reads project architecture, design, ADR, and handoff documents that set cross-cutting constraints; delegated work returns traceable evidence, and negative claims state the searched boundary so verification does not repeat the whole search.
- **Task language is local.** Setup can persist English or Simplified Chinese prose while canonical package fields and control literals stay stable.
- **Parallel reading, serialized writing.** Explorers, researchers, designers, and reviewers may run concurrently; only the main agent or one leased worker writes at a time.
- **Waiting follows dependency.** The main agent waits before decisions, writes, or final answers that pending results could change; only independent, non-overlapping work continues.
- **V2 tools have explicit responsibilities.** Ordinary `spawn_agent` calls use `fork_turns="none"` for fresh context; `send_message` queues supplemental context without starting a turn; `followup_task` delivers later or corrective work to a running target and starts a new turn for an idle target; `wait_agent` waits for the caller mailbox; `interrupt_agent` preserves context while interrupting an active turn; and `list_agents` plus final notifications reconcile status.
- **Collaboration has named modes.** `coverage` divides evidence, `panel` compares independent model judgments, and `hybrid` combines both without treating majority vote as truth.
- **Review scales with risk.** The R0–R3 gate ranges from main-agent validation to focused reviewers, remediation, and adversarial verification.
- **Models stay local and replaceable.** Agent profiles are model-neutral; optional role routes and task-specific overrides live outside the repository and can match the models available on each machine.
- **Safety boundaries are stated honestly.** Hooks reinforce routing and identity, but acceptance still depends on the main agent checking the real diff and validation evidence.

## Who it is for

This release targets Codex on macOS and native Windows for reusable exploration, research, implementation, prototype, debugging, and focused-review agents. A release candidate is supported only after both platform CI jobs pass.

Installation is performed by the user's Agent from a reviewed repository contract. The contract detects the active Codex paths and applies the platform-appropriate file and Hook configuration without requiring a platform-specific installer.

## First successful use

Start a new Codex task after installation, then ask:

```text
Use the explorer subagent to map the execution path for this feature, then summarize the evidence before proposing changes.
```

For a broader feature discussion, ask Codex to use `web-researcher` for public implementation patterns or `reference-researcher` for official documentation.

## What is included

- A main-agent orchestration Skill that owns delegation, task packaging, write leases, acceptance, and the R0–R3 review gate.
- The complete `diagnosing-bugs` and `prototype` method Skills used by their workers.
- Read-only explorer, official-reference research, web research, frontend-design, expert, and focused-review agents.
- Writable implementation, debugging, and prototype workers governed by a single-writer lease.
- Optional Hooks that reinforce main-agent routing and derived-agent scope. Lifecycle semantics stay in the Skill and the model-visible v2 tools.
- A local, optional model-routing file. No model IDs are pinned in the repository.
- An Agent installation contract for macOS and native Windows that preserves unrelated Codex configuration.

The write lease is an orchestration contract, not an operating-system ACL. The main agent remains responsible for Git, validation, review selection, and final delivery.

## Continue reading

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Hooks and long-lived prompts](docs/hooks-and-prompts.md)
- [Agent installation contract](INSTALL.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

The bundled method Skills were originally authored by Matt Pocock and are distributed under the MIT License. See [third-party notices](THIRD_PARTY_NOTICES.md).

## License

Codex Orchestration is [MIT licensed](LICENSE). Bundled third-party material retains its original notice and license.
