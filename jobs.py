"""Read-only background-job adapters; private bindings live in config/."""
import ctypes
import json
import os
import re
import time
from pathlib import Path

CONFIG = Path(__file__).resolve().parent/"config/sources.json"
LABELS = {"strict_SCF_audit":"SCF auditi", "I/O_validation":"Giriş-çıxış yoxlaması",
          "wave_cutoff":"Dalğa cutoff-u", "density_cutoff":"Sıxlıq cutoff-u",
          "paired_cutoff":"Cüt cutoff yoxlaması", "k_mesh":"K-şəbəkə yoxlaması",
          "softmode_direction":"Yumşaq mod istiqaməti"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def alive(pid):
    if not isinstance(pid,int) or pid<=0 or os.name!="nt":
        return None
    api=ctypes.WinDLL("kernel32",use_last_error=True)
    api.OpenProcess.restype=ctypes.c_void_p
    api.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
    api.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    api.CloseHandle.argtypes=[ctypes.c_void_p]
    h=api.OpenProcess(0x1000,False,pid)
    if not h:
        return False if ctypes.get_last_error()==87 else None
    code=ctypes.c_ulong()
    try:
        return code.value==259 if api.GetExitCodeProcess(h,ctypes.byref(code)) else None
    finally:
        api.CloseHandle(h)


def process_metrics(pid):
    """Read CPU time and working set without sending signals to the worker."""
    if not isinstance(pid,int) or os.name!='nt':return {}
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    from ctypes import wintypes as W
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.GetProcessTimes.argtypes=[W.HANDLE]+[ctypes.POINTER(W.FILETIME)]*4
    k.CloseHandle.argtypes=[W.HANDLE]
    handle=k.OpenProcess(0x1000,False,pid)
    if not handle:return {}
    result={}
    try:
        created,exited,kernel,user=(W.FILETIME() for _ in range(4))
        if k.GetProcessTimes(handle,*[ctypes.byref(v) for v in (created,exited,kernel,user)]):
            result['cpu_seconds']=sum((v.dwHighDateTime<<32)|v.dwLowDateTime for v in (kernel,user))/1e7
        class Memory(ctypes.Structure):
            _fields_=[('cb',W.DWORD),('faults',W.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak_working','working','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]
        memory=Memory();memory.cb=ctypes.sizeof(memory)
        api=ctypes.WinDLL('psapi')
        api.GetProcessMemoryInfo.argtypes=[W.HANDLE,ctypes.POINTER(Memory),W.DWORD]
        if api.GetProcessMemoryInfo(handle,ctypes.byref(memory),memory.cb):result['ram_gb']=memory.working/1e9
    finally:k.CloseHandle(handle)
    return result


def tail_text(path,limit=131072):
    path=Path(path)
    with path.open('rb') as f:
        f.seek(max(0,path.stat().st_size-limit))
        return f.read().decode('utf-8',errors='replace')


def qe_snapshot(root,material='Crystal'):
    root=Path(root)
    status=read_json(root/'status.json')
    plan=read_json(root/'plan.json')
    stages=plan.get('stages',[])
    latest=None
    results={}
    with (root/'events.jsonl').open(encoding='utf-8') as f:
        for line in f:
            try:
                item=json.loads(line)
                if item.get('stage') in stages:latest=item['stage']
                if item.get('stage')=='wave_cutoff_result':results[item.get('W')]=item
            except ValueError:continue
    stage=status.get('stage') if status.get('stage') in stages else latest
    case=status.get('case') or status.get('pending_case','')
    if case and not re.fullmatch(r'[A-Za-z0-9_-]+',case):raise ValueError('Invalid case folder')
    seed=case.split('_w')[0] if '_w' in case else ''
    structure={'old':'MP old seed','reference':'MP reference seed','soft_parent':'Soft-mode parent','soft_minus':'Soft-mode − displacement','soft_plus':'Soft-mode + displacement'}.get(seed,seed or 'Structure unspecified')
    title=material+' · '+structure
    current=LABELS.get(stage,stage or 'Hesablama')
    w=re.search(r'_w(\d+)',case)
    rho=re.search(r'_r(\d+)',case)
    grid=re.search(r'_k(\d)(\d)(\d)',case)
    if w:current+=' · '+w[1]+' Ry'
    if rho:current+=' · ρ '+rho[1]+' Ry'
    if grid:current+=' · k '+'×'.join(grid.groups())
    kind=status.get('status','')
    computing=kind=='computing'
    waiting=kind in ('waiting_memory','waiting_for_upstream')
    terminal=kind=='completed'
    pid=status.get('qe_pid') if computing else status.get('controller_pid')
    running=alive(pid)
    output=root/case/'scf.out' if case else None
    text='';age=None
    if output and output.exists():
        text=tail_text(output)
        age=max(0,time.time()-output.stat().st_mtime)
    iterations=re.findall(r'iteration\s*#\s*(\d+)',text)
    residuals=re.findall(r'estimated scf accuracy\s*<\s*([\d.EeDd+-]+)',text)
    iteration=int(iterations[-1]) if iterations else None
    accuracy=float(residuals[-1].replace('D','E').replace('d','e')) if residuals else None
    target=plan.get('SCF_Ry')
    if case:
        try:target=read_json(root/case/'manifest.json').get('conv_thr_Ry',target)
        except (OSError,ValueError):pass
    completed_output='JOB DONE.' in text
    metrics=''
    if computing:
        metrics=('SCF '+str(iteration)) if iteration else 'SCF başlanır'
        if accuracy is not None:metrics+=f' · ΔE < {accuracy:.2e} Ry'
        if isinstance(target,(int,float)):metrics+=f' → {target:.0e} Ry'
    badge='RUN' if computing else 'WAIT' if waiting else 'REVIEW'
    tone='green' if computing else 'amber'
    health='Proses yoxlanılır'
    label='Hesablanır' if computing else 'Yoxlama tələb olunur'
    nxt='Sonra: cari nəticənin auditi'
    if kind=='waiting_memory':
        needed=status.get('required_free_RAM_GB')
        available=status.get('available_RAM_GB')
        metrics=f'RAM: {available:.2f} / {needed:.2f} GB' if isinstance(needed,(int,float)) and isinstance(available,(int,float)) else 'RAM məlumatı gözlənilir'
        health='RAM gözləyir · QE işləmir'
        label='RAM gözləyir'
        nxt='Sonra: yaddaş ayrıldıqda SCF başlayacaq'
    elif kind=='waiting_for_upstream':
        health='Əvvəlki hesabın bitməsini gözləyir'
        label='Növbə gözləyir'
    elif computing:
        health='Proses işləyir'
        if completed_output:
            badge='CHECK';health='Hesab bitdi · nəticə auditi gözlənilir'
        if running is False:
            badge='STOP';tone='red';health='Proses tapılmadı · son jurnal göstərilir';label='Proses tapılmadı'
    elif kind=='needs_review':health='Yoxlama tələb olunur · hesab dayandırılıb'
    elif kind=='stopped_by_user':badge='STOP';health='İstifadəçi dayandırıb'
    if waiting and running is False:
        badge='STOP';tone='red';health='İdarəedici proses tapılmadı';label='Proses tapılmadı'
    if terminal:
        badge='DONE';tone='green';health='Validasiya zənciri tamamlandı';label='Hesablama zənciri bitdi'
        nxt='Sonra: nəticələrin qiymətləndirilməsi'
    # Percent is bounded to an explicitly named, countable batch, not SCF time.
    limits=plan.get('wave_cutoff_limits_Ry',[]) if stage=='wave_cutoff' else []
    finished=sum(value in results for value in limits)
    pct=round(100*finished/len(limits)) if limits else None
    scope=f'{finished}/{len(limits)} cutoff hesabı hazır' if limits else 'Cari hesabın faizi ölçülmür'
    if stage=='wave_cutoff' and results:
        last=max(k for k in results if isinstance(k,(int,float)))
        passed=results[last].get('comparison',{}).get('passed')
        if passed is not None:scope+=f' · {last} Ry '+('keçdi' if passed else 'keçmədi')
    if terminal:pct=100;scope='Validasiya zənciri tamamlandı'
    activity=process_metrics(pid) if computing and running is not False else {}
    steps=[dict(step=LABELS.get(stage,stage)+f' · {value} Ry',status='completed' if value in results else 'in_progress' if w and int(w[1])==value and computing else 'pending') for value in limits]
    return dict(percent=pct,current=current,next=nxt,active=computing and running is not False and not completed_output,
        status=label,scope=scope,title=title,badge=badge,tone=tone,metrics=metrics,health=health,
        iteration=iteration,accuracy_Ry=accuracy,target_Ry=target,output_age_seconds=age,
        controller_updated_seconds=max(0,time.time()-(root/'status.json').stat().st_mtime),pid=pid,
        process=activity,case=case,phase=kind,finished_count=finished,total_count=len(limits),source=str(root/'status.json'),steps=steps)


class Jobs:
    def __init__(self,config=CONFIG):
        self.config=Path(config)
        self.cache={}
        self.last={}
        self.telemetry={}

    def get(self,thread):
        now=time.monotonic()
        if now-self.last.get(thread,-10)<2:
            return self.cache.get(thread)
        self.last[thread]=now
        try:
            binding=read_json(self.config).get(thread)
            if binding and binding.get('enabled') is False:self.cache[thread]=None;return None
            value=None
            if binding and binding.get('adapter')=='qe':
                cloud=False
                if binding.get('project_state') and binding.get('cloud_observation'):
                    project=read_json(binding['project_state'])
                    cloud=str(project.get('status','')).lower().startswith(('colab','cloud'))
                if cloud:
                    from observations import cloud_snapshot
                    value=cloud_snapshot(binding['cloud_observation'],binding.get('material','Crystal'))
                else:value=qe_snapshot(binding['root'],binding.get('material','Crystal'))
            if value:
                rate=None
                now=time.monotonic()
                cpu=value.get('process',{}).get('cpu_seconds')
                pid=value.get('pid')
                previous=self.telemetry.get(thread)
                if cpu is not None:
                    if previous and previous[0]==pid and now>previous[2]:
                        rate=max(0,(cpu-previous[1])/(now-previous[2]))
                        if value['phase']=='computing' and value['badge']=='RUN':
                            value['health']=('CPU aktiv' if rate>.01 else 'CPU dəyişmir')+f' · {rate:.2f} CPU-s/s'
                    self.telemetry[thread]=(pid,cpu,now)
                age=value.get('output_age_seconds')
                if value['phase']=='computing' and age is not None:
                    value['health']+=f' · jurnal {int(age)} s əvvəl'
                if value['phase']=='waiting_memory':
                    value['health']+=f" · qeyd {int(value['controller_updated_seconds'])} s əvvəl"
                from health import classify
                if not value.get('observation'):value['snapshot_status']=classify(value,rate)
                value['sample_time']=time.monotonic()
            self.cache[thread]=value
        except (OSError,ValueError,KeyError,TypeError):
            # Never fall back to "100% done" when a bound live source is unreadable.
            try:bound=thread in read_json(self.config)
            except (OSError,ValueError):bound=False
            self.cache[thread]=dict(percent=None,current="İşin canlı vəziyyəti oxuna bilmir",next="",active=False,status="Məlumat yoxdur",scope="Son cavab işin tamamlanması deyil",source_error=True,snapshot_status='offline',phase='source_error',badge='OFFLINE',tone='red',health='Məlumat mənbəyi oxuna bilmir') if bound else None
        return self.cache.get(thread)
