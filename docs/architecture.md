# Architecture

Codex Orchestration separates six concerns:

1. `SKILL.md` defines root-task routing and always-on orchestration invariants; branch-specific
   collaboration, manager-only, worker, lifecycle, model, and Worktree contracts live under
   `references/`.
2. `skills/codex-review-gate/SKILL.md` defines and authorizes the primary-branch pre-merge risk
   route; the merge-owning root executes classification, Reviewer selection, remediation, and
   adversarial verification.
3. `agents/*.toml` defines narrow custom-agent behavior and sandbox defaults.
4. Local preference files select delegation language and models without placing user choices in
   the repository.
5. `examples/global-agents-block.md` is the minimal global pointer injected into the active Codex
   instruction file.
6. `INSTALL.md` defines the reviewed installation contract, implemented deterministically by
   `scripts/install.py`.

The repository is the single source of truth for portable runtime behavior. Installed Skill,
Agent, and global-rule files are replaceable deployment artifacts, while delegation language,
model IDs, unrelated Hook registrations, and other host choices remain local configuration.
This prevents an installed runtime from becoming a second implementation that drifts
independently.

The installed runtime is a projection, not a copy of the repository root: the main orchestration
Skill receives only root `SKILL.md` and `references/`; `codex-review-gate` and each bundled method
Skill have their own Skill destinations; Agent profiles go to Codex home. Deployment registries may
record this
repository as authority, but suite installation remains governed by `INSTALL.md` so a generic
single-Skill linker cannot flatten these components or expose the whole checkout as one Skill.

The installer always plans before writing and treats the selected Codex home and Skill root as
explicit trust boundaries. Standard interactive installation uses documented user defaults and one
confirmation; non-standard and non-interactive installations retain explicit target and apply
controls. It refuses linked or ambiguous managed targets, owns only named current runtime files,
preserves all unmanaged Agent and Hook assets, and rolls back completed writes when verification
fails. Legacy cleanup is a separate user-directed maintenance action rather than a permanent branch
of installation.
Codex plugin packaging is not the suite authority because plugins do not replace the separate
custom-Agent projection.

The `skills/diagnosing-bugs` and `skills/prototype` directories contain the complete method Skills
loaded by their corresponding writable workers. The read-only `simplicity-reviewer` embeds its
focused review method directly in its Agent profile. Agent profiles retain authority and
orchestration boundaries; bundled method Skills provide the detailed writable task workflows.

Every Codex task is a root for its own agent tree. Derived agents remain non-orchestrators, while a
Worktree Root is an independent task and session with the same local orchestration authority as any
other root task. Integration Root and Worktree Root are batch roles: only the former manages peer
lanes and cross-lane state for that batch. Inside each root task, read-only agents may run
concurrently and writable work uses one local single-writer lease: either the main agent writes, or
one worker writes toward one bounded outcome.

Writable Agent profiles keep test work proportional to the assigned change's material risks. They
add tests only when a correct observable seam supplies unique confidence, prefer existing tests at
the lowest-cost appropriate layer, recognize static tooling that already proves a property, and
consolidate or remove tests only when no unique protection is lost.

When the user explicitly requests official Codex worktrees and the admission gate in
`references/worktree-roots.md` passes, one Integration Root may coordinate at most three
nonterminal Worktree Roots. Each works in a verified distinct checkout, owns lane-local Git, returns
one candidate handoff branch, and may use the normal explorer, reviewer, specialist, and worker
roles. While any lane is nonterminal, the Integration Root remains repository-read-only. After the
complete batch is accepted, it owns the common base, serial merge order, integration branch,
combined validation, and integration-branch handoff. It owns `codex-review-gate` only when it also
owns the primary-branch merge. During the active batch neither its main agent nor a local worker may
write; no local writable-worker lease remains active. This keeps concurrent repository writers at
three or fewer without granting orchestration authority to a derived worker.

Each root session may keep at most eight spawned-agent threads open concurrently, excluding its
primary agent; a lower host limit wins. The host must enforce and expose a confirmable cap before a
root spawns derived agents. Worktree Roots are separate sessions, so this is not one machine-wide
aggregate budget. The separate nonterminal worktree-root limit remains three.

