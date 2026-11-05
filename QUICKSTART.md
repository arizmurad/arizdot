# Quick start

## Choose your package

Download the Codex, Claude, or Both Windows ZIP from the official arizdot Releases page. The core indicator is the same in every package; the default integration selected by the installer differs.

1. Install Python 3.11+ with Tkinter and the assistant you want to use.
2. Extract the ZIP to a permanent folder on your Windows computer.
3. Double-click **Install-arizdot.cmd**. It creates a local Python environment, downloads dependencies, and registers the selected integrations.
4. Wait for **Installed**, then close the installer and restart your assistant or open a new local session.

From a source checkout, use **Install-Codex.cmd** or **Install-Claude.cmd** to select one assistant. **Install-arizdot.cmd** selects both. There is no Windows autostart or automatic launch when the assistant opens.

## Open arizdot

| Assistant | Action |
| --- | --- |
| Codex desktop | Select arizdot in the skill picker, or invoke `$arizdot` |
| Claude Code | Run `/arizdot` |
| Claude Desktop Chat | `/` → Connectors → Add from arizdot → arizdot, then send the inserted prompt |

Approve first-use tool permissions yourself if the host asks. Claude Code requires an eligible account or API access; Pro is one supported option. Ordinary Claude Desktop Chat can use the local MCP integration on a Free account. Uploading a ZIP into a chat does not install the application on your Windows computer.

## Test the indicator

Activate it in a local conversation, then ask the assistant to complete a small task with a named three-step plan. Hover over the dot to see the task; click the task row for **Completed / Working now / Next target**. Move away to collapse it. A new hover starts with the task list and closed subprocesses.

Open another task to check concurrent rows. Double-click a row to return to that conversation where its host and chat ID permit it. Claude Desktop reports remain labelled as reported; they do not expose its internal execution.

You can also double-click inside an expanded subprocess. If a Claude Desktop task has no chat ID, paste its original `https://claude.ai/chat/...` URL into the one-time linking dialog. Use the private conversation address from your browser, not a public `/share/` snapshot link.

## If something is missing

Run `.\.venv\Scripts\python.exe doctor.py` from the application folder. Do not post its personal paths publicly. Restart the assistant after registration changes. See [Codex setup](docs/CODEX.md) or [Claude setup](docs/CLAUDE.md) before opening a redacted bug report.
