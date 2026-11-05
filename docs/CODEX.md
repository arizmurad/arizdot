# Codex setup

arizdot monitors local Codex desktop sessions on Windows. It does not add universal support for GPT models, ChatGPT web conversations, or remote/cloud sessions.

## Install

Extract the Codex preview ZIP and run `Install-arizdot.cmd`, or run `Install-Codex.cmd` from a source checkout. For manual installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe install_codex.py
```

The installer copies only arizdot-owned skill files under `~/.agents/skills/arizdot`. Its private pointer references the extracted application folder, and the helper runs with that folder's Python environment. It refuses to overwrite an unrelated same-name skill. Existing junctions to this source skill remain supported without duplicate registration.

For an older desktop version that discovers skills under `CODEX_HOME/skills`, explicitly use `install_codex.py --legacy`. Restart Codex if the new skill is not visible. Do not install both locations unnecessarily: same-name skills may appear twice.

## Activate and monitor

Select arizdot in the skill picker or explicitly invoke `$arizdot`. The skill does not activate implicitly. The host's picker appearance may differ across versions; this package does not create a new native built-in command.

The helper passes the invoking local conversation ID and waits for a matching UI acknowledgement. Merely finding an already-running dot is not considered successful activation. Other active local tasks are collected independently without changing the primary conversation.

Plan percentages count recorded completed steps. Configured scientific adapters use their own measurements. A completed assistant reply is not proof that a background calculation is complete. The local transcript and desktop navigation formats are experimental internal interfaces and may change between host releases.

If the host has no plan tool, the arizdot skill can report milestones with `report --steps-file <absolute-json-path>`. The file contains a `steps` array of named `step` / `status` objects, with statuses `pending`, `in_progress` or `completed`. The helper binds each report to the invoking active local conversation and turn; a new turn cannot inherit the previous turn's percentage. Newer commentary and native plan updates supersede older reports. Reports must be refreshed at verified milestone transitions. A report older than two minutes no longer supplies a percentage, even if other tools remain active. Tool calls remain diagnostics and are not displayed as completed project steps. Without a named plan, the panel explicitly says milestone progress has not been reported.

## Remove the registration

```powershell
.\.venv\Scripts\python.exe install_codex.py --remove
```

Use `--legacy --remove` for a copied legacy registration. Removal preserves edited files and leaves source junctions intact; it does not delete the application, transcripts or scientific work. The installer does not enable autostart.

## Official reference

[OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills) describes user skill discovery and explicit invocation. This project uses those skill entrypoints; the status adapter itself is maintained by arizdot.
