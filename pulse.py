"""Read local Codex sessions; independent background sources are routed separately."""
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class State:
    status: str = "Gözləyir"
    stage: str = "Codex sessiyası gözlənilir"
    active: bool = False
    plan: list = field(default_factory=list)
    updated: float = 0
    started: float = 0
    title: str = "Codex tapşırığı"
    detail: str = ""
    background: dict | None = None
    observed_at: float = 0
    turn_id: str = ''
    source_path: str = ''
    source_modified: float = 0
    session_ref: str = ''
    completed_actions: list = field(default_factory=list)
    pending_actions: dict = field(default_factory=dict)
    action_serial: int = 0
    detail_serial: int = 0
    plan_serial: int = 0
    revision: int = 0
    milestones: dict = field(default_factory=dict)

    @property
    def work_plan(self):
        if self.milestones and self.milestones.get('revision',-1)>=self.plan_serial and time.time()-self.milestones['updated']<=120:
            return self.milestones['steps']
        return self.plan

    @property
    def freshness(self):
        if self.observed_at and time.monotonic()-self.observed_at>30:return 'offline'
        if self.observed_at and time.monotonic()-self.observed_at>8:return 'stale'
        if self.background:return self.background.get('snapshot_status','stale')
        if self.active and self.source_modified and time.time()-self.source_modified>120:return 'stale'
        if self.active and self.updated and time.monotonic()-self.updated>120:return 'stale'
        return 'live' if self.active else 'recorded'

    def message(self, content):
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
        else:
            return
        text = " ".join(text.split()).strip()
        if text and not text.startswith("<"):
            self.detail = text[:500]
            self.revision+=1;self.detail_serial=self.revision

    @property
    def current(self):
        if self.background:
            return self.background["current"]
        if self.active and self.freshness in ('stale','offline'):return 'Yeni status məlumatı gözlənilir'
        step = next((p.get("step") for p in self.work_plan if p.get("status") == "in_progress"), None)
        if self.milestones and self.work_plan is self.milestones['steps'] and self.milestones.get('revision',-1)>=self.detail_serial:
            return step or ('Mərhələlər tamamlandı' if all(p['status']=='completed' for p in self.work_plan) else self.stage)
        if step and self.plan_serial>=self.detail_serial:return step
        return self.detail or step or self.stage

    @property
    def current_action(self):
        return next(reversed(self.pending_actions.values()),'') if self.pending_actions else ''

    @property
    def percent(self):
        if self.background:
            return self.background["percent"]
        if self.active and self.freshness in ('stale','offline'):return None
        if not self.work_plan:
            return None
        return round(100 * sum(p.get("status") == "completed" for p in self.work_plan) / len(self.work_plan))

    @property
    def next_step(self):
        if self.background:
            return self.background["next"]
        if self.active and self.freshness in ('stale','offline'):return ''
        pending=next((p.get("step","") for p in self.work_plan if p.get("status")=="pending"),"")
        return "Sonra: "+pending if pending else ""

    @property
    def progress_scope(self):
        if self.background:
            return self.background["scope"]
        if self.milestones and not self.work_plan:return 'Mərhələ statusu yenilənməlidir'
        if self.work_plan:
            done=sum(p.get("status")=="completed" for p in self.work_plan)
            return f"{done}/{len(self.work_plan)} addım · plan üzrə"
        return "Faiz ölçülmür · iki kliklə söhbətə qayıt"

    @property
    def working(self):
        if self.freshness=='offline':return False
        return self.background["active"] if self.background else self.active

    @property
    def live_title(self):
        return self.background.get('title',self.title) if self.background else self.title

    @property
    def live_badge(self):
        return self.background.get('badge','') if self.background else ('RUN' if self.active else 'IDLE')

    @property
    def live_metrics(self):
        return self.background.get('metrics','') if self.background else ''

    @property
    def live_health(self):
        return self.background.get('health','') if self.background else self.status

    @property
    def live_tone(self):
        if self.freshness=='offline':return 'red'
        if self.freshness=='stale':return 'amber'
        return self.background.get('tone','green' if self.working else 'amber') if self.background else ('green' if self.active else 'gray')

    def feed(self, row):
        d = row.get("payload", {})
        if not isinstance(d, dict):
            return
        kind = d.get("type", "")
        if row.get("type") == "event_msg":
            if kind in ("task_started", "turn_started"):
                self.turn_id=d.get('turn_id') or row.get('timestamp') or str(self.revision+1)
                self.revision+=1;self.milestones={}
                self.active, self.plan = True, []
                self.detail = ""
                self.completed_actions=[];self.pending_actions={};self.action_serial=0
                self.status, self.stage = "İşləyir", "Tapşırığı araşdırır"
                self.started = time.monotonic()
            elif kind in ("task_complete", "task_completed", "turn_completed"):
                self.active = False
                self.pending_actions={}
                self.status, self.stage = "Cavab hazırdır", "Cavab hazırdır"
            elif kind in ("turn_aborted", "task_interrupted"):
                self.active = False
                self.pending_actions={}
                self.status, self.stage = "Dayandırıldı", "İş dayandırılıb"
            elif kind == "item_completed":
                self.item(d.get("item", {}))
            elif kind == "agent_message" and d.get("phase") == "final":
                self.active = False
                self.status, self.stage = "Cavab hazırdır", "Cavab hazırdır"
            elif kind == "agent_message":
                self.message(d.get("message", ""))
        elif row.get("type") == "response_item":
            if kind in ("function_call", "custom_tool_call"):
                self.tool(d.get("name", ""), d.get("arguments", {}))
                from activity import label
                call=d.get('call_id') or d.get('id')
                if call:self.pending_actions[call]=label(d.get('name',''),d.get('arguments'))
            elif kind in ('function_call_output','custom_tool_call_output'):
                self.pending_actions.pop(d.get('call_id'),None)
            elif kind == "message" and d.get("role") == "assistant" and d.get("phase") == "final":
                self.active = False
                self.status, self.stage = "Cavab hazırdır", "Cavab hazırdır"
            elif kind == "message" and d.get("role") == "assistant":
                self.message(d.get("content", []))
        self.updated = time.monotonic()

    def item(self, item):
        if not isinstance(item, dict):
            return
        kind = item.get("type", "").lower()
        if kind in ('commandexecution','filechange','mcptoolcall','extension'):
            from activity import label,append
            identity=item.get('id')
            status=item.get('status')
            failed=status in ('failed','error','cancelled') or item.get('error') is not None or (kind=='commandexecution' and item.get('exit_code') not in (None,0))
            running=status in ('in_progress','running','pending')
            if identity and not running:
                tool=item.get('tool') or item.get('kind') or kind
                self.completed_actions=append(self.completed_actions,identity,label(tool),status='failed' if failed else 'completed')
                self.action_serial+=1
        if kind in ("plan", "planupdate"):
            self.set_plan(item.get("plan", []))
        elif kind == "agentmessage" and item.get("phase") != "final":
            self.message(item.get("content", []))
        elif kind == "usermessage":
            text = " ".join(c.get("text", "") for c in item.get("content", []) if isinstance(c, dict))
            if text and not text.startswith("<") and self.title == "Codex tapşırığı":
                self.title = text[:110]
        elif kind == "agentmessage" and item.get("phase") == "final":
            self.active = False
            self.status, self.stage = "Cavab hazırdır", "Cavab hazırdır"
        elif kind == "commandexecution":
            self.stage = "Əmr icra edir"
        elif kind == "filechange":
            self.stage = "Faylları dəyişir"
        elif kind == "reasoning" and self.active:
            self.stage = "Düşünür"
        elif kind == "extension":
            self.tool(item.get("kind", ""), {})
        elif kind == "mcptoolcall":
            self.tool(item.get("tool", ""), item.get("arguments", {}))

    def set_plan(self, plan):
        if isinstance(plan, list) and all(isinstance(p, dict) for p in plan):
            self.plan = plan
            self.revision+=1;self.plan_serial=self.revision
            current = next((p.get("step", "") for p in plan if p.get("status") == "in_progress"), "")
            if current:
                self.stage = current[:120]

    def tool(self, name, arguments):
        name = name.lower()
        if "update_plan" in name:
            try:
                args = json.loads(arguments) if isinstance(arguments, str) else arguments
                self.set_plan(args.get("plan", []))
            except (ValueError, AttributeError):
                pass
        elif "request_user_input" in name:
            self.stage = "İstifadəçi cavabı gözlənilir"
        elif any(s in name for s in ("search", "web", "fetch", "browse")):
            self.stage = "Məlumat axtarır"
        elif any(s in name for s in ("patch", "edit", "write_file")):
            self.stage = "Faylları dəyişir"
        elif any(s in name for s in ("exec", "command", "stdin")):
            self.stage = "Əmr icra edir"
        else:
            self.stage = "Alətlə işləyir"