Read-only collaboration has three multi-agent evaluation modes. `coverage` assigns non-overlapping
evidence or risk areas. `panel` gives the same core question to distinct models. `hybrid` combines
one such panel with separate specialist workstreams when both independent model judgment and
non-overlapping risk coverage can change the decision. The ordinary `single` path creates one
agent and is not an evaluation mode. Only the panel path classifies the parent model; coverage and
hybrid's specialist workstreams use ordinary role routes.

## Manager-only branch

Manager-only mode is an explicit opt-in for one current root task, documented in
`references/manager-only.md`. It is adaptive strong delegation rather than a fixed pipeline:
the root agent decomposes the goal, dispatches and coordinates work, handles Git/PR and non-code
work, and retains final acceptance. Substantive code investigation goes to `explorer`, while code
implementation, tests, and validation go to a leased `worker` or method worker. Independent Review
still follows the current risk and the primary-branch boundary of `codex-review-gate`.

In this branch, final acceptance is the only root-agent code inspection: it reads the complete diff,
key excerpts, and validation output. A failed subagent or unaccepted handoff never permits a silent
root-agent takeover; before three unsuccessful Worker rounds, the root may re-decompose or replace
the agent, while after three rounds it may only re-decompose read-only or report a blocker. It never
starts a fourth code-writing round, and new code-writing work waits for a new user direction or
explicit mode exit. The mode is current-task-only and not persisted in preferences, model routing,
Hooks, CLI, or other configuration. The root agent may resume ordinary code work only after the
user explicitly consents to exit the mode.

## Pre-merge Review boundary

Ordinary delegation is optional execution optimization; mandatory Review is a primary-branch
integration gate. It applies when a Git-managed repository has committed source and target
histories and the current workflow is about to merge a pull request, branch, or accepted Worktree
integration branch into the primary branch. The merge-owning root must then pin the latest candidate
diff; if it cannot, the merge remains blocked until the required history and refs are available.
Ordinary task completion, an unmerged handoff, pull-request creation or update without an imminent
merge, and repositories without Git history do not trigger it. Main-agent validation still applies
to those tasks.

`codex-review-gate` defines the R0-R3 route independently of the orchestration Skill. An applicable
project, user, workflow, or global rule requiring the gate authorizes only the read-only Reviewers
selected by R1-R3 without a repeated current-turn request; a current explicit user prohibition still
wins. The merge-owning root executes classification, role selection, remediation, validation, and
integration. When Reviewers are selected, it calls
`codex-orchestration` for model routing, briefs, lifecycle, and waiting rather than duplicating
those mechanics.

Normal Reviewers remain within the assigned change boundary and risk. When a finding depends on a
task or spec requirement or a repository standard, it cites and identifies that evidence class;
this does not create a generic Standards/Spec pass. Sourced violations remain distinct from
judgment calls, and passing mechanical checks are not repeated unless their coverage is the risk.

The `test-reliability-reviewer` covers both protection and necessity. It checks whether tests add
confidence in current behavior or credible failures at a correct seam, whether a cheaper layer
already supplies that confidence, and whether removal preserves equivalent behavior and failure
protection. Test count and coverage percentage are evidence inputs, not optimization targets.

The gate evaluates the highest-risk property of the latest integration candidate diff: local,
self-contained work that the main agent completely verified and that leaves no material failure
hypothesis may be R0 even when it changes runtime behavior; localized, validated, recoverable
changes with one material failure hypothesis that independent judgment could change are R1,
including localized public-contract and managed-policy changes; multiple independent risks, broad
or hard-to-recover public contracts, sensitive boundaries, or material uncertainty are R2; changed trust boundaries or
high-impact failure are R3. Main-agent validation is required at every level but does not count as
independent Review. R3 ends with adversarial verification after focused Review and remediation.

