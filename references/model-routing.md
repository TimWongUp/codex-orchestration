# Model routing

Model choices are local configuration, not repository policy.

## Selection order

1. Follow an explicit user model request.
2. Otherwise read `$CODEX_HOME/codex-orchestration/model-routing.toml` when it exists.
3. Otherwise inherit the current Codex model, reasoning effort, and service tier.

For a single agent or `coverage`, choose the first available route entry. Move to the next entry only when the prior model is unavailable, spawning fails, or the result does not meet the task's completion condition.

For `panel` and the panel portion of `hybrid`, deliberately select different available models from the role route. Different reasoning levels of the same model do not count as model diversity.

Worker rounds one and two keep the same model and thread. Round three closes the prior thread and selects the next available model in the same role route.

## Local file

During the Agent-driven installation in `INSTALL.md`, model routing is a separate optional choice. The Agent starts from `examples/model-routing.toml`, replaces placeholders only with model identifiers available on the current host, shows the complete route order, and writes the approved file to `$CODEX_HOME/codex-orchestration/model-routing.toml`. It never generates or changes routes implicitly.
