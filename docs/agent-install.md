# Agent-assisted installation

Open a Codex task in this checkout and paste:

```text
Install this codex-orchestration checkout for my local Codex environment.

1. Read README.md, AGENTS.md, docs/configuration.md, docs/hooks-and-prompts.md, and scripts/install.py before changing anything.
2. Verify that the host is macOS and that the installed Codex version supports custom agents under ~/.codex/agents.
3. Run `python3 scripts/validate.py` and stop on source validation failures.
4. Run `python3 scripts/install.py` as a dry run. For `codex-orchestration`, `diagnosing-bugs`, and `prototype`, report whether each Skill is current, reused from an existing valid installation, missing, or conflicting. Also summarize every planned agent file, hook file, hooks.json change, and existing drift.
5. Reuse valid existing same-named Skills by default. Do not replace a Skill symlink, overwrite drift, or change my existing hook defaults without showing the exact impact and receiving confirmation. Never replace a physical Skill directory.
6. Ask whether I want hooks installed. If yes, use `--with-hooks`; otherwise install only the skill and agent profiles.
7. Ask separately whether I want a custom model route. If yes, copy `examples/model-routing.toml` to a temporary file, replace placeholders only with model IDs and reasoning levels currently available on this host, show me the proposed routes, then pass it with `--routing-config`. Do not copy another user's routes or edit unrelated Codex defaults.
8. Apply the reviewed plan with `python3 scripts/install.py --apply` plus only the options I approved.
9. Run `python3 scripts/validate.py --runtime` and a final installer dry run. Report remaining drift and tell me to start a new Codex task so custom agent types reload.

Do not add repository-specific paths, personal names, private endpoints, API keys, Vault paths, or Windows configuration to this checkout.
```
