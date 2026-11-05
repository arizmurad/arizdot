"""Local command interface for the arizdot skill."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def running():
    if os.name!='nt':return False
    api=ctypes.WinDLL('user32')
    api.FindWindowW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p]
    api.FindWindowW.restype=ctypes.c_void_p
    return bool(api.FindWindowW(None,'arizdot'))


def start(session=None,provider=None,cwd=None):
    from activation import request,acknowledged
    from activation import caller_thread,split_ref
    reference=caller_thread(session,provider)
    if reference:
        kind,raw=split_ref(reference)
        if kind=='claude':
            from claude_support import register
            register(raw,cwd)
    value=request(reference)
    existed=running()
    if not existed:
        interpreter=Path(sys.executable).with_name('pythonw.exe')
        if not interpreter.exists():interpreter=Path(sys.executable)
        subprocess.Popen([str(interpreter),str(Path(__file__).with_name('arizdot.py'))],creationflags=subprocess.CREATE_NO_WINDOW)
    deadline=time.monotonic()+6
    while time.monotonic()<deadline:
        ack=acknowledged(value)
        if ack and running():return dict(running=True,already_running=existed,activated=True,thread_id=ack.get('thread_id'))
        time.sleep(.1)
    return dict(running=running(),already_running=existed,activated=False,start_requested=True,error='The UI did not confirm activation. Restart or inspect arizdot; do not report it as activated.')


def status(session=None,provider=None):
    from providers import MultiMonitor
    from activation import caller_thread
    directory=Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'sessions'
    reference=caller_thread(session,provider) if session is not None or provider is not None else None
    state,count,thread=MultiMonitor(directory,reference).poll()
    return dict(running=running(),thread_id=thread,title=state.live_title,
                status=state.background.get('status',state.status) if state.background else state.status,
                freshness=state.freshness,current=state.current,metrics=state.live_metrics,
                health=state.live_health,next_step=state.next_step,
                percent=state.percent,progress_scope=state.progress_scope,working=state.working,
                recent_active_chats=count)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('start','status','report','run','job-register','job-update','job-list','job-dismiss'))
    parser.add_argument('--job-file',type=Path,help='UTF-8 job registration or status JSON')
    parser.add_argument('--job-id',help='Registered background job UUID')
    parser.add_argument('--steps-file',type=Path,help='UTF-8 JSON with named steps and statuses')
    parser.add_argument('--session',help='Explicit session UUID or namespaced reference')
    parser.add_argument('--provider',choices=('codex','claude','claude-desktop'))
    parser.add_argument('--cwd',help='Claude Code project directory')
    args=parser.parse_args()
    try:
        if args.action=='run':
            from activation import caller_thread
            from background_launch import launch
            owner=caller_thread(args.session,args.provider)
            if not owner or not args.job_file:raise ValueError('A conversation and --job-file launch specification are required')
            result=launch(owner,json.loads(args.job_file.read_text(encoding='utf-8-sig')))
        elif args.action.startswith('job-'):
            from activation import caller_thread
            from background_jobs import Store
            owner=caller_thread(args.session,args.provider)
            if not owner:raise ValueError('The owning conversation is required')
            store=Store()
            if args.action=='job-list':result=dict(jobs=store.list(owner))
            elif args.action=='job-dismiss':result=store.dismiss(args.job_id,owner)
            else:
                if not args.job_file:raise ValueError('Provide --job-file')
                value=json.loads(args.job_file.read_text(encoding='utf-8-sig'))
                if args.action=='job-register':
                    job=store.register(owner,value.get('title'),value.get('source'),value.get('run_id'))
                else:job=store.update(args.job_id,value,owner)
                result=dict(job_id=job['id'],title=job['title'],owner=job['owner'],source_type=job['source']['type'])
        elif args.action=='report':
            if not args.steps_file:raise ValueError('Report requires --steps-file')
            from progress import report
            from activation import caller_thread
            result=report(json.loads(args.steps_file.read_text(encoding='utf-8-sig')),caller_thread(args.session,args.provider))
        else:result=start(args.session,args.provider,args.cwd) if args.action=='start' else status(args.session,args.provider)
    except (OSError,ValueError,TimeoutError) as error:
        print(json.dumps(dict(running=False,activated=False,error=str(error)),ensure_ascii=True))
        return 1
    print(json.dumps(result,ensure_ascii=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
