# Model routing

Model choices are local configuration, not repository policy.

## Selection order

1. Follow an explicit user model request. When the spawn tool supports model selection, pass the requested model as an explicit override; do not treat an omitted field as a resolved-model report.
2. Otherwise read `$CODEX_HOME/codex-orchestration/model-routing.toml` when it exists.
3. Prepend the first matching `task_overrides` entry for the current role and clearly matching task kind to the ordered role entries, removing duplicate models. This is the effective route.
4. Otherwise use the ordered role entries as the effective route.
5. If neither exists, omit model selection to request inheritance of the current Codex model, reasoning effort, and service tier. Inheritance is a request, not evidence of which model actually resolved.

After spawning, report the resolved model only when runtime metadata or the visible UI exposes it. If the tool returns only an agent id or nickname, the resolved model is `unknown`/unconfirmed; never infer it from the route, an omitted model field, or the current default.

A wrong-model correction requires runtime/UI resolved-model metadata or an explicit spawn rejection or mismatch error. A route entry, inheritance request, agent id, nickname, default, or main-agent expectation is not evidence that the wrong model resolved.

Task overrides are optional and local. Each entry names one `task_kind`, the roles it applies to, and one model configuration. Apply an override only when the task clearly matches its declared kind; otherwise continue with the ordinary role route. An override is the first candidate, not a hard pin. If it is unavailable, continue from the first ordinary role entry.

For a single agent or `coverage`, choose the first available route entry. Move to the next entry only when the prior model is unavailable, spawning fails, or the result does not meet the task's completion condition.

For `panel` and the panel portion of `hybrid`, deliberately select different available models from each agent's effective route. A matching override may be used by one panel member; later members continue to distinct ordinary-route models. Different reasoning levels of the same model do not count as model diversity.

Worker rounds one and two keep the same model and thread. Round three closes the prior thread and selects the next available model after the round-one model in the same effective route. When round one used an override that is absent from the ordinary role entries, round three therefore starts with the first available ordinary role entry.

## Local file

During the Agent-driven installation in `INSTALL.md`, model routing is a separate optional choice. The Agent starts from `examples/model-routing.toml`, replaces placeholders only with model identifiers available on the current host, removes unused example entries, shows the complete task overrides and role order, and writes the approved file to `$CODEX_HOME/codex-orchestration/model-routing.toml`. It never generates or changes routes implicitly.
