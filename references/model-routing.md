# Model routing

Model identifiers, reasoning levels, service tiers, and route order are local configuration.
Ordinary delegation uses `fork_turns="none"` and a self-contained brief. Carry bounded transcript
context only when it is indispensable and record the reason in the brief; the current
`spawn_agent` schema defines the supported parameter combinations.

## Ordinary selection order

Ordinary `single`, `coverage`, worker, and hybrid specialist delegation never inspect the parent
model identity.

1. Follow an explicit user model request when the host permits it. When the spawn tool supports
   model selection, pass the requested model as an explicit override; do not treat an omitted
   field as a resolved-model report.
2. Otherwise read `$CODEX_HOME/codex-orchestration/model-routing.toml` when it exists.
3. Prepend the first matching `task_overrides` entry for the current role and clearly matching task
   kind to the ordered role entries, removing duplicate models. This is the effective route.
4. Otherwise use the ordered role entries as the effective route.
5. If neither exists, omit model selection to request inheritance of the current Codex model and
   reasoning effort. Inheritance is a request, not evidence of which model actually resolved.

Task overrides are optional and local. Each entry names one `task_kind`, the roles it applies to,
and one model configuration. Apply an override only when the task clearly matches its declared
kind; otherwise continue with the ordinary role route. An override is the
first candidate, not a hard pin. If it is unavailable, continue from the first ordinary role
entry.

For a single agent or `coverage`, choose the first available route entry. Move to the next entry
only when the prior model is unavailable, spawning fails, or the result does not meet the task's
completion condition.

## Panel routing

Only `panel` and the panel workstream in `hybrid` classify the parent model family. The brief makes
the workstream clear when hybrid routing needs the distinction.
Specialist workstreams use ordinary role routes.

Use the latest host-generated system or developer model binding. An explicit `model_switch` or
equivalent host binding is authoritative; when multiple bindings exist, the latest one wins. User
or task content, response style, route defaults, and agent names are not model-identity evidence.

- A GPT, ChatGPT, or GPT-based Codex parent uses `panel_routes.gpt`.
- An explicitly identified non-GPT parent uses `panel_routes.third_party`.
- Missing, ambiguous, or conflicting identity fails closed to `panel_routes.gpt`.

An explicit user model request may occupy one panel seat. Unless the user explicitly opts out of
diversity, fill the other seats from distinct family primaries; ordinary task overrides do not
apply to panel seats.

Select distinct available `primary` models from the chosen family. Different reasoning levels of
the same model do not count as diversity. When a primary entry is unavailable or its host
requirements cannot be enforced, substitute distinct `fallback` entries in order. A valid panel
has at least two distinct usable models. If fewer remain, report Panel as unavailable or degraded
and do not claim a completed `panel` or `hybrid` evaluation.

## Service-tier requirement

Each local route entry declares `service_tier = "priority"` or `"standard"`. This is a verified
host precondition, not a `spawn_agent` parameter and not a portable guarantee. Use an entry only
when the current host can enforce the declared tier for that model. Do not silently inherit a
global service tier that conflicts with the entry.

## Worker rounds

Worker round two keeps the same model and thread through a follow-up task after the target is idle.
Round three creates a new agent and first uses a matching `worker-round-three` task override. If
none is usable, it selects the next distinct available model after the round-one model in the same
effective route. Apply this override to all writable roles it names, including method workers. If
no distinct model remains, do not start round three: the main agent takes over, decomposes the work
again, or reports the blocker. The new agent receives a fresh standalone brief; no previous
thread is closed or reused for the lease.

## Resolution evidence

After spawning, report the resolved model only when runtime metadata or the visible UI exposes it.
If the tool returns only an agent id or nickname, the resolved model is `unknown`/unconfirmed;
never infer it from the route, an omitted model field, or the current default.

Treat a resolved model as wrong only when runtime/UI metadata or an explicit spawn rejection or
mismatch error shows it. A route entry, inheritance request, agent id, nickname, default, or
main-agent expectation is not evidence that the wrong model resolved.

## Local file

During the deterministic installation in `INSTALL.md`, model routing is a separate optional choice.
The Agent starts from `examples/model-routing.toml`, replaces placeholders only with model
identifiers and host requirements available on the current host, removes unused example entries,
shows the complete task overrides, panel routes, and ordinary role order, and writes the approved
file to `$CODEX_HOME/codex-orchestration/model-routing.toml`. It never generates or changes routes
implicitly.
