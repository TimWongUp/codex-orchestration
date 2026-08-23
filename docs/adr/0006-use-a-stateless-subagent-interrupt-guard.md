# Use a stateless subagent interrupt guard

`subagent_guard.py` guards only interrupting `send_input` calls. It accepts explicit user stop or replacement requests and bounded orchestration corrections with a closed reason code. It does not persist terminal markers or enforce `close_agent` ordering.

**Status:** accepted

**Decision:** nested `functions.exec` calls do not reliably surface `wait_agent` PostToolUse events, and session identifiers are not a stable association key across later tool calls. A marker-based close guard therefore denied valid closes while presenting a protection it could not enforce reliably. The runtime registration contains only `PreToolUse` with matcher `send_input$`; upgrades remove this suite's old wait and close registrations. The main agent still waits for a terminal result before closing an agent.

**Consequences:** the guard remains stateless and cannot verify correction evidence or one-shot use. It narrows correction messages to `wrong_model`, `wrong_role`, `descendant_orchestration`, or `scope_drift`, and the Skill states that a correction interrupt may terminate the agent. Evidence, bounded use, and close ordering remain main-agent responsibilities and are reviewed as orchestration behavior rather than claimed as Hook-enforced safety.
