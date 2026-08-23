# Use a stateless subagent lifecycle guard

`subagent_guard.py` guards interrupting `send_input` calls and may add advisory context when the host surfaces a direct non-terminal `wait_agent` result. It accepts explicit user stop or replacement requests and bounded orchestration corrections with a closed reason code. It does not persist terminal markers or enforce `close_agent` ordering.

**Status:** accepted

**Decision:** nested `functions.exec` calls do not reliably surface `wait_agent` PostToolUse feedback, and session identifiers are not a stable association key across later tool calls. A marker-based close guard therefore denied valid closes while presenting a protection it could not enforce reliably. Each lifecycle call remains a separate model-visible operation: direct where available, or one call per exec program with the structured result returned unchanged. The runtime registers `PreToolUse` with matcher `send_input$` and a stateless `PostToolUse` advisory with matcher `wait_agent$`. It does not register outer exec or close calls. When a direct wait event is available, the advisory treats timeout, empty, missing, partial, and unrecognized results as non-terminal without associating state across calls. The main agent still waits for an explicit terminal entry before closing a target.

**Consequences:** the guard remains stateless and cannot verify correction evidence, one-shot use, or close eligibility. It narrows correction messages to `wrong_model`, `wrong_role`, `descendant_orchestration`, or `scope_drift`, and the Skill states that a correction interrupt may terminate the agent. Evidence, bounded use, and close ordering remain main-agent responsibilities and are reviewed as orchestration behavior rather than claimed as Hook-enforced safety.
