[English](README.md) | [简体中文](README.zh-CN.md)

# Codex Orchestration

A disciplined, cross-platform orchestration system for Codex custom subagents. It gives the main agent a concrete operating model for deciding when to delegate, what context every subagent receives, who may write, how results are accepted, and how much independent review a change needs.

Codex Orchestration is deliberately not a “spawn as many agents as possible” framework. Simple work stays with the main agent. Read-only agents can investigate in parallel by evidence area or independent viewpoint, while implementation follows a global single-writer lease. The main agent retains the goal, Git, validation, review selection, and final delivery, so delegation increases useful coverage without blurring ownership.

Repository: [github.com/TimWongUp/codex-orchestration](https://github.com/TimWongUp/codex-orchestration)

## Install

Requirements: macOS or native Windows, Codex with custom subagents enabled, and Python 3.9 or newer.

From a reviewed checkout, first print the complete plan:

```text
python3 scripts/install.py --codex-home ~/.codex --skills-root ~/.agents/skills --language en --hooks
```

Review the dry run, then repeat the same command with `--apply`. Use the Skill root that your Codex runtime actually loads; `--skills-root` is deliberately required. Replace `python3` with `py -3` on native Windows when needed.

Setup copies the required Skills and Agent profiles, injects one marker-delimited orchestration block into the active global `AGENTS.md` or `AGENTS.override.md`, and optionally merges the writer-lease Hook with `--hooks`. It preserves surrounding global instructions, unrelated Hook groups, local model routing, and other user files. Linked, ambiguous, or corrupt targets stop the entire plan; a caught apply or verification failure rolls completed writes back. After a Hook install, review and trust its current definition with `/hooks`.

Use `--no-global-rules` to leave global instructions unchanged, or omit `--hooks` to leave the Hook unchanged. On first install, `--language` accepts `en` or `zh-CN`; later runs preserve an existing valid preference when the option is omitted.

The authoritative procedure is [INSTALL.md](INSTALL.md), including conflict handling and runtime verification.

The repository is the only source of truth for its portable Skill, Agent, and writer-lease Hook `subagent_scope.py`. Installed files are replaceable runtime artifacts; model routes, executable paths, and Hook registrations stay local. Shared context, memory-routing, and closeout Hooks remain owned by their runtime repository.

## What makes it different

- **Delegation has a threshold.** Subagents are used only when parallel evidence, specialization, or a bounded worker can materially improve the result.
- **Handoffs preserve useful compression.** The main agent reads project architecture, design, ADR, and handoff documents that set cross-cutting constraints; delegated work returns traceable evidence, and negative claims state the searched boundary so verification does not repeat the whole search.
- **Task language is local.** Setup can persist English or Simplified Chinese prose while canonical package fields and control literals stay stable.
- **Parallel reading, serialized writing.** Explorers, researchers, designers, and reviewers may run concurrently; only the main agent or one leased worker writes at a time.
- **Waiting follows dependency.** The main agent waits before decisions, writes, or final answers that pending results could change; only independent, non-overlapping work continues.
- **V2 policy stays above the tools.** Model-visible collaboration schemas own call mechanics; the Skill adds fresh ordinary delegation, dependency-aware waiting, stale-result invalidation, explicit-stop convergence, and bounded worker rounds.
- **Collaboration has named modes.** `coverage` divides evidence, `panel` compares independent
  model judgments on one question, and `hybrid` runs that same-question panel alongside separate
  specialist workstreams. `single` remains the ordinary one-agent path, not a multi-agent
  evaluation mode.
- **Review scales with risk.** The R0–R3 gate ranges from main-agent validation to focused reviewers, remediation, and adversarial verification.
- **Models stay local and replaceable.** Agent profiles are model-neutral; optional role routes,
  task-specific overrides, parent-aware panel rosters, and host-enforced service-tier requirements
  live outside the repository. Only `panel` and the panel portion of `hybrid` inspect the latest
  host model binding; ordinary delegation follows its local role route directly.
- **Safety boundaries are stated honestly.** The optional Hook reinforces a writable-worker lease check, but acceptance still depends on the main agent checking the real diff and validation evidence.

## Who it is for

This release targets Codex on macOS and native Windows for reusable exploration, research, implementation, prototype, debugging, and focused-review agents. A release candidate is supported only after both platform CI jobs pass.

Installation uses one deterministic, dry-run-first Python implementation on both platforms. An Agent may operate it after reading `INSTALL.md`, but it does not reconstruct the filesystem and Hook merge logic itself.

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
- One optional Hook that reinforces the writable-worker lease. Tool schemas own call mechanics; the Skill owns orchestration policy and Agent profiles own derived-agent scope.
- One small, managed global `AGENTS.md` block that reliably routes subagent work through the Skill without replacing personal instructions.
- A local, optional model-routing file. No model IDs are pinned in the repository.
- A deterministic installation contract for macOS and native Windows with planning, ownership checks, rollback, and runtime verification.

The write lease is an orchestration contract, not an operating-system ACL. The main agent remains responsible for Git, validation, review selection, and final delivery.

## Continue reading

- [Architecture](docs/architecture.md)
- [Configuration](docs/configuration.md)
- [Hooks and long-lived prompts](docs/hooks-and-prompts.md)
- [Deterministic installation contract](INSTALL.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

The bundled method Skills were originally authored by Matt Pocock and are distributed under the MIT License. See [third-party notices](THIRD_PARTY_NOTICES.md).

## License

Codex Orchestration is [MIT licensed](LICENSE). Bundled third-party material retains its original notice and license.
