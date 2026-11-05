"""Local Claude Code hook snapshots and explicitly reported Desktop state."""
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from activation import ROOT,valid_thread,write_json


def session_path(session,provider='claude',root=ROOT):
    if provider not in ('claude','claude-desktop') or not valid_thread(session):raise ValueError('Invalid Claude session')
    return Path(root)/'providers'/provider/(session+'.json')


@contextmanager
def locked(path):
    """Bounded cross-process lock for concurrent, independent hook commands."""
    lock=path.with_suffix('.lock');lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a+b') as stream:
        if stream.tell()==0:stream.write(b'0');stream.flush()
        deadline=time.monotonic()+1
        while True:
            try:
                stream.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()>deadline:raise TimeoutError('Claude snapshot busy')
                time.sleep(.01)
        try:yield
        finally:
            stream.seek(0)
            if os.name=='nt':msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def read_snapshot(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value,dict):raise ValueError('Invalid snapshot')
        return value
    except FileNotFoundError:return {}


def register(session,cwd=None,root=ROOT):
    path=session_path(session,root=root)
    with locked(path):
        value=read_snapshot(path)
        if not value:
            value=dict(session=session,provider='claude',title='Claude Code',phase='selected',updated=time.time(),turn_id=uuid.uuid4().hex)
        if cwd:value['cwd']=str(Path(cwd).expanduser().resolve())
        if cwd and value.get('title')=='Claude Code':value['title']='Claude Code · '+Path(cwd).name
        write_json(path,value)
    return value


def normalize_plan(items):
    if not isinstance(items,list):return []
    result=[]
    for item in items[:200]:
        if not isinstance(item,dict):continue
        status=item.get('status','pending')
        text=item.get('content') or item.get('subject') or item.get('step')
        if isinstance(text,str) and status in ('pending','in_progress','completed'):
            result.append(dict(step=text[:1000],status=status,id=str(item.get('id',''))[:100]))
    return result


TOOLS={'Read':'Fayl oxuyur','Glob':'Faylları axtarır','Grep':'Mətndə axtarır','Bash':'Əmr icra edir','PowerShell':'Əmr icra edir','Write':'Faylları dəyişir','Edit':'Faylları dəyişir','WebSearch':'Məlumat axtarır','WebFetch':'Məlumat axtarır','TodoWrite':'Planı yeniləyir','TaskCreate':'Planı yeniləyir','TaskUpdate':'Planı yeniləyir','TaskList':'Planı oxuyur'}


