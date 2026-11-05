"""Explicit skill invocation -> UI acknowledgement and chat context."""
import json
import os
import re
import time
import uuid
from pathlib import Path

ROOT=Path(os.environ.get('ARIZDOT_DATA_DIR',Path(__file__).resolve().parent/'config'))
UUID=re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')


def valid_thread(value):return bool(isinstance(value,str) and UUID.fullmatch(value))


def split_ref(value):
    if valid_thread(value):return 'codex',value
    if isinstance(value,str) and ':' in value:
        provider,session=value.split(':',1)
        if provider in ('claude','claude-desktop') and valid_thread(session):return provider,session
    raise ValueError('Invalid provider/session reference')


def valid_ref(value):
    try:split_ref(value);return True
    except ValueError:return False


def session_ref(session,provider='codex'):
    if provider not in ('codex','claude','claude-desktop'):raise ValueError('Unknown provider')
    if not valid_thread(session):raise ValueError('Invalid session UUID')
    return session if provider=='codex' else provider+':'+session


def caller_thread(explicit=None,provider=None):
    if explicit is not None:
        if valid_ref(explicit) and ':' in explicit:
            detected,_=split_ref(explicit)
            if provider and detected!=provider:raise ValueError('Provider does not match session')
            return explicit
        return session_ref(explicit,provider or 'codex')
    if provider in ('claude','claude-desktop'):
        value=os.environ.get('CLAUDE_SESSION_ID')
        if not valid_thread(value):raise ValueError('Claude invocation requires an explicit session UUID')
        return session_ref(value,provider)
    return next((os.environ[k] for k in ('CODEX_THREAD_ID','CODEX_SESSION_ID') if valid_thread(os.environ.get(k))),None)


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_text(json.dumps(value),encoding='utf-8')
        os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)


def request(thread=None,root=ROOT,provider=None):
    value=dict(id=uuid.uuid4().hex,created=time.time(),thread=caller_thread(thread,provider))
    write_json(Path(root)/'activation-request.json',value)
    return value


def acknowledged(value,root=ROOT):
    try:
        data=json.loads((Path(root)/'activation-ack.json').read_text(encoding='utf-8'))
        return data if data.get('id')==value['id'] else None
    except (OSError,ValueError):return None


class Inbox:
    def __init__(self,root=ROOT):self.root=Path(root);self.last=None

    def poll(self):
        try:value=json.loads((self.root/'activation-request.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):return None
        if not isinstance(value,dict) or value.get('id')==self.last:return None
        if not isinstance(value.get('created'),(int,float)) or not -2<=time.time()-value['created']<=12:return None
        if value.get('thread') is not None and not valid_ref(value['thread']):return None
        if not isinstance(value.get('id'),str):return None
        self.last=value['id']
        return value

    def ack(self,value,thread):
        write_json(self.root/'activation-ack.json',dict(id=value['id'],thread_id=thread,visible=True,acknowledged=time.time()))
