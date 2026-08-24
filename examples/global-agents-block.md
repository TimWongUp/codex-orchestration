<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:START -->
## Subagent orchestration

- Main agent only: load `codex-orchestration` before creating, coordinating, or waiting for subagents, and apply its Review risk gate before delivery when code changed.
- The main agent owns Git, acceptance, review selection, and final delivery.
- Simple tasks and ordinary documentation stay with the main agent.
- Writable workers require the canonical single-writer lease; derived agents never orchestrate descendants.
<!-- CODEX-ORCHESTRATION:GLOBAL-RULES:END -->