Risk level and Reviewer count are separate decisions. The level expresses impact and
recoverability; R1-R3 always select at least one matching Reviewer, and additional seats correspond
only to additional material failure hypotheses for which independent judgment can change
integration.
Mechanical validation, an absent evidence axis, and a desired panel size do not create extra seats.
R1 defaults to `correctness-reviewer`; a matching specialist replaces that default when the sole
material hypothesis belongs to its domain, rather than adding another Reviewer for the same risk.
Reviewer findings remain hypotheses until the merge-owning root checks their cited evidence against
the pinned candidate diff. After an accepted finding is fixed, the original Reviewer verifies that
finding through a same-thread targeted follow-up; the gate does not restart a full Review solely to
obtain a clean report. A new substantive change after Review stales the candidate and requires the
merge-owning root to re-pin and reclassify it.

The merge-owning root retains finding decisions, remediation authority, validation authority, and
gate authority. In ordinary mode, the main agent may implement an accepted fix. In manager-only
mode, the leased worker implements the accepted fix and runs validation; the root inspects and
accepts the result before the original Reviewer performs the targeted follow-up.

## V2 lifecycle

The model-visible collaboration-tool schemas own call mechanics. The repository does not wrap the
tools or cache their API descriptions. Its portable policy starts ordinary delegation with
`fork_turns="none"` and a self-contained natural-language brief; bounded transcript context is an
explained exception.

The root Skill keeps the dependency barrier and authority boundaries inline. It progressively
discloses multi-agent read-only modes through `references/read-only-collaboration.md`, follow-up and
stop edge cases through `references/collaboration-lifecycle.md`, writable-worker details through
`references/worker-writing.md`, and Worktree-batch behavior through
`references/worktree-roots.md`.

The main agent waits before any decision, write, or final answer that pending work could change,
while continuing only independent work. The current tree and final notification are the
authoritative convergence signals. After a follow-up is accepted, earlier final notifications and
snapshots for that target are stale, so the main agent waits for a newer final and reconciles it
with a fresh snapshot. A third writable round creates a new agent with a fresh package and lease.

An Integration Root applies the same dependency barrier to peer Worktree Roots through the current
task/thread tools. It serially reserves at most three nonterminal lane slots, verifies distinct
official worktree identities, and waits for the complete accepted batch before serial integration.
Each Worktree Root performs local lane acceptance and validation; the Integration Root separately
owns handoff and batch acceptance. Optional intermediate consultation is added only when risk would
otherwise compound. A failed or canceled declared lane blocks successful delivery unless the user
explicitly rescopes the outcome. `codex-review-gate` runs once against the latest combined
candidate only when that integration branch is about to merge into the primary branch; an unmerged
branch handoff defers Review to the future merge-owning task.

An explicit stop freezes new delegation, snapshots the tree, interrupts every active descendant,
and waits for final notifications plus a fresh snapshot showing no running agents. A leased worker
retains its lease until that convergence point. A correction that must prevent further current-turn
work first interrupts the target and waits for the interruption to become visible, then uses
`followup_task` to deliver the corrected task.

For a Worktree batch, stop convergence separately freezes peer dispatch, sends the available
task/thread stop operation or request to every active root, moves submitted `handoff_ready` lanes to
`canceled`, cancels unlaunched `pending` reservations, and waits for fresh peer snapshots. The
Integration Root neither merges nor reports success while a peer or lane is still nonterminal.

No orchestration Hook is installed. Agent profiles remain the authority for derived-agent identity
and read-only scope, while the two policy Skills and current tool schemas carry main-agent policy. Worker
selection establishes the root task's single-writer lease; task messages use natural briefs rather
than fixed authorization labels, and the main agent accepts work only after inspecting the complete
diff and validation. Cross-host context injection, memory routing, and closeout behavior belong to
their shared runtime; Codex-native agent status UI remains host-owned.

Installation uses one standard-library Python implementation on macOS and native Windows. The
canonical global block is inserted into the first non-empty global `AGENTS.override.md` or
`AGENTS.md`; surrounding bytes remain user-owned, and corrupt or duplicated markers fail closed.
`scripts/validate.py` remains read-only and verifies both the public source contract and an
installed runtime supplied by path.

The transaction contract covers failures caught by the running installer, not abrupt termination
or hostile same-user path replacement. A fresh dry run is the recovery authority after a crash or
power loss; linked or changed targets fail closed instead of being followed.
