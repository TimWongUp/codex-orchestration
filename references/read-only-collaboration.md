# Read-only collaboration

Read this file before creating two or more read-only agents.

## Modes

Choose the mode by the evidence the decision needs:

- `coverage`: separate evidence ranges or risk hypotheses.
- `panel`: normally two or three distinct models answer the same task independently.
- `hybrid`: one same-question panel plus separate specialist workstreams.

Tell each agent which workstream it serves when that distinction affects its assignment. In
`hybrid`, distinguish the panel question from specialist coverage. These are semantic instructions,
not required labels, and missing labels never make an otherwise actionable assignment invalid.

Use `coverage` when independent evidence classes are necessary. Use `panel` when model-diverse
judgment on one question can change the decision. Use `hybrid` only when both needs are material.
One ordinary agent is the `single` path, not an evaluation mode.

## Panel independence

Give panel members the same question, necessary context, evidence boundary, and acceptance focus;
change only the model route. A derived panel member answers independently. It does not load or
execute `codex-orchestration`, synthesize the panel, call collaboration tools, or orchestrate any
other agent.

After every member returns, the main agent synthesizes consensus, material disagreement, and
evidence quality. Majority vote is not the decision rule.

## Assignment boundaries

Give each Reviewer a concrete failure hypothesis and evidence boundary when the role, task, or diff
does not already make them clear. Give each specialist one distinct specialty. Keep scopes
non-overlapping unless intentional redundancy is the reason for the panel.
