"""Independent, read-only remote evidence. No model or browser is required."""
import atexit
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from datetime import datetime
from activation import ROOT,write_json

READERS={}
READERS_LOCK=threading.Lock()


def credentials_present(home=None):
    base=Path(home or Path.home())/'.kaggle'
    config=Path(os.environ.get('KAGGLE_CONFIG_DIR',base))
    return bool(os.environ.get('KAGGLE_API_TOKEN') or (os.environ.get('KAGGLE_USERNAME') and os.environ.get('KAGGLE_KEY')) or
        any(p.is_file() for p in (base/'access_token',base/'credentials.json',config/'kaggle.json')))


def validate(binding):
    kernel=binding.get('kernel','')
    if not isinstance(kernel,str) or not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+(?:/v?[1-9][0-9]*)?',kernel):raise ValueError('Invalid Kaggle kernel reference')
    if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}',binding.get('marker','ARIZDOT_PROGRESS')):raise ValueError('Invalid log marker')
    return kernel


def timestamp(value):
    try:
        stamp=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return stamp.timestamp() if stamp.tzinfo is not None else 0
    except (ValueError,TypeError):return 0


class MarkerReader:
    def __init__(self,binding):
        validate(binding);self.binding=binding;self.buffer=''

    def feed(self,text):
        if not isinstance(text,str):return []
        self.buffer=(self.buffer+text)[-131072:];result=[]
        marker=self.binding.get('marker','ARIZDOT_PROGRESS')
        while marker in self.buffer:
            start=self.buffer.index(marker)+len(marker)
            candidate=self.buffer[start:].lstrip()
            try:value,end=json.JSONDecoder().raw_decode(candidate)
            except ValueError:
                # A partial chunk waits; malformed lines cannot hide later records.
                line_end=candidate.find('\n')
                if line_end<0:break
                self.buffer=candidate[line_end+1:];continue
            self.buffer=candidate[end:]
            if not isinstance(value,dict):continue
            case=value.get('case','')
            expected=self.binding.get('expected_cases',[])
            if expected and case not in expected:continue
            stamp=timestamp(value.get('updated_UTC'))
            if not stamp or stamp>time.time()+60:continue
            allowed=('status','updated_UTC','case','iteration','highest_observed_iteration','last_scf_error_Ry','SCF_target_Ry',
                'qe_process_alive','qe_CPU_seconds','qe_RSS_GB','elapsed_seconds','cutoffs_Ry','log_regression_detected','completed','total','current','next')
            clean={k:value[k] for k in allowed if k in value}
            # Never persist raw logs, tracebacks, commands, credentials or remote PIDs.
            if len(json.dumps(clean))<=8192:result.append(clean)
        return result


def historical(binding):
    try:
        value=json.loads(Path(binding.get('observation_file','')).read_text(encoding='utf-8-sig'))
        return value.get('latest',{})
    except (OSError,ValueError,TypeError):return {}


