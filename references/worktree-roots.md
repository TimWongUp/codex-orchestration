# Independent Worktree Roots

Read this file only when an Integration Root is considering parallel writable work in official
Codex-managed Git worktrees.

## Identity

A Worktree Root is an independent Codex task and session running in its own checkout. It is a peer
root task, not a derived writable agent. It loads `codex-orchestration` normally and may use the
same `explorer`, reviewer, worker, and specialist roles as any root task.

`Integration Root` and `Worktree Root` are batch roles, not different agent types. Any root may act
as an Integration Root for a separately user-authorized batch after passing admission. While a root
is assigned one lane in the current batch, that scope does not let it create or coordinate peer
lanes for the same batch.

The Integration Root coordinates peer tasks through the current task/thread tools. Use a worktree
task environment rather than a derived-agent spawn. Derived agents created inside any root task
retain their normal role boundaries and do not become roots.

## Admission

Create Worktree Roots only when every condition holds:

1. The user explicitly requested official Codex worktrees in the current task.
2. The project is a Git repository and every lane starts from one accepted committed base.
3. Two or three writable lanes have independently acceptable outcomes and distinct intended write
   ownership.
4. Shared interfaces, migrations, generated artifacts, manifests, and lockfiles have one declared
   owner or remain reserved for integration.
5. The Integration Root can inspect every complete lane diff and run the combined validation.
6. Tests and external resources can run without the lanes mutating one shared environment.
7. The host exposes enough task, checkout, branch, and base identity to prove that every lane uses a
   distinct official worktree and that none shares the Integration Root's checkout. Otherwise do
   not start parallel writers.
8. The Integration Root has no active local writer lease before the first lane dispatch.

Use serialized stages inside one root task when any condition fails.

## Concurrency and authority

- One Integration Root coordinates at most three nonterminal Worktree Roots. Immediately before
  each dispatch, refresh the batch snapshot and serially reserve one lane slot; `pending`, `running`,
  and `handoff_ready` lanes consume slots until they become terminal. At the limit, wait instead of
  dispatching.
- Each root session may keep at most eight spawned-agent threads open concurrently, excluding its
  primary agent. Configure and confirm a host-enforced limit of eight or fewer; a lower host limit
  wins. Before each derived-agent spawn, refresh the visible agent tree when the host exposes it and
  never intentionally exceed the lower visible limit. If the root cannot confirm the host cap, it
  fails closed and does not spawn; a missing tree/count or rejection is never bypassed.
- The per-session limit is not a machine-wide aggregate. Worktree Roots are separate tasks and do
  not consume the Integration Root's spawned-agent slots.
- Each Worktree Root owns decomposition, model selection, subagent use, one local writer lease,
  lane-local Git operations, local acceptance, and validation inside its assigned lane. Like any
  normal root, it may use short-lived stage or prototype branches, but it returns one candidate lane
  branch for handoff acceptance.
- The Integration Root owns the common base, lane contracts, batch lifecycle, handoff and batch
  acceptance across lanes, merge order, integration fixes, and publishing. It owns the final
  PR Review when it creates, updates, or is asked to review the integration PR; the final merge
  check belongs to the root authorized to merge into the primary branch.
- While any lane is nonterminal, the Integration Root remains repository-read-only and does not
  modify its integration checkout. It neither creates nor retains a local writable-worker lease;
  neither its main agent nor any local worker writes the repository. It may activate one local
  writer for serial merge and integration fixes only after the complete batch is accepted. This
  keeps the batch at no more than three concurrent repository writers.
- Within its current lane assignment, a Worktree Root does not manage peer roots, merge another
  lane, or write the integration branch. This is batch scope, not a special subagent restriction.

## Dispatch

Use the current Codex task/thread creation schema and select its official worktree environment.
The prompt is user-visible, so write it as a compact standalone brief in the user-requested or
configured language. Natural prose is sufficient; optional headings such as task, context,
handoff, and references may be used when they improve readability. Include only the lane outcome,
context the root cannot cheaply recover, intended write ownership, accepted base, shared contracts,
useful references, validation expectations, and handoff evidence that materially affect the work.
Do not require field labels or create a temporary handoff document.

