"""Provider-independent background jobs; their lifetime is not a chat turn."""
import copy
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from activation import ROOT,split_ref,valid_ref,write_json
from claude_support import locked

TERMINAL={'completed','failed','cancelled'}
STATES={'queued','running','waiting','completed','failed','cancelled','unknown'}


def read(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8-sig'))
        return value if isinstance(value,dict) else {}
    except FileNotFoundError:return {}


def validate_source(source):
    if not isinstance(source,dict):raise ValueError('A concrete status source is required')
    kind=source.get('type')
    if kind in ('json_file','process'):
        if kind=='json_file' and not Path(source.get('path','')).is_absolute():raise ValueError('Status file must have an absolute path')
        if kind=='process' and (type(source.get('pid')) is not int or source['pid']<=0):raise ValueError('Provide an actual local process ID')
    elif kind=='http_json':
        url=urlsplit(source.get('url',''))
        if url.username or url.password or url.fragment or not url.hostname:raise ValueError('Invalid status URL; keep credentials out of URLs')
        if url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('127.0.0.1','localhost','::1')):raise ValueError('Remote status endpoints require HTTPS')
        if source.get('token_env') and not re.fullmatch(r'[A-Z_][A-Z0-9_]*',source['token_env']):raise ValueError('Use an environment variable name for endpoint authentication')
    elif kind=='kaggle':
        from kaggle_remote import validate
        validate(source)
    elif kind!='reported':raise ValueError('Supported sources: json_file, http_json, process, kaggle, reported')
    return copy.deepcopy(source)


def process_identity(pid):
    """Capture creation identity so a recycled local PID is not adopted."""
    if os.name!='nt':
        try:return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
        except (OSError,IndexError):return None
    import ctypes
    from ctypes import wintypes as W
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.GetProcessTimes.argtypes=[W.HANDLE]+[ctypes.POINTER(W.FILETIME)]*4
    k.CloseHandle.argtypes=[W.HANDLE]
    handle=k.OpenProcess(0x1000,False,pid)
    if not handle:return None
    try:
        values=[W.FILETIME() for _ in range(4)]
        if k.GetProcessTimes(handle,*[ctypes.byref(v) for v in values]):return str(values[0].dwHighDateTime<<32|values[0].dwLowDateTime)
    finally:k.CloseHandle(handle)
    return None


class Store:
    def __init__(self,root=ROOT):self.root=Path(root);self.path=self.root/'background-jobs.json'

    def register(self,owner,title,source,run_id=None):
        if not valid_ref(owner):raise ValueError('A real owning Codex or Claude conversation is required')
        if not isinstance(title,str) or not title.strip() or len(title)>300:raise ValueError('Provide a short job title')
        source=validate_source(source)
        if source['type']=='process':
            source['creation_id']=process_identity(source['pid'])
            if not source['creation_id']:raise ValueError('The local process could not be identified')
        if run_id is not None and (not isinstance(run_id,str) or not run_id or len(run_id)>200):raise ValueError('Invalid run ID')
        with locked(self.path):
            data=read(self.path)
            # Idempotent repeated registration must not duplicate a running job.
            for job in data.values():
                if job['owner']==owner and job['source']==source and job.get('run_id')==run_id and not job.get('dismissed'):return job
            identity=str(uuid.uuid4());now=time.time()
            job=dict(id=identity,owner=owner,title=title.strip(),source=source,run_id=run_id,created=now,dismissed=False)
            data[identity]=job;write_json(self.path,data)
        return job

    def update(self,identity,value,owner):
        if not isinstance(value,dict):raise ValueError('Expected a status object')
        with locked(self.path):
            jobs=read(self.path);job=jobs.get(identity)
            if not job or job['owner']!=owner:raise ValueError('Job does not belong to this conversation')
            if job['source']['type']!='reported':raise ValueError('Observed jobs update from their source, not model reports')
            value=dict(value,updated_at=time.time())
            value.setdefault('run_id',job.get('run_id'))
            normalized=normalize(value,job)
            if not normalized:raise ValueError('Invalid or mismatched job status')
            job['report']=dict(value,updated_at=time.time());write_json(self.path,jobs)
        return job

    def dismiss(self,identity,owner):
        with locked(self.path):
            jobs=read(self.path);job=jobs.get(identity)
            if not job or job['owner']!=owner:raise ValueError('Job does not belong to this conversation')
            job['dismissed']=True;write_json(self.path,jobs)
        return dict(dismissed=True,job_id=identity,execution_changed=False)

    def list(self,owner=None):return [j for j in read(self.path).values() if not j.get('dismissed') and (owner is None or j['owner']==owner)]


def normalize(value,job):
    from kaggle_remote import timestamp
    if not isinstance(value,dict):return None
    if job.get('run_id') and value.get('run_id')!=job['run_id']:return None
    stamp=value.get('updated_at',value.get('updated_UTC',0))
    stamp=stamp if type(stamp) in (int,float) else timestamp(stamp)
    if not stamp or stamp>time.time()+60:return None
    phase=value.get('state',value.get('status','unknown'))
    phase={'working':'running','computing':'running','error':'failed','needs_review':'failed','done':'completed'}.get(phase,phase)
    if phase not in STATES:return None
    steps=value.get('steps',[])
    if not isinstance(steps,list) or len(steps)>200:return None
    if any(not isinstance(p,dict) or not isinstance(p.get('step'),str) or p.get('status') not in ('pending','in_progress','completed') for p in steps):return None
    plan=[dict(step=p['step'][:300],status=p['status']) for p in steps]
    percent=None;scope='Progress units not reported'
    if plan:
        done=sum(p['status']=='completed' for p in plan);percent=round(100*done/len(plan));scope=f'{done}/{len(plan)} work steps'
    else:
        done=value.get('completed');total=value.get('total')
        if type(done) is int and type(total) is int and total>0 and 0<=done<=total:
            percent=round(100*done/total);scope=f'{done}/{total} work units'
    return dict(current=str(value.get('current',''))[:1000] or next((p['step'] for p in plan if p['status']=='in_progress'),'Work '+phase),
        next=str(value.get('next',''))[:1000] or next((p['step'] for p in plan if p['status']=='pending'),''),
        phase=phase,percent=percent,scope=scope,steps=plan,metrics=str(value.get('metrics',''))[:1000],source_updated=stamp)


class SameOriginRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        if urlsplit(request.full_url)[:2]!=urlsplit(newurl)[:2]:raise ValueError('Cross-origin status redirect rejected')
        return super().redirect_request(request,fp,code,msg,headers,newurl)


def observe(job):
    source=job['source'];kind=source['type']
    if kind=='json_file':
        with Path(source['path']).open('rb') as stream:body=stream.read(1048577)
        if len(body)>1048576:raise ValueError('Status file is too large')
        value=json.loads(body.decode('utf-8-sig'))
    elif kind=='http_json':
        headers={'Accept':'application/json'}
        if source.get('token_env'):
            token=os.environ.get(source['token_env'])
            if not token:raise ValueError('Endpoint authentication is unavailable')
            headers['Authorization']='Bearer '+token
        with build_opener(SameOriginRedirect()).open(Request(source['url'],headers=headers),timeout=5) as response:body=response.read(1048577)
        if len(body)>1048576:raise ValueError('Status response is too large')
        value=json.loads(body)
    elif kind=='reported':value=job.get('report',{})
    elif kind=='process':
        from jobs import alive,process_metrics
        same=process_identity(source['pid'])==source['creation_id']
        running=alive(source['pid']) if same else False
        # Exit without a captured exit result is never evidence of success.
        value=dict(run_id=job.get('run_id'),updated_at=time.time(),state='running' if running is True else 'unknown',
            current='Local process running' if running is True else 'Process ended · result verification required',
            metrics=json.dumps(process_metrics(source['pid'])) if running is True else '')
    else:return None
    result=normalize(value,job)
    if result is None:raise ValueError('Source status is missing or belongs to another run')
    result['checked_at']=time.time();return result


def state_for(job,evidence=None,error=None):
    from pulse import State
    source=job['source'];reported=source['type']=='reported';now=time.time()
    evidence=evidence or {};phase=evidence.get('phase','unknown')
    age=max(0,now-evidence.get('source_updated',0));check_age=max(0,now-evidence.get('checked_at',0))
    terminal=phase in TERMINAL
    fresh=not error and (terminal or age<=120) and check_age<=45
    data=dict(title=job['title'],current=evidence.get('current','Waiting for job status') if fresh else 'Waiting for a current job status update',
        next=evidence.get('next','') if fresh else '',metrics=evidence.get('metrics','') if fresh else '',
        percent=evidence.get('percent') if fresh else None,scope=evidence.get('scope','Progress units not reported'),
        active=fresh and phase in ('running','queued'),phase=phase,status=phase,
        health=('Reported job status' if reported else 'Job status source observed')+f' · {int(age)} s ago' if evidence else 'Job status source is not connected',
        snapshot_status=('recorded' if reported or terminal else 'live') if fresh else 'offline' if error else 'stale',
        tone='red' if phase=='failed' else 'green' if fresh else 'amber',steps=evidence.get('steps',[]),badge='DONE' if terminal else 'RUN' if fresh else 'CHECK',
        kind='background_job',reported=reported,background_job=True,owner_ref=job['owner'],job_visible=True,source_type=source['type'])
    return State(title=job['title'],background=data,source_modified=evidence.get('source_updated',job['created']),session_ref='job:'+job['id'])


class Monitor:
    def __init__(self,root=ROOT,start=True):
        self.store=Store(root);self.cache={};self.stop=threading.Event();self.lock=threading.Lock()
        self.worker=threading.Thread(target=self.run,daemon=True,name='arizdot-background-jobs')
        if start:self.worker.start()

    def refresh(self):
        jobs=[j for j in self.store.list() if j['source']['type']!='kaggle']
        if not jobs:return
        with ThreadPoolExecutor(max_workers=4,thread_name_prefix='arizdot-job-source') as pool:
            pending={pool.submit(observe,job):job for job in jobs}
            for future in as_completed(pending):
                job=pending[future]
                try:value=future.result();error=None
                except (OSError,ValueError,TypeError):value=None;error='source_unavailable'
                with self.lock:
                    prior=self.cache.get(job['id'],(None,None))[0]
                    self.cache[job['id']]=(value or prior,error)

    def run(self):
        while not self.stop.is_set():
            try:self.refresh()
            except (OSError,ValueError,TypeError):pass
            self.stop.wait(5)

    def collect(self):
        from pulse import State
        entries=[]
        for job in self.store.list():
            if job['source']['type']=='kaggle':
                from kaggle_remote import get
                data=get(job['source']);data.update(background_job=True,owner_ref=job['owner'],job_visible=True,kind='background_job')
                state=State(title=job['title'],background=data,session_ref='job:'+job['id'],source_modified=time.time())
            else:
                with self.lock:evidence,error=copy.deepcopy(self.cache.get(job['id'],(None,None)))
                state=state_for(job,evidence,error)
            entries.append((state,self.store.path))
        return entries


_MONITORS={}
_LOCK=threading.Lock()


def collect(root=ROOT):
    root=Path(root)
    if not Store(root).list():return []
    with _LOCK:
        key=str(root.resolve())
        if key not in _MONITORS:_MONITORS[key]=Monitor(root)
        monitor=_MONITORS[key]
    return monitor.collect()
