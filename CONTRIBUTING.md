# Contributing to arizdot

arizdot is part of [ariztools](https://github.com/arizmurad/ariztools), created by **ariztotell** and maintained on GitHub by **@arizmurad**.

## Use, modify, and share

The MIT license permits forks, modifications, redistribution, and commercial use. Keep the copyright and license notice. You do not need maintainer approval to publish your own fork. Clearly identify modified distributions; do not imply that they are an official arizdot release.

## Propose a change to this repository

1. Open an issue for a substantial feature, provider change, or interaction change before implementing it.
2. Fork the repository and create a focused branch.
3. Explain the concrete problem and the resulting behavior in your pull request.
4. Run the checks below. Include a screenshot or short recording for visual changes, using synthetic tasks and no private conversations.
5. Request review from **@arizmurad** and address feedback. Only the maintainer accepts and merges changes into the official project.

No automatic merging is used. Fork publication and acceptance into this repository are separate: the first is permitted by the license, while the second requires maintainer review. CODEOWNERS identifies the reviewer; the repository owner must also enable GitHub's required-review settings to enforce this policy.

## Local checks

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-claude.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe package_source.py --release
```

On an interactive Windows desktop, also run the native UI checks:

```powershell
$env:ARIZDOT_NATIVE_TEST = '1'
.\.venv\Scripts\python.exe -m unittest tests.test_island -v
```

Keep percentages tied to countable plan steps or measurements. Do not invent progress, ETA, background completion, or live telemetry. Keep providers and conversations separate. Preserve explicit activation, hover exit behavior, and the absence of side notifications.

Do not commit `config/`, transcripts, credentials, private file paths, scientific project bindings, virtual environments, or screenshots of real conversations. Redact diagnostic output before attaching it to an issue.

Contributions are licensed under the project's MIT license. Report bugs with the issue form; report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
