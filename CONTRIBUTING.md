# Contributing

Contributions are welcome. Bug reports and feature requests belong in GitHub Issues. Report suspected vulnerabilities privately according to the [security policy](SECURITY.md), not through a public Issue. Do not include credentials, private data, or unredacted logs in Issues or pull requests.

The target local runtimes are Codex on macOS and native Windows. Development requires Git and Python 3.9 or newer. Install and run the complete check set for your platform before opening a pull request.

On macOS:

```text
python3 -m pip install "ruff>=0.12.0" "pyright>=1.1.400"
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
ruff check .
ruff format --check .
pyright
bash -n skills/diagnosing-bugs/scripts/hitl-loop.template.sh
```

On native Windows PowerShell:

```text
py -3 -m pip install "ruff>=0.12.0" "pyright>=1.1.400"
py -3 scripts/validate.py
py -3 -m unittest discover -s tests -v
ruff check .
ruff format --check .
pyright
[void][scriptblock]::Create((Get-Content -Raw 'skills/diagnosing-bugs/scripts/hitl-loop.template.ps1'))
```

If Windows exposes the interpreter as `python` instead of `py -3`, substitute that command consistently. CI repeats these checks on macOS and Windows with Python 3.9 and 3.13. A release may claim support only after all matrix jobs pass.

Keep changes focused. Agent profiles must remain model-neutral, installation-contract changes must preserve unrelated user configuration, and public files must not contain personal paths or credentials.

The bundled `diagnosing-bugs` and `prototype` Skills originate from Matt Pocock's MIT-licensed repository. Preserve their attribution and license; when syncing upstream changes, update the recorded source revision.

When public behavior changes, update both `README.md` and `README.zh-CN.md`.
