[English](README.md) | [简体中文](README.zh-CN.md)

# Codex Orchestration

A disciplined, cross-platform orchestration system for Codex custom subagents and independent Worktree Roots. It gives each root task a concrete operating model for deciding when to delegate, what context every subagent receives, who may write, how parallel worktree lanes are integrated, how results are accepted, and how much independent review a change needs.

Codex Orchestration is deliberately not a “spawn as many agents as possible” framework. Simple work stays with the main agent. Read-only agents can investigate in parallel by evidence area or independent viewpoint, while each root task follows a local single-writer lease. When the user explicitly requests official Codex worktrees and the work can be partitioned safely, one Integration Root may coordinate up to three independent Worktree Roots for isolated parallel implementation. Each Worktree Root behaves like a normal root task inside its assigned lane; neither the Integration Root nor its local workers write the repository until every declared handoff is accepted, after which it serially merges the batch and owns combined validation. It owns the final Review only when the batch is about to merge into the primary branch.

Repository: [github.com/TimWongUp/codex-orchestration](https://github.com/TimWongUp/codex-orchestration)

## Install

Requirements: macOS or native Windows, Codex with custom subagents enabled, and Python 3.9 or newer.

You do not need to download the repository manually. Paste this prompt into Codex:

```text
Install the latest Codex Orchestration from https://github.com/TimWongUp/codex-orchestration.
Obtain and keep a suitable local checkout, read INSTALL.md completely, and use only
scripts/install.py for installation. Run the non-interactive dry run for this platform first
(use language en on a first install), show me the complete plan, and ask for my approval before
running it again with --apply. After applying, verify the runtime and remind me to start a new
Codex task. Preserve any existing checkout with uncommitted changes and all unmanaged local files.
```

Codex still obtains a checkout because the installer consumes the repository's Skills, Agent
profiles, managed rules, and validation logic together. That checkout remains the source of truth
for deterministic updates and uninstall; the prompt simply removes the manual download and command
selection steps.

For manual installation, download or clone the repository, then run this from the checkout:

```text
python3 scripts/install.py
```

On a first install, setup suggests `en` or `zh-CN` from the system locale, prints the complete plan, and asks once before applying it. Later updates reuse the saved language. The default targets are `~/.codex` and the documented Codex user Skill directory `~/.agents/skills`. Replace `python3` with `py -3` on native Windows.

Non-interactive runs never prompt and are dry runs by default. Pass `--language en` or `--language zh-CN` on the first run, review the plan, then add `--apply`. Non-standard runtimes can still override `--codex-home` and `--skills-root`.

Setup copies the required Skills and Agent profiles and injects one marker-delimited orchestration and code-review block into the active global `AGENTS.md` or `AGENTS.override.md`. It writes only that current projection and preserves unmanaged Agent profiles, Hook registrations and files, surrounding global instructions, local model routing, and other user files. Linked, ambiguous, or corrupt managed targets stop the entire plan; a caught apply or verification failure rolls completed writes back. Removing assets from earlier versions is a separate user-directed maintenance action.

Use `--no-global-rules` to leave global instructions unchanged; an existing owned block must already be current, so stale Review routing blocks the plan.

To uninstall the global runtime, preview the complete removal plan first, then apply the same plan:

```text
python3 scripts/install.py --uninstall
python3 scripts/install.py --uninstall --apply
```

Interactive terminals ask for confirmation instead of requiring `--apply`. Uninstall removes only
current managed files that still match this checkout and the marker-owned global rules block. It
preserves model routing, Hooks, personal instructions, unmanaged Agents and Skills, project rules,
and extra files. Any changed managed file or malformed marker blocks the complete operation; there
is no force-delete mode.

The authoritative procedure is [INSTALL.md](INSTALL.md), including conflict handling and runtime verification.

The repository is the only source of truth for its portable Skills, Agents, installer, and managed global-rules block. Installed files are replaceable runtime artifacts; model routes and unrelated Hook registrations stay local. Shared context, memory-routing, and closeout Hooks remain owned by their runtime repository.

## What makes it different

- **Delegation has a threshold.** Subagents are used only when parallel evidence, specialization, or a bounded worker can materially improve the result; the separate pre-merge gate authorizes only its selected read-only Reviewers.
- **Handoffs preserve useful compression.** Delegation uses compact natural-language briefs with optional task, context, handoff, and reference sections instead of mandatory fields or temporary documents. Agents recover ordinary repository context and return traceable evidence.
- **Task language is local.** Setup can persist English or Simplified Chinese delegation prose while role names, paths, and external protocol literals stay stable.
- **Parallel reading, locally serialized writing.** Explorers, researchers, and reviewers may run concurrently; inside each root task, only the main agent or one leased worker writes at a time.
- **Parallel worktrees use peer roots.** With explicit user approval and an admission gate, an
  Integration Root may coordinate up to three independent Worktree Roots. They use normal
  subagents in isolated checkouts.
- **Orchestration stays with roots.** Derived Agents do not call collaboration tools or orchestrate
  descendants, siblings, or other Agents; panel membership never changes that boundary.
- **Concurrency is bounded per session.** Each root session uses at most eight spawned-agent
  threads, excluding its primary agent, while lower host limits still apply.
- **Waiting follows dependency.** The main agent waits before decisions, writes, or final answers that pending results could change; only independent, non-overlapping work continues.
- **V2 policy stays above the tools.** Model-visible collaboration schemas own call mechanics; the Skill adds fresh ordinary delegation, dependency-aware waiting, stale-result invalidation, explicit-stop convergence, and bounded worker rounds.
- **Collaboration has named modes.** `coverage` divides evidence, `panel` compares independent
  model judgments on one question, and `hybrid` runs that same-question panel alongside separate
  specialist workstreams. `single` remains the ordinary one-agent path, not a multi-agent
  evaluation mode.
- **Review is a primary-branch integration gate.** `codex-review-gate` runs only when the current root is about to merge a pull request, branch, or accepted Worktree integration branch into a Git repository's primary branch. Ordinary task completion, unmerged handoff, pull-request creation or update without an imminent merge, and repositories without Git history stay with normal validation and do not enter R0-R3. When the gate applies, it classifies the latest candidate diff: R0 covers fully verified changes with no material failure hypothesis; R1 uses one matching Reviewer for one localized, validated, recoverable hypothesis; R2 covers multiple independent risks, broad or hard-to-recover contracts, sensitive boundaries, or material uncertainty; R3 adds focused remediation and adversarial verification for changed trust boundaries or high-impact failure. Additional seats follow only additional material hypotheses, never a quota.
- **Review findings preserve evidence classes.** Reviewers stay within the assigned change boundary and risk. When a finding depends on a task or spec requirement or a repository standard, they cite that source and identify the evidence class without starting a generic Standards/Spec pass. Judgment calls remain labelled, and checks conclusively covered by current passing tooling are omitted unless that coverage is itself in question. After an accepted finding is fixed, the original Reviewer verifies that finding through a same-thread targeted follow-up; this does not restart a full Review loop merely to obtain a clean report.
- **Tests must earn their maintenance cost.** Writable Agents add tests only when they supply unique confidence at a correct observable seam, preferring an existing test at the lowest-cost appropriate layer. The test-reliability Reviewer also identifies coverage-chasing, redundant, implementation-bound, prose-bound, flaky, or retired-compatibility tests, but recommends removal only when equivalent behavior and failure protection remain.
- **Models stay local and replaceable.** Agent profiles are model-neutral; optional role routes,
  task-specific overrides, parent-aware panel rosters, and host-enforced service-tier requirements
  live outside the repository. Only `panel` and the panel portion of `hybrid` inspect the latest
  host model binding; ordinary delegation follows its local role route directly.
- **Safety boundaries are stated honestly.** A worker role is an orchestration lease, not an operating-system control; acceptance depends on the main agent checking the complete diff and validation evidence.

## Who it is for

This release targets Codex on macOS and native Windows for reusable exploration, research, implementation, prototype, debugging, and focused-review agents. A release candidate is supported only after both platform CI jobs pass.

Installation uses one deterministic, dry-run-first Python implementation on both platforms. An Agent may operate it after reading `INSTALL.md`, but it does not reconstruct the filesystem projection itself.

## First successful use

Start a new Codex task after installation, then ask:

```text
Use the explorer subagent to map the execution path for this feature, then summarize the evidence before proposing changes.
```

For a broader feature discussion, ask Codex to use `web-researcher` for public implementation patterns or `reference-researcher` for official documentation.

## What is included

- A root-task orchestration Skill that owns delegation briefs, local write leases, Worktree Root coordination, acceptance, and reusable Agent execution.
- An independent `codex-review-gate` Skill that defines the pre-merge R0–R3 route and authorizes only its selected read-only Reviewers; the merge-owning root executes classification, remediation, and integration.
- The complete `diagnosing-bugs` and `prototype` method Skills used by their workers.
- Read-only explorer, official-reference research, web research, expert, and focused-review agents.
- Writable implementation, debugging, and prototype workers governed by a per-root single-writer lease.
- No project Hook; tool schemas own call mechanics, the Skill owns orchestration policy, and Agent profiles own derived-agent scope.
- One small, managed global `AGENTS.md` block that independently routes subagent execution and code-change Review without replacing personal instructions.
- A local, optional model-routing file. No model IDs are pinned in the repository.
- A deterministic installation and uninstall contract for macOS and native Windows with planning, ownership checks, rollback, and runtime verification.

The write lease is an orchestration contract, not an operating-system ACL. Each root task remains responsible for its local Git and validation; the merge-owning root remains responsible for pre-merge Review, and the Integration Root remains responsible for cross-worktree integration.

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
