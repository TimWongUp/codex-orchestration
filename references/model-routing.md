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

Copy `examples/model-routing.toml` outside the repository and replace placeholders with model identifiers available on the current host. Install it with:

```bash
python3 scripts/install.py --apply --routing-config /path/to/model-routing.toml
```

The installer writes it to `$CODEX_HOME/codex-orchestration/model-routing.toml`. It never generates or changes routes implicitly.
