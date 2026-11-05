# Background work that outlives the chat

Conversation activity and background execution have different lifetimes. A reply ending or a new prompt starting never completes, resets or removes a registered background job. Codex and Claude share the same registry. Keep arizdot running; the assistant and browser can be closed when the job has an independent source.

| Source | Observed evidence | Required connection |
| --- | --- | --- |
| `json_file` | Independently updated local/synchronized JSON | A real worker status file |
| `http_json` | HTTPS JSON endpoint | Existing endpoint and any required authentication |
| `process` | Local PID and its creation identity | A progress source for detailed stages; exit alone does not verify results |
| `kaggle` | Version-pinned platform status and structured logs through the official API | One-time account authentication and structured log events |
| `reported` | Explicit assistant reports, labelled reported | Further reports; cannot update unattended while the assistant is idle |

These adapters do not imply every service exposes a usable API. Each job needs registration and a real source. arizdot cannot discover an unknown remote execution from a model mentioning it. Both installed integrations require registration immediately after each verified launch. Existing work can be attached without rerunning it.

## Automatic local launch registration

For a NEW, already-authorized background command, write a private launch file:

```json
{
  "title": "Export verified rows",
  "cwd": "C:/Work/export",
  "command": ["C:/Python/python.exe", "export.py"]
}
```

Call the installed helper with `run --job-file <absolute-spec-path>` and the normal provider/session context. It starts an independent supervisor, registers the job and acknowledges a real child PID. No shell command string is accepted. Execution and exit status are observed after the launch call returns; a successful exit is labelled with output verification still required. No project percentage is invented.

The worker receives `ARIZDOT_RUN_ID` and `ARIZDOT_STATUS_FILE` and can use `job_signal.JobSignal.write` to publish actual stages and measurements. Only a recent matching run signal is merged. Private arguments and output logs stay in `config/runs/`, outside release packages. Closing arizdot does not stop these commands.

## Attach existing work

Write a registration file and call `job-register --job-file <absolute-path>`:

```json
{
  "title": "Density calculation",
  "run_id": "actual-execution-identity",
  "source": {"type": "json_file", "path": "C:/Work/calculation/status.json"}
}
```

The helper obtains the owning conversation from the host or explicit session arguments. Keep the returned job_id. `job-list` rediscovers that conversation's jobs. `job-dismiss --job-id <id>` hides only the entry, never execution. Double-click a job to return to its owning assistant/chat.

Desktop Chat uses `arizdot_job_register`, `arizdot_job_update` and `arizdot_jobs` with its monitor ID. Only a same-owner `reported` job accepts model updates. Models cannot overwrite observed file/API/process state.

## Status signal

```json
{
  "run_id": "actual-execution-identity",
  "updated_at": "2026-01-01T12:00:00+00:00",
  "state": "running",
  "current": "Validate exported rows",
  "next": "Write audit report",
  "steps": [
    {"step": "Read input", "status": "completed"},
    {"step": "Validate rows", "status": "in_progress"},
    {"step": "Write audit", "status": "pending"}
  ],
  "metrics": "12000 rows checked"
}
```

States: queued, running, waiting, completed, failed, cancelled, unknown. Instead of steps, producers may provide real integer completed/total units. UTC-aware ISO timestamps and Unix seconds are accepted. Matching run IDs prevent a reused source from adopting another execution. Write atomically, ideally through JobSignal. Verify results before claiming project completion.

Emit real execution health during long stages. Static files are not live connections. Errors/stale running signals suppress old current progress; verified terminal results remain readable. PID creation checks prevent adopting a recycled process. Readers run outside the animation thread.

HTTPS sources use `{"type":"http_json","url":"https://example.org/status.json","token_env":"PROJECT_STATUS_TOKEN"}`. Credentials stay in environment variables. Cross-origin redirects are rejected. HTTP is accepted only on loopback. Reads are bounded by time and size; there are no arbitrary job-control commands or uploads.

## Optional Kaggle connector

Install requirements-kaggle.txt, then run Connect-Kaggle.cmd for the official login. The CLI requests resources.admin:* account scope; arizdot only calls metadata, status and logs. Review its permission screen yourself and keep credentials out of chat. Existing notebooks are not changed, relaunched or stopped.

The source has type kaggle, kernel owner/slug/version, a structured log marker and optional expected_cases. Without an explicit version, the connector resolves it once and pins vN; scriptVersionId is not a version label. Expected case matching protects calculation identity. Platform state and calculation telemetry age are distinct. SCF iteration/error/target are measurements, not an invented elapsed-time percentage.

Existing structured controller logs can be consumed without changing running calculations. Other workers can emit ARIZDOT_PROGRESS followed by JSON with updated_UTC, status, case, current/next and optional real counts. Raw notebook logs, remote PIDs and credentials are not copied into the public project.

Official references: [Kaggle status/logs](https://github.com/Kaggle/kaggle-cli/blob/main/skills/references/kernels.md), [authentication](https://github.com/Kaggle/kaggle-cli/blob/main/skills/references/auth.md).
