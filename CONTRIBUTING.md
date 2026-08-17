# Contributing

Contributions are welcome. The current supported runtime is Codex on macOS.

Before opening a pull request:

```bash
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
```

Keep changes focused. Agent profiles must remain model-neutral, installer changes must preserve unrelated user configuration, and public files must not contain personal paths or credentials.

The bundled `diagnosing-bugs` and `prototype` Skills originate from Matt Pocock's MIT-licensed repository. Preserve their attribution and license; when syncing upstream changes, update the recorded source revision.

When public behavior changes, update both `README.md` and `README.zh-CN.md`.
