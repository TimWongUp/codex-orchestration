# Configuration

## Install scope

The installer manages these locations under `$CODEX_HOME` (default `~/.codex`):

- `skills/codex-orchestration` — symlink to the checkout.
- `agents/*.toml` — managed custom-agent copies.
- `hooks/orchestration_route.py` and `hooks/subagent_scope.py` — only with `--with-hooks`.
- `hooks.json` — merged with existing registrations, only with `--with-hooks`.
- `codex-orchestration/model-routing.toml` — only with `--routing-config`.

Unrelated files and hook registrations are preserved. Managed drift is reported and requires `--replace`.

## Model routes

The repository does not ship active routes. Start from `examples/model-routing.toml`, replace placeholders with values available on the current host, review the full order, then install it explicitly.

Without a local route file, the main agent inherits the current Codex model configuration.

## Installer modes

```bash
python3 scripts/install.py                         # dry run
python3 scripts/install.py --check                 # fail if managed state differs
python3 scripts/install.py --apply                 # skill + agents
python3 scripts/install.py --apply --with-hooks    # skill + agents + hooks
python3 scripts/install.py --apply --replace       # replace reviewed managed drift
```

Use `--codex-home` only for an alternate Codex home or isolated testing.