The Worktree Root recovers ordinary repository and environment context itself. Make clear that the
lane is an intermediate stage whose acceptance and combined validation belong to the Integration
Root; pre-merge Review belongs to whichever root later owns the primary-branch merge. Its natural
handoff still gives the Integration Root enough evidence to verify task/session
and worktree identity, branch and commit, complete diff, changed files, validation, and unresolved
integration risks.

Create peer tasks one at a time after reserving their slots. Record the task/session identifier and
the host-exposed worktree checkout, branch, and base identity. Before admitting a lane, confirm that
its checkout and branch are distinct from every peer and the Integration Root, and that its base is
the agreed commit. A duplicate or unverifiable identity fails the lane closed.

Create every lane from the same accepted base commit and give it a distinct handoff branch. Keep
shared uncommitted state out of the common base.

## Lane handoff

Before returning, a Worktree Root:

1. Inspects the actual lane diff and confirms that it matches the assigned outcome.
2. Runs the relevant tests, lint, type checks, builds, or smoke tests.
3. Leaves the candidate handoff work on a distinct branch with an unambiguous head commit.
4. Returns its task/session and worktree identity, branch, commit, changed files, validation
   evidence, and remaining integration risks.

A separate independent review is not required for every lane. The Worktree Root may use reviewers
normally and adds intermediate review when risk would otherwise compound.

## Lane and batch states

A lane is `pending`, `running`, `handoff_ready`, `accepted`, `failed`, or `canceled`. The Worktree
Root moves its lane from `pending` to `running`, then to `handoff_ready`, `failed`, or `canceled`.
`handoff_ready` remains nonterminal and consumes its slot. The Integration Root alone moves a
handoff from `handoff_ready` to `accepted` or `failed` after checking the lane root's local
acceptance and evidence against the lane contract. Only `accepted`, `failed`, and `canceled` are
terminal and release a lane slot; task completion alone is not acceptance. For a prototype lane,
handoff acceptance additionally requires the current user's explicit confirmation of the direction;
a completed prototype task is never merged automatically.

The original batch succeeds only when every declared lane is accepted, merged into the integration
branch, and included in combined validation, with the applicable PR Review or final merge check
in the integration barrier completed. A failed or canceled lane blocks
successful delivery of that batch.
Excluding a declared lane requires the user's explicit rescoping; treat that as a new accepted
outcome rather than silently completing a partial batch.

## Integration barrier

The Integration Root waits for the complete batch: every Worktree Root has reached a terminal lane
state and every completed handoff has been accepted or failed explicitly. If any lane failed or was
canceled, report the blocked batch and do not represent partial work as the requested completion.
For a successful batch, it then:

1. Reconfirms every task/session, checkout, branch, and base identity and inspects each complete diff.
2. Confirms each accepted branch still descends from the agreed base.
3. Serially merges accepted branches into a dedicated integration branch, never directly into the
   main branch.
4. Resolves or returns merge conflicts and reruns affected lane validation after each correction.
5. Runs the combined validation after all accepted branches are present.
6. When handling an integration PR or about to merge the integration branch into the primary branch,
   load `codex-review-gate` and complete its R0-R3 review against the latest combined candidate diff,
   reusing applicable earlier coverage. Otherwise hand off the validated branch without the gate.

Lane review covers only its assigned risks; check combined behavior and remaining integration risks.

## Stop convergence

When the user stops a batch, freeze new peer dispatch, mark the batch stopped, and send the current
task/thread stop or stop-request operation to every active `pending` or `running` Worktree Root.
The Integration Root moves every unlaunched `pending` reservation and every `handoff_ready` lane
directly to `canceled` without accepting or merging it. Wait for fresh peer-task snapshots until
every active peer task and every lane is terminal. If the host cannot force-stop a peer, state that
limitation and keep waiting for acknowledgment or terminal state. A stopped batch is not merged,
reviewed, or delivered as successful work.
