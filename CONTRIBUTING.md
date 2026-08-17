# Contributing

Contributions are welcome. The target local runtimes are Codex on macOS and native Windows; both CI runners must pass before a release claims support.

Before opening a pull request:

```text
python scripts/validate.py
python -m unittest discover -s tests -v
```

Keep changes focused. Agent profiles must remain model-neutral, installation-contract changes must preserve unrelated user configuration, and public files must not contain personal paths or credentials.

The bundled `diagnosing-bugs` and `prototype` Skills originate from Matt Pocock's MIT-licensed repository. Preserve their attribution and license; when syncing upstream changes, update the recorded source revision.

When public behavior changes, update both `README.md` and `README.zh-CN.md`.