def record_hook(payload,root=ROOT):
    if not isinstance(payload,dict):raise ValueError('Expected a hook object')
    session=payload.get('session_id');path=session_path(session,root=root)
    event=payload.get('hook_event_name')
    allowed={'UserPromptSubmit','PreToolUse','PostToolUse','PostToolUseFailure','PermissionRequest','Notification','Stop','StopFailure','SessionEnd'}
    if event not in allowed:return None
    with locked(path):
        value=read_snapshot(path) or dict(session=session,provider='claude',title='Claude Code',turn_id=uuid.uuid4().hex)
        event_id=payload.get('tool_use_id')
        if isinstance(event_id,str):
            key=event+':'+event_id
            seen=value.get('seen_events',[])
            if key in seen:return value
            value['seen_events']=(seen+[key])[-200:]
        value.update(updated=time.time(),last_event=event)
        if isinstance(payload.get('cwd'),str):value['cwd']=payload['cwd'][:2000]
        if event=='UserPromptSubmit':
            value.update(phase='working',plan=[],plan_updated=0,completed_actions=[],running_tools={},turn_id=str(payload.get('prompt_id') or uuid.uuid4().hex),current='Tapşırığı araşdırır',tool='')
        elif event in ('PreToolUse','PostToolUse'):
            tool=str(payload.get('tool_name',''))[:150]
            inputs=payload.get('tool_input') or {}
            response=payload.get('tool_response') or {}
            if not isinstance(inputs,dict):inputs={}
            if not isinstance(response,dict):response={}
            value.update(phase='working',tool=tool,current=TOOLS.get(tool,'Alətlə işləyir'))
            from activity import label,append
            identity=event_id or tool
            running=value.get('running_tools',{})
            if event=='PreToolUse':running[identity]=label(tool,inputs)
            else:
                running.pop(identity,None)
                value['completed_actions']=append(value.get('completed_actions',[]),identity,label(tool,inputs))
                value['current']='Növbəti əməliyyat hazırlanır'
            value['running_tools']=running
            # Task changes count only after the tool actually succeeds.
            if event=='PostToolUse':
                before_plan=json.dumps(value.get('plan',[]),sort_keys=True)
                if tool=='TodoWrite' and isinstance(inputs.get('todos'),list):value['plan']=normalize_plan(inputs['todos'])
                elif tool=='TaskList' and isinstance(response.get('tasks'),list):value['plan']=normalize_plan(response['tasks'])
                elif tool=='TaskCreate':
                    item=response.get('task',response)
                    if isinstance(item,dict) and item.get('id'):
                        if not any(p.get('id')==str(item['id']) for p in value.get('plan',[])):
                            value['plan']=value.get('plan',[])+normalize_plan([dict(id=item['id'],subject=inputs.get('subject'),status='pending')])
                elif tool=='TaskUpdate':
                    for item in value.get('plan',[]):
                        if item.get('id')==str(inputs.get('taskId')):
                            if inputs.get('status') in ('pending','in_progress','completed'):item['status']=inputs['status']
                            if isinstance(inputs.get('subject'),str):item['step']=inputs['subject'][:1000]
                    if inputs.get('status')=='deleted':value['plan']=[p for p in value.get('plan',[]) if p.get('id')!=str(inputs.get('taskId'))]
                if json.dumps(value.get('plan',[]),sort_keys=True)!=before_plan:
                    value['plan_updated']=value['updated']
                    value['current']=next((p['step'] for p in value.get('plan',[]) if p['status']=='in_progress'),value['current'])
        elif event=='PermissionRequest':value.update(phase='waiting',current='İstifadəçi cavabı gözlənilir')
        elif event=='Notification':
            if payload.get('notification_type') in ('permission_prompt','idle_prompt'):value.update(phase='waiting',current='İstifadəçi cavabı gözlənilir')
        elif event in ('PostToolUseFailure','StopFailure'):
            value.update(phase='error',current='Claude alət xətası · yoxlama tələb olunur')
            value.get('running_tools',{}).pop(event_id,None)
        elif event=='Stop':
            background=payload.get('background_tasks') or []
            value.update(phase='background' if background else 'completed',current='Fon işi davam edir' if background else 'Cavab hazırdır')
            value['background_task_count']=len(background)
            value['running_tools']={}
            text=payload.get('last_assistant_message')
            if isinstance(text,str):value['last_message']=text[:4000]
        elif event=='SessionEnd':value.update(phase='ended',current='Claude sessiyası bitdi')
        write_json(path,value)
    return value


def report_code(session,steps,root=ROOT):
    from progress import validate
    plan=validate(dict(steps=steps));path=session_path(session,root=root)
    with locked(path):
        value=read_snapshot(path)
        if not value or value.get('phase') not in ('working','waiting','background'):raise ValueError('No active Claude Code turn was found')
        value.update(plan=plan,updated=time.time(),plan_updated=time.time(),tool='')
        value['current']=next((p['step'] for p in plan if p['status']=='in_progress'),'Mərhələlər tamamlandı' if all(p['status']=='completed' for p in plan) else 'Tapşırığı araşdırır')
        write_json(path,value)
    return dict(reported=True,completed=sum(p['status']=='completed' for p in plan),total=len(plan))


def report_desktop(session,title,current,completed=None,total=None,next_step='',phase='working',root=ROOT,conversation_id=None,steps=None,new_turn=False):
    if phase not in ('working','waiting','completed','error'):raise ValueError('Invalid reported phase')
    for field in (title,current,next_step):
        if not isinstance(field,str) or len(field)>4000:raise ValueError('Text must be at most 4000 characters')
    if (completed is None)!=(total is None):raise ValueError('Both completed and total are required')
    if total is not None and (type(total) is not int or type(completed) is not int or not 0<=completed<=total or total<=0):raise ValueError('Invalid completed/total counts')
    if steps is not None:
        if not isinstance(steps,list) or len(steps)>200:raise ValueError('At most 200 steps are supported')
        for step in steps:
            if not isinstance(step,dict) or not isinstance(step.get('step'),str) or not step['step'].strip() or len(step['step'])>1000 or step.get('status') not in ('pending','in_progress','completed'):raise ValueError('Invalid reported step')
        done=sum(p['status']=='completed' for p in steps)
        if steps:
            if completed is not None and (completed!=done or total!=len(steps)):raise ValueError('Counts must agree with the reported steps')
            completed,total=done,len(steps)
    if (completed is None)!=(total is None):raise ValueError('Both completed and total are required')
    if total is not None and (type(total) is not int or type(completed) is not int or not 0<=completed<=total or total<=0):raise ValueError('Invalid completed/total counts')
    path=session_path(session,'claude-desktop',root)
    if conversation_id is not None and not valid_thread(conversation_id):raise ValueError('Invalid Claude conversation UUID')
    with locked(path):
        old=read_snapshot(path)
        turn=old.get('turn_id') or uuid.uuid4().hex
        if new_turn or (old.get('phase')=='completed' and phase in ('working','waiting')):turn=uuid.uuid4().hex
        value=dict(provider='claude-desktop',session=session,title=title,current=current,next=next_step,phase=phase,
                   updated=time.time(),completed=completed,total=total,turn_id=turn,reported=True)
        if steps is not None:value['plan']=normalize_plan(steps)
        if conversation_id or old.get('conversation_id'):value['conversation_id']=conversation_id or old['conversation_id']
        write_json(path,value)
    return value


