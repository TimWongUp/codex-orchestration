# Configuration

## Install scope

The installer manages or verifies these locations under `$CODEX_HOME` (default `~/.codex`):

- `skills/codex-orchestration` — symlink to the checkout.
- `skills/diagnosing-bugs` — symlink to the bundled complete debugging Skill when no valid installation exists.
- `skills/prototype` — symlink to the bundled complete prototype Skill when no valid installation exists.
- `agents/*.toml` — managed custom-agent copies.
- `hooks/orchestration_route.py` and `hooks/subagent_scope.py` — only with `--with-hooks`.
- `hooks.json` — merged with existing registrations, only with `--with-hooks`.
- `codex-orchestration/model-routing.toml` — only with `--routing-config`.

Unrelated files and hook registrations are preserved. Managed drift is reported and requires `--replace`.

## Existing Skill preflight

All three Skill targets are checked before any installation write:

- A link to this checkout is `CURRENT`.
- A valid same-named Skill from another source is `REUSE` and remains untouched.
- A missing Skill is planned for creation.
- An existing target with no valid matching `name` is a conflict; the installer stops before creating Skills or Agent files.

`--replace` may replace a reviewed differing symlink, including a same-named external symlink. It never replaces a physical Skill directory; move that directory manually if replacement is intentional.

The same preflight covers every managed Agent, optional Hook, and routing target. Known drift or a physical-path conflict prevents the complete plan from being applied; Hook registrations are updated only after the managed files pass preflight.

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
