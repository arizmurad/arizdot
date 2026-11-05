"""Route explicit activation to Codex or Claude without mixing session IDs."""
import json
import time
from datetime import datetime,timezone
from pathlib import Path
from activation import ROOT,split_ref,valid_ref
from claude_support import snapshot_state


class ProviderNavigation:
    def __init__(self,codex,pinned=None):
        self.codex=codex
        self.selected=pinned
        self.pinned=pinned is not None
        self.activated=''
        if not pinned:
            try:
                ack=json.loads((ROOT/'activation-ack.json').read_text(encoding='utf-8'))
                ref=ack.get('thread_id')
                if valid_ref(ref) and ':' in ref:
                    self.selected=ref
                    self.activated=datetime.fromtimestamp(ack['acknowledged'],timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
            except (OSError,ValueError,KeyError,TypeError):pass

    def activate(self,reference):
        provider,session=split_ref(reference)
        self.pinned=False
        if provider=='codex':
            self.selected=None
            self.codex.navigation.activate(session)
        else:
            self.selected=reference
            self.activated=datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
        self.codex.last_poll=-10

    def poll(self):
        self.codex.navigation.poll()
        if self.selected and not self.pinned and self.codex.navigation.stamp>self.activated:self.selected=None
        return self.selected


class MultiMonitor:
    def __init__(self,directory,session=None):
        from pulse import Monitor
        provider,raw=split_ref(session) if session else ('codex',None)
        self.codex=Monitor(directory,raw if provider=='codex' else None)
        self.directory=directory
        self.overview=None
        self.navigation=ProviderNavigation(self.codex,session if provider!='codex' else None)
        self.entries=[]
        self.last_poll=-10
        self.cached=None

    def collect_tasks(self):
        """Read concurrent tasks without changing the explicitly selected chat."""
        if self.overview is None:
            from pulse import Monitor
            self.overview=Monitor(self.directory)
        self.overview.poll()
        entries=list(self.overview.entries)
        for provider in ('claude','claude-desktop'):
            folder=ROOT/'providers'/provider
            paths=sorted(folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:32]
            for path in paths:
                if not valid_ref(provider+':'+path.stem):continue
                try:
                    state=snapshot_state(path.stem,provider)
                    bound=self.overview.jobs.get(state.session_ref)
                    if bound:state.background=bound
                    entries.append((state,path))
                except (OSError,ValueError,TypeError):continue
        from background_jobs import collect
        entries.extend(collect(ROOT))
        return entries

    def poll(self):
        now=time.monotonic()
        if now-self.last_poll<.5 and self.cached is not None:return self.cached
        self.last_poll=now
        try:selected=self.navigation.poll()
        except OSError:selected=self.navigation.selected
        if not selected:
            codex=self.codex.poll()
            self.entries=list(self.codex.entries)
            self.cached=codex
            return codex
        # A large or unavailable Codex transcript must not block a Claude
        # activation. Providers read only their selected source here.
        self.entries=[]
        provider,session=split_ref(selected)
        try:state=snapshot_state(session,provider)
        except (OSError,ValueError,TypeError):
            from pulse import State
            state=State(title='Claude',stage='Claude status mənbəyi oxuna bilmir',session_ref=selected,
                background=dict(title='Claude',current='Claude status mənbəyi oxuna bilmir',next='',scope='Faiz ölçülmür',percent=None,active=False,snapshot_status='offline',phase='source_error',health='Məlumat yoxdur',tone='red'))
        bound=self.codex.jobs.get(selected)
        if bound:state.background=bound
        self.entries.append((state,Path(state.source_path or session+'.json')))
        self.cached=(state,int(state.working),selected)
        return self.cached
