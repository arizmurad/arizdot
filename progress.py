"""Explicit Codex milestones, isolated to one conversation and one turn."""
import json
import os
import time
from pathlib import Path
from activation import ROOT,caller_thread,split_ref,write_json


def validate(value):
    if not isinstance(value,dict):raise ValueError('Progress must be a JSON object')
    steps=value.get('steps')
    if not isinstance(steps,list) or not 1<=len(steps)<=40:raise ValueError('Provide 1–40 named steps')
    result=[]
    for step in steps:
        if not isinstance(step,dict) or step.get('status') not in ('pending','in_progress','completed'):raise ValueError('Invalid step status')
        name=step.get('step')
        if not isinstance(name,str) or not name.strip() or len(name)>300:raise ValueError('Each step needs a short name')
        result.append(dict(step=name.strip(),status=step['status']))
    if sum(s['status']=='in_progress' for s in result)>1:raise ValueError('Only one step may be in progress')
    return result


def report(value,session=None,directory=None,root=ROOT):
    from pulse import Tail
    ref=caller_thread(session)
    if not ref:raise ValueError('An invoking conversation is required')
    steps=validate(value)
    provider,raw=split_ref(ref)
    if provider=='claude':
        from claude_support import report_code
        return report_code(raw,steps,root)
    if provider!='codex':raise ValueError('Use the MCP report tool for Claude Desktop')
    directory=Path(directory or Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'sessions')
    path=next(directory.rglob('*'+ref+'.jsonl'),None)
    if not path:raise ValueError('Local conversation source was not found')
    state=Tail(path).poll()
    if not state.active or not state.turn_id:raise ValueError('No active turn was found; progress was not changed')
    data=dict(turn_id=state.turn_id,updated=time.time(),steps=steps,revision=state.revision)
    write_json(Path(root)/'progress'/f'{ref}.json',data)
    return dict(reported=True,completed=sum(s['status']=='completed' for s in steps),total=len(steps),percent=round(100*sum(s['status']=='completed' for s in steps)/len(steps)))


def attach(state,ref,root=ROOT):
    state.milestones={}
    try:
        data=json.loads((Path(root)/'progress'/f'{ref}.json').read_text(encoding='utf-8'))
        steps=validate(data)
        updated=data.get('updated')
        if state.turn_id and data.get('turn_id')==state.turn_id and type(updated) in (int,float) and 0<=time.time()-updated:
            state.milestones=dict(steps=steps,updated=updated,revision=data.get('revision',-1))
    except (OSError,ValueError,TypeError):pass
