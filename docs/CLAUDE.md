# Claude setup

arizdot supports local Claude Code sessions and ordinary Claude Desktop Chat through different interfaces. The native indicator requires Windows.

## Install

Run `Install-arizdot.cmd` from the Claude ZIP, or `Install-Claude.cmd` from a source checkout. For manual setup, run from the extracted application folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-claude.txt
.\.venv\Scripts\python.exe install_claude.py --code --desktop
```

The installer adds a personal skill under `~/.claude/skills/arizdot` and merges one local MCP entry into Claude Desktop's configuration. It detects migrated Windows Store data under `%LOCALAPPDATA%/Claude-Data/claude_pzs8sxrjxfjjc`, older packaged data, and the traditional `%APPDATA%/Claude` folder. `doctor.py` prints the selected configuration path. It preserves unrelated settings, backs up an existing Desktop configuration, and refuses to overwrite unmanaged entries. Autostart is not enabled. Restart Claude Desktop after changing its MCP configuration.

The generated skill uses absolute executable and hook paths. Source files remain under `integrations/claude/skills/arizdot`; the installed skill carries a pointer to this distribution. Keep the project folder in place while using these registrations.

## Claude Code and the Desktop Code tab

Use `/arizdot` to activate; use `/arizdot status` to read status. The skill passes `${CLAUDE_SESSION_ID}` explicitly and namespaces it as `claude:<uuid>`, separate from Codex UUIDs. Activation succeeds only after the UI acknowledges the matching provider/session.

Hooks start after the skill is invoked and remain active for that Code session. They observe prompts being submitted, tool activity, task plans, permission waits, stops and failures. They never launch the indicator on their own, start scientific jobs, rewrite tool input, approve permissions, or block the underlying action. Task changes count after successful completion and repeated tool events are deduplicated. Stop preserves unfinished plan steps; a reply finishing does not prove a background task finished.

If hooks are missing, inspect `/hooks` and your organization policy. The indicator reports unavailable/stale data rather than bypassing host restrictions. Invoke `/arizdot` in the session you want to track; Claude does not expose the same visual navigation feed as Codex. A new explicit Codex navigation resumes Codex following.

## Ordinary Claude Desktop Chat

Verify the local MCP connection in Desktop settings, then ask Claude: **“Open arizdot and track this task.”** If the client exposes MCP prompts, the server also supplies an `arizdot` prompt. A literal `/arizdot` skill command is supported on compatible Claude Code surfaces, not guaranteed in ordinary Desktop Chat.

The local stdio server exposes:

- `arizdot_open(title, monitor_id?, conversation_id?)`: opens/reveals the indicator. Preserve the returned `monitor_id` in this conversation and reuse it. Supply a real Claude `conversation_id` only when known.
- `arizdot_report(monitor_id, current, completed?, total?, next_step?, phase?, steps?, title?, new_turn?)`: reports concrete work, a short task title and optional real counts. Always resend the full `steps` list of named `{step, status}` milestones; status is `pending`, `in_progress`, or `completed`. Omitted steps clear the old plan. Set `new_turn=true` on the first report of each later user turn. Counts are derived from steps and must agree with them if supplied. Phases: `working`, `waiting`, `completed`, `error`. Invalid updates do not mutate the last good state.
- `arizdot_status(monitor_id)`: reads this conversation's report without opening the indicator.
- `arizdot_job_register(monitor_id, title, source, run_id?)`: attaches real background work to a status source, independently of conversation turns.
- `arizdot_job_update(monitor_id, job_id, status)`: updates a same-owner, explicitly reported job.
- `arizdot_jobs(monitor_id)`: rediscovers the conversation's registered background jobs.

See [Background jobs](BACKGROUND-JOBS.md) for independent file/API/process readers, the local launch supervisor, optional service connectors and their authentication requirements. Closing Claude or completing a reply does not complete those jobs.

Connecting the server does not launch the UI. No port, public URL, API key or model call is needed. Separate conversations must keep separate monitor IDs.

Active local Codex and registered Claude tasks appear together in the panel. Click a task row for its inline completed steps, current subprocess and next target. Model-reported work stays labelled as reported; it is never presented as independently observed execution. Side notifications and the separate single-click status window are removed. Restart Claude Desktop after updating this server to load the new optional `steps` tool argument.

The MCP interface cannot read ordinary Desktop Chat's internal execution or infer its chat ID. Status is labelled **reported by Claude**, not independently observed computation, and ages into stale data. No fabricated ETA or fractional SCF completion is added.

An activation alone is not a live feed. The arizdot prompt instructs Claude to report immediately, before and after real milestones, and on later turns while the monitor is in use. Desktop Chat must actually call `arizdot_report` for those changes to arrive; the server cannot intercept unrelated tools or force model compliance. A report without steps clears old milestones and counts; a new task can update its title and explicitly start a new turn. Reports older than two minutes show **Waiting for a new status update**, with no current percentage or next target. Restart Claude Desktop and invoke the arizdot prompt again after updating these instructions.

Claude Code hooks show the latest actual operation rather than an old in-progress plan label. Milestone percentages expire independently of tool activity. When no task-plan tool is available, the installed skill uses `report --provider claude --session <session-id> --steps-file <absolute-json-path>` to refresh verified milestones through the same local command bridge as Codex. A new UserPromptSubmit event clears the previous turn's plan.

Double-click a task row or its expanded subprocess to return to that task. Desktop Chat uses its real conversation UUID. If the host did not supply it, arizdot asks for the original `https://claude.ai/chat/...` URL once per monitor and stores the binding privately with its existing state. Right-click the task and choose **Link this task to chat…** to replace a binding. Public `/share/` snapshot links are rejected. Reporting progress preserves a saved binding; the monitor UUID is never used as a guessed chat UUID. For Code sessions, the installed CLI requests `claude --desktop --resume <session-id>`; missing CLI support opens recent chats with an explicit selection hint.

## Scientific work

Owner-configured private `config/sources.json` can bind an adapter to `claude:<session-uuid>` or `claude-desktop:<monitor-uuid>`. It uses the same QE/cloud adapters as Codex. Explicit scientific telemetry takes priority over conversational completion. MCP tools do not modify these bindings or launch/stop calculations.

## Verify and remove

```powershell
.\.venv\Scripts\python.exe doctor.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe install_claude.py --code --desktop --remove
```

Removal preserves unrelated settings and user-edited files. Tests use synthetic events, a real SDK stdio server/client in modern and legacy protocol modes, and the native Windows indicator. They do not authenticate to either assistant.

Local verification covers the skill-to-hook-to-UI and MCP-to-UI acknowledgement chains, actual stdio protocol discovery, invalid-input handling and native Windows interactions. A Claude Desktop 4.4212.0 Free-account connection was checked for successful initialization, tool discovery and its enabled connector/prompt entry. Claude Code hook availability and account policies still require testing in the intended host. The preview does not claim universal compatibility or error-free operation.

## Primary references

- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Desktop Code](https://code.claude.com/docs/en/desktop)
- [Local MCP servers](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop)
- [Desktop deep links](https://support.claude.com/en/articles/14729294-open-claude-desktop-with-a-link)
- [Official MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