def snapshot(binding,record,now=None):
    now=time.time() if now is None else now
    data=record.get('telemetry') or historical(binding)
    telemetry_age=max(0,now-timestamp(data.get('updated_UTC'))) if data else None
    check_age=max(0,now-record.get('checked_at',0))
    connected=record.get('connection')=='connected' and check_age<=60
    platform=record.get('platform_status','UNKNOWN')
    terminal=platform in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED') and record.get('connection')=='connected'
    if terminal:connected=True
    fresh=connected and telemetry_age is not None and telemetry_age<=120
    case=data.get('case','');cutoffs=data.get('cutoffs_Ry')
    pair=f'{cutoffs[0]}/{cutoffs[1]} Ry' if isinstance(cutoffs,list) and len(cutoffs)==2 else ''
    iteration=data.get('iteration');metrics=[]
    if type(iteration) is int:metrics.append(f'SCF iteration {iteration}')
    error=data.get('last_scf_error_Ry');target=data.get('SCF_target_Ry')
    if isinstance(error,(int,float)):metrics.append(f'ΔE < {error:.2e} Ry')
    if isinstance(target,(int,float)):metrics.append(f'target {target:.0e} Ry')
    if isinstance(data.get('qe_CPU_seconds'),(int,float)):metrics.append(f"CPU {data['qe_CPU_seconds']:.0f} s")
    if isinstance(data.get('qe_RSS_GB'),(int,float)):metrics.append(f"RAM {data['qe_RSS_GB']:.1f} GB")
    if data and not fresh:metrics.insert(0,f'Last calculation report {int(telemetry_age or 0)} s ago')
    phase='remote_running';percent=None;steps=[]
    for label in binding.get('verified_completed',[]):steps.append(dict(step=str(label)[:300],status='completed'))
    if connected:
        health=f'Kaggle API checked {int(check_age)} s ago'
        if platform in ('ERROR','CANCEL_REQUESTED','CANCEL_ACKNOWLEDGED'):
            current='Kaggle notebook failed or stopped';phase='needs_review'
        elif platform=='COMPLETE':
            current='Kaggle notebook execution ended · result audit required';phase='remote_finished'
        elif fresh:
            current=str(data.get('current') or ('Density cutoff · '+pair if pair else data.get('status','Kaggle calculation')))
        else:current='Kaggle notebook '+platform.lower()+' · waiting for calculation update'
    else:
        current='Kaggle connection required' if record.get('connection')=='auth_required' else 'Kaggle connection unavailable'
        health='Connect Kaggle once to read this private run' if record.get('connection')=='auth_required' else 'No current Kaggle API response'
        phase='remote_disconnected'
    if fresh and type(data.get('completed')) is int and type(data.get('total')) is int and 0<=data['completed']<=data['total'] and data['total']>0:
        percent=round(100*data['completed']/data['total'])
        scope=f"{data['completed']}/{data['total']} reported work units"
    else:scope='SCF convergence · no fixed iteration total' if data else 'Remote progress not received'
    nxt=str(data.get('next') or binding.get('next_target','')) if fresh else ''
    if phase=='remote_finished':nxt='Audit and import the saved outputs'
    return dict(title=binding.get('material','Calculation')+' · Kaggle',current=current,metrics=' · '.join(metrics),health=health,
        next=nxt,percent=percent,active=connected and platform in ('RUNNING','QUEUED'),status=current,scope=scope,
        badge='RUN' if connected and platform=='RUNNING' else 'REVIEW' if phase=='needs_review' else 'CONNECT' if not connected else 'DONE',
        tone='green' if fresh else 'amber',source='Kaggle API',case=case,phase=phase,
        snapshot_status='recorded' if terminal else 'live' if connected else 'offline',remote=True,telemetry_fresh=fresh,steps=steps,
        output_age_seconds=telemetry_age,controller_updated_seconds=check_age,platform_status=platform)


class Reader:
    def __init__(self,binding,root=ROOT):
        self.binding=dict(binding);validate(binding)
        self.key=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()[:24]
        self.path=Path(root)/'remote'/('kaggle-'+self.key+'.json')
        self.record={};self.process=None;self.checked=-100;self.lock=threading.Lock()
        try:self.record=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass

    def get(self):
        with self.lock:
            now=time.monotonic()
            terminal=self.record.get('platform_status') in ('COMPLETE','ERROR','CANCEL_ACKNOWLEDGED') and self.record.get('connection')=='connected'
            if not terminal and now-self.checked>30 and (self.process is None or self.process.poll() is not None):
                self.checked=now
                if not credentials_present():self.record['connection']='auth_required'
                else:
                    config=dict(self.binding)
                    if self.record.get('resolved_ref'):config['kernel']=self.record['resolved_ref']
                    python=Path(sys.executable)
                    if python.name.lower()=='pythonw.exe':python=python.with_name('python.exe')
                    kwargs={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
                    self.process=subprocess.Popen([str(python),str(Path(__file__).with_name('kaggle_worker.py'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',**kwargs)
                    self.process.stdin.write(json.dumps(config));self.process.stdin.close()
                    threading.Thread(target=self.consume,args=(self.process,),daemon=True,name='arizdot-kaggle').start()
            return snapshot(self.binding,dict(self.record))

    def consume(self,process):
        for line in process.stdout:
            if len(line)>20000:continue
            try:value=json.loads(line)
            except ValueError:continue
            if not isinstance(value,dict):continue
            with self.lock:
                self.record.update(value)
                try:write_json(self.path,self.record)
                except OSError:pass

    def close(self):
        if self.process is not None and self.process.poll() is None:
            # Windows venv launchers can have a second Python child. This tree
            # contains only our read-only monitor, never a calculation worker.
            if os.name=='nt':
                try:subprocess.run(['taskkill','/PID',str(self.process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
                except (OSError,subprocess.TimeoutExpired):self.process.terminate()
            else:self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:pass


def get(binding):
    validate(binding);key=json.dumps(binding,sort_keys=True)
    with READERS_LOCK:
        if key not in READERS:READERS[key]=Reader(binding)
        reader=READERS[key]
    return reader.get()


@atexit.register
def close():
    for reader in list(READERS.values()):reader.close()
