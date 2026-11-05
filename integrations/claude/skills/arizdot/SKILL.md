---
name: arizdot
description: Activate the local arizdot floating work indicator for this Claude Code session, or read its observed work and plan progress.
argument-hint: "[status]"
hooks:
  UserPromptSubmit:
    - hooks:
        - type: command
          command: python
          args: ["${CLAUDE_SKILL_DIR}/scripts/hook.py"]
          timeout: 3
  PreToolUse:
    - matcher: "*"
      hooks:
        - type: command
          command: python
          args: ["${CLAUDE_SKILL_DIR}/scripts/hook.py"]
          timeout: 3
  PostToolUse:
    - matcher: "*"
      hooks:
        - type: command
          command: python
          args: ["${CLAUDE_SKILL_DIR}/scripts/hook.py"]
          timeout: 3
  PostToolUseFailure:
    - matcher: "*"
      hooks:
        - type: command
          command: python
          args: ["${CLAUDE_SKILL_DIR}/scripts/hook.py"]
          timeout: 3
  PermissionRequest:
    - matcher: "*"
      hooks:
        - type: command
          command: python
          args: ["${CLAUDE_SKILL_DIR}/scripts/hook.py"]
          timeout: 3
  Stop:
    - hooks:
        - type: command
          command: python
          args: ["${CLAUDE_SKILL_DIR}/scripts/hook.py"]
          timeout: 3
  StopFailure:
    - hooks:
        - type: command
          command: python
          args: ["${CLAUDE_SKILL_DIR}/scripts/hook.py"]
          timeout: 3
  SessionEnd:
    - hooks:
        - type: command
          command: python
          args: ["${CLAUDE_SKILL_DIR}/scripts/hook.py"]
          timeout: 3
---

# arizdot for Claude Code

For `/arizdot`, run:

`python "${CLAUDE_SKILL_DIR}/scripts/arizdot_skill.py" start --provider claude --session "${CLAUDE_SESSION_ID}"`

For `/arizdot status`, run:

`python "${CLAUDE_SKILL_DIR}/scripts/arizdot_skill.py" status --provider claude --session "${CLAUDE_SESSION_ID}"`

The installer writes exact PowerShell commands with safely quoted executable and script paths. Run the installed command with the PowerShell tool. The helper obtains the project directory from its working directory without shell interpolation. Interpret `$ARGUMENTS` as the requested operation, never interpolate arbitrary arguments into a shell command. User operations are start/default or status; `report` is the internal milestone-update command described below. Require both `running: true` and `activated: true` before reporting successful activation. Do not guess a session ID if substitution failed.

The hooks observe this session only after the skill is invoked. They do not launch the indicator, approve permissions, alter tool input, block turns, or publish data. Keep TodoWrite/task statuses current at actual milestone transitions throughout the monitored task, including later user turns. Their local snapshots carry observed action completions and real task counts; a completed tool action is not proof that a project milestone finished, and a completed reply does not force the plan to 100%. If enterprise policy prevents hooks, report the missing status source instead of claiming live telemetry. Describe hook state as observed events, not continuous access to Claude's internal reasoning. Keep scientific background jobs separate from conversational completion.

If no task-plan tool is available, write a UTF-8 JSON file with `{"steps":[{"step":"Concrete milestone","status":"in_progress"},{"step":"Next milestone","status":"pending"}]}` and run `python "${CLAUDE_SKILL_DIR}/scripts/arizdot_skill.py" report --provider claude --session "${CLAUDE_SESSION_ID}" --steps-file <absolute-json-path>`. Resend the full list immediately after activation for substantive work, before/after each real milestone and before the final answer. Use `completed` only after verification. Refresh long-running milestone reports within two minutes when their status is actually known; never send a heartbeat that merely disguises an unknown status. Each user turn gets a fresh plan. Plan percentages expire independently of tool activity; hooks always show the latest real operation rather than an older in-progress task name.

Do not enable Windows autostart or publish to GitHub. Do not read or upload unrelated Claude sessions. For ordinary Claude Desktop Chat use the bundled local MCP tools; this skill targets terminal/IDE Claude Code and local Desktop Code sessions.

Register EVERY background job you actually start while monitoring, immediately after verifying its launch and before returning the reply. This applies to local processes and remote work of all kinds. Write a JSON file with `{"title":"Concrete work","run_id":"actual-run-identity","source":{"type":"json_file","path":"C:/absolute/status.json"}}`, then run `python "${CLAUDE_SKILL_DIR}/scripts/arizdot_skill.py" job-register --provider claude --session "${CLAUDE_SESSION_ID}" --job-file <absolute-json-path>`. Use a real JSON status file, HTTPS JSON endpoint (`http_json`), local PID (`process`), service connector (`kaggle`), or explicitly `reported` source. Never invent a source or relaunch work to monitor it. Prefer independent telemetry. See the application's `docs/BACKGROUND-JOBS.md` for the signal schema.

Registrations outlive replies and later prompts. Keep the returned job_id. `job-list` rediscovers this session's jobs; `job-update --job-id <id> --job-file <status-json>` refreshes only a `reported` job; `job-dismiss --job-id <id>` hides the entry without stopping the job. Run these commands with the same `--provider claude --session` context. A model-reported job is not live when Claude is idle. Hook Stop/SessionEnd must not complete independently running jobs.

For a NEW, already-authorized local background command, prefer `run --job-file <launch-spec>` with the same provider/session context. The spec contains title, absolute cwd and a command argument array. Its independent supervisor registers the actual child and passes ARIZDOT_STATUS_FILE/ARIZDOT_RUN_ID for detailed signals. Use job-register for existing work; never relaunch it for monitoring or start unauthorized commands.
