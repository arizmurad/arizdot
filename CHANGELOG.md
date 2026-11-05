# Changelog

## 0.1.0-preview.1 — Unreleased

First public preview prepared for Codex and Claude on Windows.

- A 32-pixel floating dot expands into a smooth, antialiased work panel.
- Concurrent local tasks retain separate progress and freshness.
- A shared background-job registry separates actual execution from chat turns. Independent file, HTTPS, process and optional Kaggle readers continue without a model. The local launch supervisor registers authorized background commands and observes real exit status.
- Newer activity and concurrent snapshots supersede cached step labels. Claude Desktop reports replace old plans and can update task titles; stale reports and expired milestone percentages are no longer presented as current. Claude Code supports the same explicit milestone bridge as Codex.
- Subprocesses prioritize milestone progress rather than generic tool calls. A conversation-and-turn-bound reporting bridge supplies named Codex milestones when the host has no plan tool. Stale work is explicitly labelled as recorded history.
- Small supplied OpenAI / Claude logos and separate blue / warm copper labels distinguish the assistants without changing health colors.
- Codex and Claude tasks share one panel; rows stay in place during clicks and completed subprocesses remain readable until pointer exit.
- Selecting a task reveals completed steps, current work and the next target inline.
- Double-click routing retains the clicked provider/task across layout changes and supports the expanded subprocess body. Claude Desktop can privately bind its original chat URL without confusing share IDs and monitor IDs.
- Leaving the panel collapses subprocesses and resets the next hover.
- Codex skill activation, Claude Code session hooks and Claude Desktop MCP reports use separate provider IDs.
- Named Claude Desktop milestones and optional scientific adapters keep progress scoped to actual evidence.
- English and Azerbaijani interfaces, drag alignment and provider-aware chat return.
- Separate Codex, Claude and combined installer profiles.
- No side notifications, separate status window, implicit activation or Windows autostart.

This is a preview. Host versions and policies can affect skill discovery, hooks and deep links. macOS/Linux rendering and ordinary ChatGPT web monitoring are not implemented.
