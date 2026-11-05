"""Launch and register an authorized local background command as one operation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import threading
import uuid
from activation import ROOT,write_json
from background_jobs import Store,read,normalize


def launch(owner,spec,root=ROOT):
    command=spec.get('command');cwd=Path(spec.get('cwd',Path.cwd()))
    if not isinstance(command,list) or not command or any(not isinstance(p,str) for p in command):raise ValueError('Use an argument array, never a shell command string')
    if not cwd.is_dir():raise ValueError('Working directory does not exist')
    title=spec.get('title','Background command');run_id=str(uuid.uuid4());folder=Path(root)/'runs'/run_id
    folder.mkdir(parents=True)
    source=folder/'status.json';request=folder/'launch.json'
    job=Store(root).register(owner,title,dict(type='json_file',path=str(source.resolve())),run_id)
    write_json(request,dict(command=command,cwd=str(cwd.resolve()),title=title,run_id=run_id,folder=str(folder.resolve())))
    python=Path(sys.executable)
    if os.name=='nt' and python.with_name('pythonw.exe').exists():python=python.with_name('pythonw.exe')
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
    process=subprocess.Popen([str(python),str(Path(__file__).resolve()),'--supervise',str(request.resolve())],**flags)
    threading.Thread(target=process.wait,daemon=True,name='arizdot-launch-reaper').start()
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        value=read(source)
        if value.get('pid') or value.get('state')=='failed':
            return dict(launched=bool(value.get('pid')),job_id=job['id'],run_id=run_id,pid=value.get('pid'),progress_file=str((folder/'progress.json').resolve()))
        if process.poll() is not None:break
        time.sleep(.05)
    raise ValueError('The supervisor did not acknowledge a real process launch')


def supervise(path):
    spec=read(path);folder=Path(spec['folder']);run_id=spec['run_id'];source=folder/'status.json'
    env=os.environ.copy();env.update(ARIZDOT_STATUS_FILE=str(folder/'progress.json'),ARIZDOT_RUN_ID=run_id)
    try:
        with (folder/'output.log').open('ab') as output:
            flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
            process=subprocess.Popen(spec['command'],cwd=spec['cwd'],env=env,stdout=output,stderr=subprocess.STDOUT,shell=False,**flags)
            while True:
                code=process.poll()
                value=dict(run_id=run_id,updated_at=time.time(),state='running' if code is None else 'completed' if code==0 else 'failed',
                    current=spec['title']+' · process running' if code is None else 'Command execution finished · verify outputs' if code==0 else 'Command execution failed',
                    metrics='Local process '+str(process.pid),pid=process.pid,exit_code=code)
                try:
                    signal=read(folder/'progress.json');normalized=normalize(signal,dict(run_id=run_id))
                    if normalized and time.time()-normalized['source_updated']<=120:
                        for key in ('current','next','steps','completed','total','metrics'):
                            if key in signal:value[key]=signal[key]
                        if code==0 and signal.get('state')=='completed':value['current']=signal.get('current',value['current'])
                    elif signal and code is None:value['current']='Process running · stage update overdue'
                except (OSError,ValueError,TypeError):pass
                write_json(source,value)
                if code is not None:return
                time.sleep(1)
    except (OSError,ValueError,TypeError):
        write_json(source,dict(run_id=run_id,updated_at=time.time(),state='failed',current='Background command could not be launched'))


if __name__=='__main__' and len(sys.argv)==3 and sys.argv[1]=='--supervise':supervise(sys.argv[2])
