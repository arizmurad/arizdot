# arizdot v0.1.0-preview.1 — Codex and Claude for Windows

A small dot for Codex and Claude, created by **ariztotell** as part of **ariztools**.

This first Windows preview shows concurrent work in a compact floating panel. Hover for the task list; click a task for completed steps, current work and the next target. Move away to collapse the panel. Double-click to return to the corresponding chat when the host supports it.

Codex and Claude can run at the same time: both assistants' tasks appear together with independent progress and subprocess details. Background updates do not move the rows you are clicking or dismiss an open subprocess when a task finishes.

## Choose a download

| File | Default integration |
| --- | --- |
| `arizdot-0.1.0-preview.1-codex-windows.zip` | Local Codex desktop |
| `arizdot-0.1.0-preview.1-claude-windows.zip` | Claude Code and Claude Desktop Chat |
| `arizdot-0.1.0-preview.1-both-windows.zip` | Both assistants |
| `SHA256SUMS.txt` | Checksums for the three packages |

Extract your ZIP, run **Install-arizdot.cmd**, and restart the assistant or open a new local session. Requires Windows 10/11, Python 3.11+ with Tkinter and internet access for setup. No API key or administrator rights are needed by arizdot itself. Assistant access and tool permissions remain separate.

## Included

- Smooth dot-to-panel animation, separate concurrent task rows and inline subprocesses.
- Codex skill activation, Claude Code event hooks and Claude Desktop MCP tools.
- Named milestones and plan-count percentages, with clear LIVE / STALE / OFFLINE / RECORDED states.
- Progress-first subprocesses and explicit Codex milestone reports when the host has no plan tool; reports cannot carry over into a different turn.
- Shared Codex / Claude Code milestone reporting, independent plan expiry, newer-operation precedence and replacement Claude Desktop reports prevent old work from remaining current.
- Background jobs outlive chat replies through shared file/API/process readers and optional Kaggle status/log monitoring. An authorized local launch wrapper registers background commands automatically. Service authentication remains an explicit account step.
- English and Azerbaijani interfaces, drag alignment and provider-aware chat return.
- Explicit activation, automatic collapse on pointer exit, no side notifications and no Windows autostart.

## Preview limits

Ordinary ChatGPT web chats and macOS/Linux rendering are not supported. Claude Desktop Chat status is explicitly reported by Claude, not independently observed execution. Claude Code hooks, skill discovery and exact chat return depend on host versions and policy. No percentage or ETA is invented for unmeasured work.

The release packages exclude private state and machine registrations. MIT permits forks and redistribution; changes to the official project require maintainer review. Please report reproducible problems with redacted diagnostics through Issues.