def snapshot_state(session,provider,root=ROOT):
    from pulse import State
    path=session_path(session,provider,root)
    value=read_snapshot(path)
    ref=provider+':'+session
    if not value:
        return State(title='Claude Code' if provider=='claude' else 'Claude Desktop',stage='Claude status mənbəyi gözlənilir',session_ref=ref,
            background=dict(title='Claude',current='Claude status mənbəyi gözlənilir',metrics='',health='Məlumat yoxdur',next='',scope='Faiz ölçülmür',percent=None,active=False,snapshot_status='offline',phase='source_error',badge='OFFLINE',tone='red'))
    phase=value.get('phase','selected');age=max(0,time.time()-value.get('updated',0))
    reported=provider=='claude-desktop'
    plan=normalize_plan(value.get('plan'))
    # Desktop reports are already explicit current-work descriptions. A retained
    # plan from a previous report must never override a newer current string.
    current=None
    running=value.get('running_tools',{})
    if not reported and running:current=next(reversed(running.values()))
    current=current or value.get('current','Claude status mənbəyi gözlənilir')
    freshness='stale' if age>120 else 'recorded' if reported or phase in ('completed','ended','error','selected') else 'live'
    count=sum(p['status']=='completed' for p in plan)
    percent=round(count*100/len(plan)) if plan else None
    scope=f'{count}/{len(plan)} addım · plan üzrə' if plan else 'Faiz ölçülmür'
    if not reported and plan and time.time()-value.get('plan_updated',value.get('updated',0))>120:
        percent=None;scope='Mərhələ statusu yenilənməlidir'
    if reported:
        total=value.get('total');done=value.get('completed')
        if type(total) is int and type(done) is int and total>0 and 0<=done<=total:
            percent=round(done*100/total);scope=f'{done}/{total} addım · Claude tərəfindən bildirilib'
        else:scope='Faiz ölçülmür · Claude tərəfindən bildirilib'
    next_step=value.get('next') or next((p['step'] for p in plan if p['status']=='pending'),'')
    if not reported and plan and percent is None:next_step=''
    if freshness=='stale':
        current='Yeni status məlumatı gözlənilir';next_step='';percent=None
        scope='Mərhələ statusu yenilənməlidir'
    health=('Claude tərəfindən bildirilib' if reported else 'Claude hadisəsi qeydə alınıb')+f' · qeyd {int(age)} s əvvəl'
    data=dict(title=value.get('title','Claude Code'),current=current,next=next_step,scope=scope,percent=percent,
        active=not reported and phase in ('working','background') and freshness=='live',status=phase,phase='needs_review' if phase=='error' else phase,
        badge={'waiting':'WAIT','error':'REVIEW','completed':'DONE','ended':'STOP'}.get(phase,'RUN'),tone='red' if phase=='error' else 'amber' if phase=='waiting' or reported else 'green',
        metrics='',health=health,snapshot_status=freshness,source=str(path),
        controller_updated_seconds=age,output_age_seconds=age,case=value.get('turn_id',session),reported=reported,kind='chat',
        completed_count=value.get('completed'),total_count=value.get('total'))
    state=State(title=data['title'],plan=plan,background=data,source_path=str(path),source_modified=value.get('updated',0),session_ref=ref,turn_id=value.get('turn_id',''))
    state.completed_actions=value.get('completed_actions',[])
    return state