class Tail:
    """Incrementally consume complete JSONL lines; retry partial last lines."""
    def __init__(self, path):
        self.path, self.offset, self.state = Path(path), 0, State()

    def poll(self):
        if self.path.stat().st_size < self.offset:
            self.offset, self.state = 0, State()
        with self.path.open("rb") as stream:
            stream.seek(self.offset)
            while True:
                line = stream.readline()
                if not line or not line.endswith(b"\n"):
                    break
                self.offset = stream.tell()
                try:
                    self.state.feed(json.loads(line))
                except (ValueError, TypeError, AttributeError):
                    continue
        return self.state


class Monitor:
    def __init__(self, directory, session=None):
        self.directory, self.session = Path(directory), session
        self.tails = {}
        self.scanned = -10
        self.paths = []
        self.entries = []
        self.names = {}
        from navigation import Navigation
        self.navigation = Navigation()
        self.current_id = None
        self.last_poll = -10
        self.cached = (State(), 0, "")
        from jobs import Jobs
        self.jobs=Jobs()

    def poll(self):
        now = time.monotonic()
        if now-self.last_poll < 0.5:
            return self.cached
        self.last_poll = now
        visible = self.session or self.navigation.poll()
        if now - self.scanned >= 5:
            self.scanned = now
            paths = self.directory.rglob("*.jsonl")
            self.paths = sorted((p for p in paths if not self.session or self.session in p.name),
                                key=lambda p: p.stat().st_mtime, reverse=True)[:12]
            if not self.session:
                # Scientific jobs can outlive the conversation's transcript.
                # Keep explicitly bound sessions discoverable beyond the recent 12.
                try:
                    from jobs import read_json
                    from activation import valid_thread
                    for ref in read_json(self.jobs.config):
                        if valid_thread(ref) and not any(ref in p.name for p in self.paths):
                            bound=next(self.directory.rglob('*'+ref+'.jsonl'),None)
                            if bound:self.paths.append(bound)
                except (OSError,ValueError,TypeError):pass
            self.tails = {p: self.tails.get(p, Tail(p)) for p in self.paths}
            try:
                with (self.directory.parent / "session_index.jsonl").open(encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            self.names[entry["id"]] = entry["thread_name"]
                        except (ValueError, KeyError, TypeError):
                            continue
            except OSError:
                pass
        if visible and not any(visible in p.name for p in self.paths):
            pinned = next(self.directory.rglob("*" + visible + ".jsonl"), None)
            if pinned:
                self.paths.append(pinned)
                self.tails[pinned] = Tail(pinned)
        states = []
        for p in self.paths:
            try:
                state = self.tails[p].poll()
                state.source_path=str(p)
                state.session_ref=p.stem[-36:]
                state.source_modified=p.stat().st_mtime
                state.background=self.jobs.get(p.stem[-36:])
                from progress import attach
                attach(state,state.session_ref)
                state.title = self.names.get(p.stem[-36:], state.title)
                states.append((state, p))
            except OSError:
                continue
        if not states:
            self.entries=[]
            self.cached = (State(), 0, "")
            return self.cached
        active = [(s, p) for s, p in states if s.active]
        self.entries = active + [(s,p) for s,p in states if not s.active]
        pool = active or states
        chosen = next(((s,p) for s,p in states if p.stem[-36:] == visible), None)
        if chosen:
            s,p = chosen
            self.current_id = visible
        elif visible:
            self.current_id = visible
            self.cached = (State(title=self.names.get(visible,"Açıq söhbət"), stage="Bu söhbətin yerli vəziyyət qeydi yoxdur"), len(active), visible)
            return self.cached
        else:
            self.current_id = None
            self.cached = (State(stage="Tətbiqdə bir söhbət açın", title="Açıq söhbət gözlənilir"),len(active),"")
            return self.cached
        self.cached = (s, len(active), p.stem[-36:])
        return self.cached


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions")
    parser.add_argument("--session", help="Pin a session UUID (otherwise follow latest active session)")
    parser.add_argument("--check", action="store_true", help="Print sanitized state without opening UI")
    args = parser.parse_args()
    from providers import MultiMonitor
    monitor = MultiMonitor(args.sessions, args.session)
    if args.check:
        s, count, sid = monitor.poll()
        print(json.dumps(dict(status=s.background["status"] if s.background else s.status, stage=s.current, next=s.next_step, scope=s.progress_scope, percent=s.percent, working=s.working, active=count, session=sid), ensure_ascii=True))
        return
    from island import Island
    from backend import AsyncMonitor
    background=AsyncMonitor(monitor)
    try:Island(background).run()
    finally:background.close()


if __name__ == "__main__":
    main()
