"""Concurrent work cards and inline milestones, with no secondary windows."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import math
import time
from PIL import Image,ImageDraw,ImageChops,ImageOps
from surface import Painter,WIDTH,SCALE
from languages import DisplayState,translate

ROW=86
HEADER=38
FOOTER=28
DETAIL=220
PAGE=3
COLORS={'green':'#68f0b0','amber':'#ffc56d','red':'#ff8585','gray':'#b4b9c6'}
# Provider identity remains separate from progress / health colors.
PROVIDER_ASSETS=Path(__file__).resolve().parent/'assets/providers'
PROVIDERS={
    'Codex':dict(image='openai.png',mark='Cx',accent='#a9caff',tile='#19283d',border='#344a69'),
    'Claude':dict(image='claude.webp',mark='Cl',accent='#efbda2',tile='#30241f',border='#655044')}
LABELS={
 'en':dict(done='Completed',current='Working now',next='Next target',unknown='No completed steps recorded',unplanned='Next target has not been recorded',hint='Click a task for steps',tasks='tasks',reported='REPORTED',live='LIVE',stale='STALE',offline='OFFLINE',recorded='RECORDED',more='Scroll for more',count='completed steps; names not reported'),
 'az':dict(done='Bitən hissələr',current='İndi görülən iş',next='Növbəti hədəf',unknown='Bitən hissələr barədə qeyd yoxdur',unplanned='Növbəti hədəf bildirilməyib',hint='Alt proseslər üçün işi seçin',tasks='iş',reported='BİLDİRİLİB',live='CANLI',stale='KÖHNƏ',offline='ƏLAQƏ YOX',recorded='QEYD',more='Davamı üçün sürüşdürün',count='hissə bitib; adlar bildirilməyib')}


@dataclass(frozen=True)
class TaskCard:
    ref:str
    title:str
    current:str
    next_step:str
    scope:str
    metrics:str
    health:str
    percent:int|None
    freshness:str
    tone:str
    working:bool
    provider:str
    completed:tuple
    completed_count:int|None=None
    reported:bool=False
    completed_source:str='plan'
    phase:str='working'
    background_job:bool=False


def card(state,reference,language):
    d=DisplayState(state,language)
    job=state.background or {}
    plan=job.get('steps',[]) if job and job.get('kind')!='chat' else state.work_plan
    completed=tuple(translate(p.get('step',''),language) for p in plan if p.get('status')=='completed' and p.get('step'))
    source='plan'
    metrics=d.live_metrics
    if not job and state.detail and state.detail!=state.current:metrics=state.detail
    # Tool invocations are diagnostics, not project milestones.
    if not job:metrics=''
    if not job and not state.active:current=translate(state.stage,language)
    else:current=d.current
    return TaskCard(reference,d.live_title,current,d.next_step,d.progress_scope,metrics,d.live_health,
        d.percent,d.freshness,d.live_tone,d.working,
        'Claude' if reference.startswith('claude') or job.get('owner_ref','').startswith('claude') else 'Codex',completed,
        len(completed) if plan else job.get('finished_count',job.get('completed_count')),bool(job.get('reported')),source,
        job.get('phase','working' if state.active else 'idle'),bool(job.get('background_job')))


def relevant(state):
    job=state.background or {}
    if job.get('background_job'):return job.get('job_visible',True)
    phase=job.get('phase','')
    if job and job.get('kind')!='chat':return phase not in ('completed','stopped_by_user')
    age=time.time()-state.source_modified if state.source_modified else 0
    if job.get('reported'):return phase in ('working','waiting','needs_review') and age<120
    return (state.working or phase in ('waiting','needs_review','background')) and age<900


@dataclass(frozen=True)
class Layout:
    rows:tuple
    details:tuple|None
    height:float

    def hit(self,x,y):
        if not 12<=x<=WIDTH-12:return None
        return next((ref for ref,top,bottom in self.rows if top<=y<bottom),None)


class PanelModel:
    def __init__(self):
        self.cards=[]
        self.expanded=None
        self.offset=0
        self.detail_scroll=0

    def update(self,state,reference,entries,language,preserve_order=False):
        candidates={}
        visible_refs={c.ref for c in self.visible}
        for item,path in entries:
            ref=item.session_ref or path.stem[-36:]
            # A task finishing while being clicked remains readable until exit.
            # Its new status is still used; only removal/reordering is deferred.
            if relevant(item) or (preserve_order and ref in visible_refs):candidates[ref]=item
        if reference or not candidates:
            prior=candidates.get(reference or '')
            # The concurrent reader can finish after the primary reader. Keep
            # the newest payload for the selected row, not a cached primary.
            def version(item):return (max(item.source_modified,item.milestones.get('updated',0)),item.revision)
            if prior is None or version(state)>=version(prior):candidates[reference or '']=state
        # Follow the current chat between visits. During interaction keep the
        # same rows under the pointer even when the other provider takes focus.
        previous=[c.ref for c in self.cards]
        if preserve_order:order=[r for r in previous if r in candidates]
        else:order=([reference] if reference in candidates else [])+[r for r in previous if r in candidates and r!=reference]
        order += [r for r in candidates if r not in order]
        self.cards=[card(candidates[ref],ref,language) for ref in order]
        self.offset=min(self.offset,max(0,len(self.cards)-PAGE))
        if self.expanded not in [c.ref for c in self.visible]:self.expanded=None;self.detail_scroll=0

    @property
    def visible(self):return self.cards[self.offset:self.offset+PAGE]

    @property
    def indicator_task(self):
        return next((c for c in self.cards if c.background_job and c.working),None) or next((c for c in self.cards if c.working),None) or (self.visible[0] if self.visible else None)

    def toggle(self,reference):
        if reference and reference in [c.ref for c in self.visible]:
            self.expanded=None if self.expanded==reference else reference
            self.detail_scroll=0

    def scroll(self,delta,details=False):
        if details and self.expanded:self.detail_scroll=max(0,self.detail_scroll+delta*3)
        else:
            self.offset=max(0,min(max(0,len(self.cards)-PAGE),self.offset+delta))
            if self.expanded not in [c.ref for c in self.visible]:self.expanded=None;self.detail_scroll=0

    def layout(self,reveal=1):
        rows=[];details=None;y=HEADER
        for task in self.visible:
            rows.append((task.ref,y,y+ROW-4));y+=ROW
            if task.ref==self.expanded:
                details=(y,y+DETAIL*reveal)
                y+=DETAIL*reveal
        return Layout(tuple(rows),details,y+FOOTER)


class PanelPainter(Painter):
    def image(self,height):return Image.new('RGBA',(WIDTH*SCALE,round(height*SCALE)))

    @lru_cache(maxsize=2)
    def provider_logo(self,provider):
        definition=PROVIDERS.get(provider,PROVIDERS['Codex'])
        try:
            with Image.open(PROVIDER_ASSETS/definition['image']) as original:
                logo=ImageOps.contain(original.convert('RGBA'),(22*SCALE,22*SCALE),Image.Resampling.LANCZOS)
        except OSError:return None
        tile=Image.new('RGBA',(22*SCALE,22*SCALE))
        tile.alpha_composite(logo,((tile.width-logo.width)//2,(tile.height-logo.height)//2))
        mask=Image.new('L',tile.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,tile.width-1,tile.height-1),radius=4*SCALE,fill=255)
        tile.putalpha(ImageChops.multiply(tile.getchannel('A'),mask))
        return tile

    def text(self,draw,x,y,value,size=12,color='#c4c9d4',bold=False):
        draw.text((round(x*SCALE),round(y*SCALE)),str(value),font=self.font(size,bold),fill=color)

    @lru_cache(maxsize=256)
    def wrap(self,value,width=350,size=12):
        result=[]
        for paragraph in str(value).splitlines():
            line=''
            for word in paragraph.split():
                candidate=(line+' '+word).strip()
                if line and self.font(size).getlength(candidate)>width*SCALE:result.append(line);line=''
                # Long paths/words also wrap without overflowing the surface.
                while self.font(size).getlength(word)>width*SCALE:
                    end=max(1,int(len(word)*width*SCALE/self.font(size).getlength(word)))
                    while end>1 and self.font(size).getlength(word[:end])>width*SCALE:end-=1
                    if line:result.append(line);line=''
                    result.append(word[:end]);word=word[end:]
                line=(line+' '+word).strip()
            if line:result.append(line)
        return tuple(result)

    @lru_cache(maxsize=24)
    def detail_lines(self,task,language):
        labels=LABELS[language]
        az=language=='az'
        done=task.completed or ((str(task.completed_count)+' '+labels['count'],) if task.completed_count else (labels['unknown'],))
        current=task.current+('\n'+task.metrics if task.metrics else '')
        done_label=labels['done']
        if task.freshness in ('stale','offline'):done_label='Son qeydə alınan bitən hissələr' if az else 'Last recorded completed steps'
        current_label=labels['current']
        if task.freshness in ('stale','offline'):current_label='Son qeydə alınan iş' if az else 'Last recorded work'
        elif task.phase in ('completed','ended','idle'):current_label='Son nəticə / vəziyyət' if az else 'Latest result / status'
        next_label=('Son qeydə alınan hədəf' if az else 'Last recorded target') if task.freshness in ('stale','offline') else labels['next']
        sections=((current_label,(current,),'#c0d4ff'),(done_label,done,'#90d9b6'),(next_label,(task.next_step or labels['unplanned'],),'#c4c9d4'))
        summary=(('Proqres' if az else 'Progress')+f' · {task.percent}% · '+task.scope) if task.percent is not None else (('Proqres · status yenilənməsi gözlənilir' if az else 'Progress · waiting for a status update') if task.freshness in ('stale','offline') else ('Proqres · mərhələ planı bildirilməyib' if az else 'Progress · milestone plan not reported'))
        if task.background_job and task.percent is None and task.freshness not in ('stale','offline'):
            summary=('Proqres' if az else 'Progress')+' · '+task.scope
        lines=[(line,True,'#90d9b6') for line in self.wrap(summary)]
        for heading,values,color in sections:
            if heading!=current_label:lines.append(('',False,color))
            lines.append((heading,True,color))
            for value in values:
                lines.extend((line,False,'#d6dae3') for line in self.wrap(value))
        lines.append(('',False,'#b4b9c6'))
        lines.extend((line,False,'#b4b9c6') for line in self.wrap(task.health+' · '+task.scope))
        return tuple(lines)

    @lru_cache(maxsize=48)
    def details(self,task,language,scroll):
        lines=self.detail_lines(task,language)
        scroll=min(scroll,max(0,len(lines)-10))
        overlay=self.image(DETAIL)
        draw=ImageDraw.Draw(overlay)
        draw.rounded_rectangle((16*SCALE,0,(WIDTH-16)*SCALE,(DETAIL-8)*SCALE),radius=12*SCALE,fill='#12161d')
        for i,(value,bold,color) in enumerate(lines[scroll:scroll+10]):self.text(draw,28,10+i*18,value,12,color,bold)
        if len(lines)>10:
            self.text(draw,28,193,LABELS[language]['more'],10,'#a7b1c3')
            top=10+166*scroll/max(1,len(lines)-10)
            draw.rounded_rectangle(((WIDTH-24)*SCALE,top*SCALE,(WIDTH-22)*SCALE,(top+16)*SCALE),radius=SCALE,fill='#6b778e')
        return overlay.resize((WIDTH,DETAIL),Image.Resampling.LANCZOS),scroll

    @lru_cache(maxsize=64)
    def row(self,task,selected,hovered,language):
        overlay=self.image(ROW)
        draw=ImageDraw.Draw(overlay)
        draw.rounded_rectangle((12*SCALE,0,(WIDTH-12)*SCALE,(ROW-5)*SCALE),radius=12*SCALE,fill='#1a222d' if selected else '#151b23' if hovered else '#101318')
        color=COLORS.get(task.tone,COLORS['gray'])
        provider=PROVIDERS.get(task.provider,PROVIDERS['Codex'])
        logo=self.provider_logo(task.provider)
        if logo is not None:overlay.alpha_composite(logo,(24*SCALE,5*SCALE))
        else:
            draw.rounded_rectangle((24*SCALE,7*SCALE,44*SCALE,27*SCALE),radius=6*SCALE,fill=provider['tile'],outline=provider['border'],width=SCALE)
            mark_width=self.font(10,True).getlength(provider['mark'])/SCALE
            self.text(draw,34-mark_width/2,9,provider['mark'],10,provider['accent'],True)
        self.text(draw,52,7,self.fit(task.title,WIDTH-143,13,True),13,'#f5f5f7',True)
        self.text(draw,WIDTH-70,8,f'{task.percent}%' if task.percent is not None else '—',13,color,True)
        # Chevron indicates that this row, rather than the dot, opens milestones.
        x=WIDTH-26;y=17
        edge=y+2 if selected else y-2
        middle=y-2 if selected else y+2
        draw.line(((x-3)*SCALE,edge*SCALE,x*SCALE,middle*SCALE,(x+3)*SCALE,edge*SCALE),fill='#b4bfd1',width=SCALE)
        self.text(draw,24,29,self.fit(task.current,WIDTH-50,12),12,'#d2d7e2')
        badge=LABELS[language][task.freshness]
        if task.reported and task.freshness=='recorded':badge=LABELS[language]['reported']
        self.text(draw,24,52,task.provider,10,provider['accent'],True)
        label_width=self.font(10,True).getlength(task.provider)/SCALE
        self.text(draw,24+label_width+5,52,'· '+badge,10,color,True)
        self.text(draw,24,66,self.fit(task.scope,WIDTH-50,10),10,'#aab2c1')
        return overlay.resize((WIDTH,ROW),Image.Resampling.LANCZOS)

    @lru_cache(maxsize=128)
    def background(self,width,height):
        image=self.image(height)
        draw=ImageDraw.Draw(image)
        left=(WIDTH-width)/2
        draw.rounded_rectangle((round(left*SCALE),0,round((left+width-1)*SCALE),(height-1)*SCALE),radius=round(min(22,width/2)*SCALE),fill='#08090b')
        return image.resize((WIDTH,height),Image.Resampling.LANCZOS)

    def draw_panel(self,model,progress,reveal,now,language='az',hovered=None,error=False,aligned=(False,False)):
        layout=model.layout(reveal)
        height=max(32,math.ceil(32+(layout.height-32)*progress))
        width=round(32+(WIDTH-32)*progress,2)
        image=self.background(width,height).copy()
        task=model.indicator_task
        color=COLORS.get(task.tone if task else 'gray',COLORS['gray'])
        # A small supersampled icon keeps curves sharp during the morph.
        icon=Image.new('RGBA',(24*SCALE,24*SCALE));draw=ImageDraw.Draw(icon)
        draw.ellipse((4*SCALE,4*SCALE,20*SCALE,20*SCALE),outline='#2b3341',width=2*SCALE)
        if task and (task.percent is not None or task.working):
            start=-90 if task.percent is not None else (now*140)%360
            extent=max(1,min(100,task.percent)*3.59) if task.percent is not None else 100
            draw.arc((4*SCALE,4*SCALE,20*SCALE,20*SCALE),start,start+extent,fill=color,width=2*SCALE)
        draw.ellipse((9*SCALE,9*SCALE,15*SCALE,15*SCALE),fill=color)
        cx=WIDTH/2+(22-WIDTH/2)*progress;cy=16+3*progress
        image.alpha_composite(icon.resize((24,24),Image.Resampling.LANCZOS),(round(cx-12),round(cy-12)))
        alpha=round(255*max(0,min(1,(progress-.65)/.35)))
        if alpha:
            overlay=Image.new('RGBA',(WIDTH,max(height,math.ceil(layout.height))))
            header=self.image(HEADER);d=ImageDraw.Draw(header)
            self.text(d,37,9,'arizdot',13,'#f5f5f7',True)
            label=f'{len(model.cards)} '+LABELS[language]['tasks']
            if len(model.cards)>PAGE:label=f'{model.offset+1}–{model.offset+len(model.visible)} / {len(model.cards)}'
            self.text(d,WIDTH-90,10,label,11,'#b7c5da')
            overlay.alpha_composite(header.resize((WIDTH,HEADER),Image.Resampling.LANCZOS))
            for item,(_,top,_) in zip(model.visible,layout.rows):
                overlay.alpha_composite(self.row(item,item.ref==model.expanded,item.ref==hovered,language),(0,round(top)))
                if item.ref==model.expanded and reveal>0:
                    details,model.detail_scroll=self.details(item,language,model.detail_scroll)
                    visible=max(1,round(DETAIL*reveal))
                    overlay.alpha_composite(details.crop((0,0,WIDTH,visible)),(0,round(top+ROW)))
            footer=self.image(FOOTER);d=ImageDraw.Draw(footer)
            note=translate(error if isinstance(error,str) else 'Söhbət açıla bilmədi · yenidən yoxlayın',language) if error else LABELS[language]['hint']
            self.text(d,24,5,self.fit(note,WIDTH-48,11),11,'#aeb8ca')
            overlay.alpha_composite(footer.resize((WIDTH,FOOTER),Image.Resampling.LANCZOS),(0,round(layout.height-FOOTER)))
            overlay=overlay.crop((0,0,WIDTH,height))
            overlay.putalpha(ImageChops.multiply(overlay.getchannel('A'),image.getchannel('A')).point([round(n*alpha/255) for n in range(256)]))
            image=Image.alpha_composite(image,overlay)
        if any(aligned):
            d=ImageDraw.Draw(image)
            if aligned[0]:d.line((WIDTH//2,1,WIDTH//2,height-2),fill='#407b69')
            if aligned[1]:d.line(((WIDTH-width)/2+1,height/2,(WIDTH+width)/2-2,height/2),fill='#407b69')
        return image
