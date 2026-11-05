"""Read-only adapter for desktop navigation logs (internal format)."""
import os
import re
import time
from pathlib import Path

UUID = r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}"
ROUTE = re.compile(r"ownerRoutePath=(/local/(" + UUID + r"))(?=[?\s]|$)")


class Navigation:
    def __init__(self, roots=None):
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        self.roots = roots if roots is not None else [
            local / "Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/Codex/Logs",
            local / "Codex/Logs",
        ]
        self.offsets = {}
        self.thread = None
        self.stamp = ""
        self.paths = []
        self.last_scan = -10
        self.forced_thread=None
        self.forced_stamp=''
        if roots is None:
            # A separate status command must see the same explicit activation
            # as the running UI, until a newer navigation supersedes it.
            from activation import ROOT,valid_thread
            from datetime import datetime,timezone
            import json
            try:
                ack=json.loads((ROOT/'activation-ack.json').read_text(encoding='utf-8'))
                if valid_thread(ack.get('thread_id')) and isinstance(ack.get('acknowledged'),(int,float)):
                    self.forced_thread=ack['thread_id']
                    self.forced_stamp=datetime.fromtimestamp(ack['acknowledged'],timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
            except (OSError,ValueError,OverflowError):pass

    def activate(self,thread):
        from activation import valid_thread
        if not valid_thread(thread):raise ValueError('Invalid local thread UUID')
        from datetime import datetime,timezone
        self.forced_thread=thread
        self.forced_stamp=datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

    def consume(self, line):
        match = ROUTE.search(line)
        # Only explicit UI owner navigation, never background thread activity.
        if match and "browser sidebar owner sync" in line:
            stamp = line[:24]
            if stamp >= self.stamp:
                self.stamp = stamp
                self.thread = match.group(2)

    def poll(self):
        now = time.monotonic()
        if now - self.last_scan > 2:
            self.last_scan = now
            paths = [p for root in self.roots for p in Path(root).rglob("*.log")]
            self.paths = sorted(paths, key=lambda p:p.stat().st_mtime, reverse=True)[:4]
        for p in self.paths:
            try:
                size = p.stat().st_size
                offset = self.offsets.get(p, max(0, size - 2_000_000))
                if offset > size:
                    offset = 0
                with p.open("rb") as f:
                    f.seek(offset)
                    while True:
                        line = f.readline()
                        if not line or not line.endswith(b"\n"):
                            break
                        self.offsets[p] = f.tell()
                        self.consume(line.decode("utf-8", errors="replace"))
            except OSError:
                continue
        if self.forced_thread:
            if self.stamp<=self.forced_stamp:return self.forced_thread
            self.forced_thread=None
        return self.thread


def thread_url(thread):
    if not isinstance(thread, str) or not re.fullmatch(UUID, thread):
        raise ValueError("Invalid local thread UUID")
    return "codex://threads/" + thread


def claude_chat_url(value):
    """Accept an actual private chat URL/UUID, never a public share snapshot."""
    from urllib.parse import urlsplit
    from activation import valid_thread
    if isinstance(value,str) and valid_thread(value.strip()):return 'claude://claude.ai/chat/'+value.strip()
    if not isinstance(value,str):raise ValueError('Paste the original https://claude.ai/chat/... link')
    parsed=urlsplit(value.strip())
    if parsed.scheme not in ('https','claude') or parsed.netloc!='claude.ai':raise ValueError('Paste the original https://claude.ai/chat/... link')
    match=re.fullmatch('/chat/('+UUID+')/?',parsed.path)
    if not match:raise ValueError('Use the original /chat/ link, not a /share/ link')
    return 'claude://claude.ai/chat/'+match[1]


def bind_thread(reference,url,root=None):
    from activation import ROOT,split_ref,write_json
    from claude_support import locked,read_snapshot,session_path
    provider,session=split_ref(reference)
    if provider!='claude-desktop':raise ValueError('Chat links can only be assigned to Claude Desktop monitors')
    canonical=claude_chat_url(url)
    path=session_path(session,provider,root or ROOT)
    with locked(path):
        value=read_snapshot(path)
        if not value:raise ValueError('Activate this Claude monitor before linking its conversation')
        value['conversation_id']=canonical.rsplit('/',1)[-1]
        write_json(path,value)
    return canonical


def open_thread(thread):
    if isinstance(thread,str) and thread.startswith('job:'):
        from background_jobs import Store
        from activation import valid_thread
        identity=thread[4:]
        if not valid_thread(identity):raise ValueError('Invalid background job')
        job=next((j for j in Store().list() if j['id']==identity),None)
        if not job:raise ValueError('Background job not found')
        result=open_thread(job['owner'])
        return dict(result,link_reference=job['owner'])
    from activation import split_ref
    provider,session=split_ref(thread)
    if provider=='codex':os.startfile(thread_url(session));return {'exact':True}
    if provider=='claude-desktop':
        from claude_support import read_snapshot,session_path
        from activation import valid_thread
        value=read_snapshot(session_path(session,provider))
        conversation=value.get('conversation_id')
        if valid_thread(conversation):
            os.startfile('claude://claude.ai/chat/'+conversation)
            return {'exact':True}
        return {'exact':False,'needs_link':True,'message':'Claude söhbət linkini bir dəfə əlavə edin'}
    else:
        import shutil,subprocess
        executable=shutil.which('claude')
        if executable:
            subprocess.Popen([executable,'--desktop','--resume',session],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            return {'exact':True}
    # Official missing-ID route opens recent chats; do not invent a deep link.
    os.startfile('claude://claude.ai/chat/')
    return {'exact':False,'message':'Claude açıldı · söhbəti tətbiqdə seçin'}
