"""Local stdio MCP integration for Claude Desktop. Does not launch on connect."""
import asyncio
import uuid
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
import os
from pydantic import StrictInt,BaseModel,Field
from typing import Literal
from claude_support import report_desktop,session_path,read_snapshot
from activation import valid_thread


def time_stale(value):
    import time
    return time.time()-value.get('updated',0)>120

mcp=MCPServer('arizdot',instructions='Use arizdot_open only when the user asks to activate the indicator. Keep monitor_id in this conversation. Immediately report actual current work, title and the FULL named plan with arizdot_report. Report at real transitions; on later user turns use new_turn=true in the first report. Omitted steps clear the old plan. Register EVERY actual background job with arizdot_job_register immediately after a verified launch and before returning a reply. Prefer an independent file/API/process/service source so monitoring continues when Claude is idle or closed. Keep its job_id; use arizdot_jobs to rediscover it. Do not relaunch work for monitoring, invent sources or complete jobs merely because a reply ends. Reported sources are explicitly model-provided and cannot update themselves. Never mix conversations or invent percentages.',version='0.2.0')


class Milestone(BaseModel):
    step:str=Field(min_length=1,max_length=1000)
    status:Literal['pending','in_progress','completed']


def require_monitor(monitor_id):
    if not valid_thread(monitor_id):raise ToolError('Invalid monitor UUID')
    try:value=read_snapshot(session_path(monitor_id,'claude-desktop'))
    except (OSError,ValueError):raise ToolError('Local monitor state cannot be read') from None
    if not value:raise ToolError('Monitor not found; call arizdot_open first')
    return value


@mcp.tool()
async def arizdot_open(title:str='Claude Desktop',monitor_id:str|None=None,conversation_id:str|None=None)->dict:
    """Activate the local indicator for this conversation. Preserve its returned monitor_id. conversation_id is optional: use only a known actual Claude chat UUID, never guess one."""
    from control import start
    if os.name!='nt':raise ToolError('The native arizdot indicator currently requires Windows')
    monitor_id=monitor_id or str(uuid.uuid4())
    if not valid_thread(monitor_id):raise ToolError('Invalid monitor UUID')
    try:
        if session_path(monitor_id,'claude-desktop').exists():
            value=require_monitor(monitor_id)
            if conversation_id or time_stale(value):
                stale=time_stale(value)
                report_desktop(monitor_id,value['title'],'Claude tərəfindən vəziyyət bildirilməsi gözlənilir' if stale else value['current'],None if stale else value.get('completed'),None if stale else value.get('total'),'' if stale else value.get('next',''),'waiting' if stale else value.get('phase','waiting'),conversation_id=conversation_id,steps=None if stale else value.get('plan'))
        else:report_desktop(monitor_id,title,'Claude tərəfindən vəziyyət bildirilməsi gözlənilir',phase='waiting',conversation_id=conversation_id)
    except ValueError as error:raise ToolError(str(error)) from None
    except OSError:raise ToolError('Local monitor state cannot be written') from None
    result=await asyncio.to_thread(start,monitor_id,'claude-desktop')
    return dict(**result,monitor_id=monitor_id,telemetry='reported',next_required_action='Call arizdot_report now with the real current work, next target and named steps; update it at each milestone and on later turns while monitoring.',exact_chat_return=bool(read_snapshot(session_path(monitor_id,'claude-desktop')).get('conversation_id')))


@mcp.tool()
def arizdot_report(monitor_id:str,current:str,completed:StrictInt|None=None,total:StrictInt|None=None,next_step:str='',phase:Literal['working','waiting','completed','error']='working',steps:list[Milestone]|None=None,title:str|None=None,new_turn:bool=False)->dict:
    """Refresh current work, task title, next target and the FULL named plan. Set new_turn=true on the first report of each user turn. Omitted steps clear old milestones. Counts must agree with steps. Reported state does not verify background jobs or open the UI."""
    value=require_monitor(monitor_id)
    try:report_desktop(monitor_id,title if title is not None else value['title'],current,completed,total,next_step,phase,steps=[s.model_dump() for s in steps] if steps is not None else None,new_turn=new_turn)
    except ValueError as error:raise ToolError(str(error)) from None
    except OSError:raise ToolError('Local monitor state cannot be written') from None
    from control import status
    return dict(monitor_id=monitor_id,**status(monitor_id,'claude-desktop'))


@mcp.tool()
def arizdot_status(monitor_id:str)->dict:
    """Read this conversation's existing monitor, freshness and progress scope without starting the indicator."""
    require_monitor(monitor_id)
    from control import status
    return dict(monitor_id=monitor_id,**status(monitor_id,'claude-desktop'))


@mcp.tool()
def arizdot_job_register(monitor_id:str,title:str,source:dict,run_id:str|None=None)->dict:
    """Register work that outlives a reply. Use an existing JSON status file, HTTPS JSON endpoint, actual local process, or Kaggle read connector. A reported source is explicitly model-reported. Register immediately after a real launch; do not launch a second job. Keep job_id for updates. Source types: json_file(path), http_json(url, optional token_env), process(pid), kaggle(kernel), reported."""
    require_monitor(monitor_id)
    from background_jobs import Store
    try:job=Store().register('claude-desktop:'+monitor_id,title,source,run_id)
    except (ValueError,OSError,TypeError) as error:raise ToolError(str(error)) from None
    return dict(job_id=job['id'],title=job['title'],source_type=job['source']['type'],lifetime='independent of conversation turns')


@mcp.tool()
def arizdot_job_update(monitor_id:str,job_id:str,status:dict)->dict:
    """Update only a reported background job owned by this conversation. Send state, concrete current/next, and verified steps or completed/total units. This cannot override an observed file/API/process source or change actual execution."""
    require_monitor(monitor_id)
    from background_jobs import Store
    try:job=Store().update(job_id,status,'claude-desktop:'+monitor_id)
    except (ValueError,OSError,TypeError) as error:raise ToolError(str(error)) from None
    return dict(job_id=job['id'],updated=True,telemetry='reported')


@mcp.tool()
def arizdot_jobs(monitor_id:str)->dict:
    """List this conversation's registered background jobs without launching or stopping work."""
    require_monitor(monitor_id)
    from background_jobs import Store
    return dict(jobs=[dict(job_id=j['id'],title=j['title'],source_type=j['source']['type']) for j in Store().list('claude-desktop:'+monitor_id)])


@mcp.prompt(name='arizdot')
def arizdot_prompt()->str:
    """Activate the floating indicator for the current conversation."""
    return 'Open arizdot using arizdot_open and retain monitor_id in this conversation. Immediately report title, current work, next_step and FULL named steps. On later user turns use new_turn=true in the first report. Update at real milestones. For EVERY background job you start, verify the launch then call arizdot_job_register with the real file/API/process/service source before returning a reply. Those jobs live independently of conversation turns and continue to be observed while Claude is closed. Never restart work just to attach monitoring, invent a source, use a remote PID as local, or mark a job finished because a reply ends. Model-reported sources need further reports and are not unattended live telemetry. Use arizdot_jobs to rediscover job IDs. Omitted plan steps clear old progress; never invent counts or ETA.'


if __name__=='__main__':mcp.run(transport='stdio')
