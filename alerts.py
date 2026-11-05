"""Transition notifications with restart-safe deduplication."""
import json
import time
from dataclasses import dataclass
from pathlib import Path

PATH=Path(__file__).resolve().parent/'config/notifications.json'


@dataclass
class Alert:
    thread:str
    kind:str
    title:str
    body:str


class AlertPolicy:
    def __init__(self,path=PATH,wait_seconds=600):
        self.path=Path(path)
        try:self.saved=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):self.saved={}
        self.enabled=self.saved.get('enabled',True)
        self.seen=set(self.saved.get('seen',[]))
        self.waiting=self.saved.get('waiting',{})
        self.previous={}
        self.faults={}
        self.wait_seconds=wait_seconds

    def save(self):
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            self.path.write_text(json.dumps(dict(enabled=self.enabled,seen=sorted(self.seen)[-200:],waiting=self.waiting),ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError:pass

    def enable(self,enabled):
        self.enabled=bool(enabled)
        self.save()

    def emit(self,thread,job,kind,key,body):
        token=thread+'|'+key
        if token in self.seen:return None
        self.seen.add(token)
        self.save()
        if not self.enabled:return None
        return Alert(thread,kind,job.get('title','arizdot'),body)

    def observe(self,thread,job,now=None):
        if not thread or not job:return []
        now=time.time() if now is None else now
        old=self.previous.get(thread)
        self.previous[thread]=dict(job)
        case=job.get('case','')
        phase=job.get('phase','')
        events=[]
        def add(kind,key,body):
            event=self.emit(thread,job,kind,key,body)
            if event:events.append(event)
        # First observation is a baseline, never a completion notification.
        if old:
            if phase=='completed' and old.get('phase')!='completed':
                add('complete',case+'|pipeline-complete','Cavab hazırdır' if job.get('kind')=='chat' else 'Validasiya zənciri tamamlandı')
            elif job.get('badge')=='CHECK' and old.get('badge')!='CHECK':
                add('complete',case+'|case-complete','Cari hesab tamamlandı · nəticə auditi gözlənilir')
            elif case!=old.get('case') and job.get('finished_count',0)>old.get('finished_count',0):
                add('complete',old.get('case','')+'|case-complete','Əvvəlki hesab tamamlandı · növbəti addıma keçildi')
        waiting=phase in ('waiting_memory','waiting_for_upstream','waiting') and job.get('snapshot_status')!='offline'
        saved=self.waiting.get(thread)
        if waiting:
            if not saved or saved.get('case')!=case or saved.get('phase')!=phase:
                saved=dict(case=case,phase=phase,since=now)
                self.waiting[thread]=saved;self.save()
            if now-saved['since']>=self.wait_seconds:
                add('waiting',case+'|'+phase+'|'+str(saved['since']),'Gözləmə uzanır · '+job.get('health',''))
        elif saved:
            del self.waiting[thread];self.save()
        fault=(phase=='needs_review' or job.get('snapshot_status') in ('offline','stale'))
        if fault:
            code=case+'|'+phase+'|'+job.get('snapshot_status','review')
            previous=self.faults.get(thread)
            if not previous or previous[0]!=code:self.faults[thread]=(code,now)
            elif now-previous[1]>=10:
                add('attention',code,'Diqqət tələb olunur · '+job.get('health',job.get('current','')))
        else:self.faults.pop(thread,None)
        return events
