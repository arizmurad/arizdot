"""Render public documentation images using synthetic tasks, never local chats."""
from pathlib import Path
import time
from PIL import Image
from pulse import State
from panel import PanelModel,PanelPainter


def render(output=None):
    output=Path(output or Path(__file__).resolve().parent/'docs/assets');output.mkdir(parents=True,exist_ok=True)
    a='00000000-0000-4000-8000-000000000801';b='claude-desktop:00000000-0000-4000-8000-000000000802'
    first=State(title='Add CSV export',active=True,status='Working',session_ref=a,source_modified=time.time(),
        plan=[dict(step='Read the export requirements',status='completed'),dict(step='Validate exported rows',status='in_progress'),dict(step='Run the regression checks',status='pending')])
    second=State(title='Review release notes',session_ref=b,source_modified=time.time(),
        plan=[dict(step='Read the changelog',status='completed'),dict(step='Check installation steps',status='completed'),dict(step='Review wording',status='in_progress'),dict(step='Prepare the final draft',status='pending')],
        background=dict(title='Review release notes',current='Review wording',next='Prepare the final draft',scope='2/4 steps · reported by Claude',metrics='',health='Reported by Claude',percent=50,active=False,reported=True,kind='chat',phase='working',snapshot_status='recorded',tone='amber'))
    job='job:00000000-0000-4000-8000-000000000803'
    remote=State(title='Crystal · remote calculation',session_ref=job,source_modified=time.time(),
        background=dict(title='Crystal · remote calculation',current='Density cutoff · 130/720 Ry',next='Audit the completed result',scope='SCF convergence · no fixed iteration total',metrics='SCF iteration 8 · ΔE < 1e-12 Ry → 1e-14 Ry',health='Remote API checked 2 s ago',percent=None,active=True,kind='background_job',background_job=True,owner_ref=a,job_visible=True,phase='remote_running',snapshot_status='live',tone='green',steps=[dict(step='Previous checkpoint verified',status='completed')]))
    model=PanelModel();model.update(first,a,[(second,Path(b.split(':')[-1])),(remote,Path('synthetic-job'))],'en');model.toggle(job)
    painter=PanelPainter()
    painter.draw_panel(model,1,1,1,'en').save(output/'overview.png')
    full_height=round(model.layout().height)
    frames=[];durations=[]
    def frame(progress,reveal,duration=65):
        image=painter.draw_panel(model,progress,reveal,len(frames)/15,'en')
        canvas=Image.new('RGB',(410,full_height),'#1b1f27');canvas.paste(image,(0,0),image)
        frames.append(canvas);durations.append(duration)
    model.expanded=None
    frame(0,0,800)
    for i in range(1,9):frame(i/8,0)
    frame(1,0,1000)
    model.expanded=job
    for i in range(1,9):frame(1,i/8)
    frame(1,1,2000)
    for i in range(7,-1,-1):frame(1,i/8)
    model.expanded=None
    for i in range(7,-1,-1):frame(i/8,0)
    frame(0,0,1000)
    frames[0].save(output/'demo.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=True)
    return dict(overview=str(output/'overview.png'),demo=str(output/'demo.gif'))


if __name__=='__main__':print(render())
