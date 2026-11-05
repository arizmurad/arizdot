"""A compact dot that reveals concurrent work and inline subprocesses."""
import os
import time
import tkinter as tk
from surface import WIDTH,MAX_HEIGHT
from panel import PanelModel,PanelPainter,HEADER


class Island:
    def __init__(self,monitor):
        self.monitor=monitor
        if os.name=='nt':
            import ctypes
            try:ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except (OSError,AttributeError):pass
        self.root=tk.Tk()
        self.root.title('arizdot')
        self.root.overrideredirect(os.environ.get('CODEX_PULSE_FRAMED')!='1')
        self.root.attributes('-topmost',True)
        self.root.configure(bg='#ff00ff')
        self.canvas=tk.Canvas(self.root,bg='#ff00ff',highlightthickness=0,takefocus=True)
        self.canvas.pack(fill='both',expand=True)
        self.drag=None
        self.anchor=None
        self.vertical_centered=False
        self.aligned=(False,False)
        self.hovered=False
        self.hovered_ref=None
        self.focused_ref=None
        self.last_pointer=None
        self.visible_thread=None
        self.hold_open_until=0
        self.forced_open_until=0
        self.error_until=0
        self.open_hint=None
        self.last_paint=None
        self.last_position=None
        self.last_model=-10
        self.click_timer=None
        self.press_target=None
        self.click_reference=None
        self.click_position=None
        self.click_started=0
        self.expand_target=None
        self.panel=PanelModel()
        self.layout=self.panel.layout(0)
        self.painter=PanelPainter()
        from languages import Language
        self.language=Language()
        self.language.poll()
        from activation import Inbox
        self.activation=Inbox()
        self.pending_activation=None
        self.last_activation_check=-10
        from motion import Spring
        self.morph=Spring()
        self.detail_morph=Spring()
        self.canvas.bind('<ButtonPress-1>',self.press)
        self.canvas.bind('<B1-Motion>',self.move)
        self.canvas.bind('<ButtonRelease-1>',self.release)
        self.canvas.bind('<Double-Button-1>',self.open_chat)
        self.canvas.bind('<MouseWheel>',self.wheel)
        self.canvas.bind('<Tab>',self.focus_next)
        self.canvas.bind('<Return>',self.activate_focused)
        self.canvas.bind('<space>',self.activate_focused)
        self.root.bind('<Escape>',self.escape)
        self.canvas.bind('<Button-3>',self.menu)
        self.root.geometry(f'{WIDTH}x{MAX_HEIGHT}+{self.center()-WIDTH//2}+10')
        self.root.update_idletasks()
        from surface import Surface
        self.surface=Surface(self.root)
        self.refresh()

    def hit(self,x,y):
        return self.layout.hit(x,y) if self.morph.value(time.monotonic())>.96 else None

    def reference_at(self,x,y):
        reference=self.hit(x,y)
        if reference:return reference
        if self.morph.value(time.monotonic())>.96 and self.layout.details and 12<=x<=WIDTH-12:
            top,bottom=self.layout.details
            if top<=y<bottom:return self.panel.expanded
        if y<HEADER:return self.visible_thread
        return None

    def press(self,e):
        if self.click_timer:self.root.after_cancel(self.click_timer);self.click_timer=None
        self.canvas.focus_set()
        self.press_target=self.hit(e.x,e.y)
        self.click_reference=self.reference_at(e.x,e.y)
        self.click_position=(e.x_root,e.y_root)
        self.click_started=time.monotonic()
        self.drag=(e.x_root,e.y_root,self.center(),self.root.winfo_y())

    def center(self):return self.anchor if self.anchor is not None else self.root.winfo_screenwidth()//2

    def move(self,e):
        if self.drag:
            x,y,cx,ry=self.drag
            if abs(e.x_root-x)+abs(e.y_root-y)>5:
                from alignment import snap
                visible_height=32+(self.layout.height-32)*self.morph.value(time.monotonic())
                width,height=self.root.winfo_screenwidth(),self.root.winfo_screenheight()
                center,top,horizontal,vertical=snap(cx+e.x_root-x,ry+e.y_root-y,width,height,visible_height)
                self.anchor=max(WIDTH//2+5,min(width-WIDTH//2-5,center))
                self.vertical_centered=vertical
                self.aligned=(horizontal,vertical)
                self.root.geometry(f'+{self.anchor-WIDTH//2}+{max(0,top)}')

    def release(self,e):
        target=self.press_target
        if self.drag and abs(e.x_root-self.drag[0])+abs(e.y_root-self.drag[1])<5 and target and target==self.hit(e.x,e.y):
            self.click_timer=self.root.after(220,lambda:self.toggle_task(target))
        self.drag=None
        self.press_target=None

    def toggle_task(self,reference):
        self.click_timer=None
        if reference not in [c.ref for c in self.panel.visible]:return
        self.expand_target=None if self.expand_target==reference else reference
        if self.expand_target:
            self.panel.expanded=reference
            self.panel.detail_scroll=0
        self.last_paint=None

    def collapse_subprocess(self):
        if self.click_timer:
            self.root.after_cancel(self.click_timer)
            self.click_timer=None
        self.expand_target=None
        self.focused_ref=None
        self.press_target=None

    def wheel(self,e):
        if not e.delta:return
        inside=bool(self.layout.details and self.layout.details[0]<=e.y<self.layout.details[1])
        self.panel.scroll(-1 if e.delta>0 else 1,inside)
        if not self.panel.expanded:self.expand_target=None
        self.last_paint=None
        return 'break'

    def focus_next(self,e=None):
        refs=[c.ref for c in self.panel.visible]
        if refs:self.focused_ref=refs[(refs.index(self.focused_ref)+1)%len(refs)] if self.focused_ref in refs else refs[0]
        self.forced_open_until=time.monotonic()+3
        self.last_paint=None
        return 'break'

    def activate_focused(self,e=None):
        reference=self.focused_ref or self.hovered_ref
        if reference:self.toggle_task(reference)
        return 'break'

    def escape(self,e=None):
        if self.expand_target:self.collapse_subprocess();return 'break'
        self.root.destroy()

    def set_language(self,code):
        self.language.choice=code
        self.language.poll()
        self.last_model=-10
        self.last_paint=None

    def menu(self,e):
        tr=self.language.tr
        menu=tk.Menu(self.root,tearoff=False)
        reference=self.reference_at(e.x,e.y) or self.visible_thread
        menu.add_command(label=tr('Söhbətə qayıt'),command=lambda:self.open_reference(reference))
        if reference and reference.startswith('claude-desktop:'):
            menu.add_command(label='Söhbət linkini bağla…' if self.language.code=='az' else 'Link this task to chat…',command=lambda:self.link_chat(reference))
        languages=tk.Menu(menu,tearoff=False)
        for label,code in ((tr('Avtomatik (Codex)'),'auto'),('English','en'),('Azərbaycan dili','az')):
            languages.add_command(label=('✓ ' if self.language.choice==code else '')+label,command=lambda c=code:self.set_language(c))
        menu.add_cascade(label=tr('Dil'),menu=languages)
        menu.add_separator()
        menu.add_command(label=tr('Bağla'),command=self.root.destroy)
        try:menu.tk_popup(e.x_root,e.y_root)
        finally:menu.grab_release()

    def link_chat(self,reference):
        from tkinter import simpledialog,messagebox
        from navigation import bind_thread
        az=self.language.code=='az'
        while True:
            value=simpledialog.askstring('arizdot · '+('Söhbət linki' if az else 'Chat link'),
                'Bu işin orijinal Claude söhbət linkini əlavə edin:\nhttps://claude.ai/chat/…\n/share/ linki uyğun deyil.' if az else 'Paste this task\'s original Claude chat link:\nhttps://claude.ai/chat/…\nA /share/ link cannot reopen the original conversation.',parent=self.root)
            if value is None:return False
            try:bind_thread(reference,value);return True
            except (OSError,ValueError) as error:messagebox.showerror('arizdot',str(error),parent=self.root)

    def open_reference(self,reference):
        if self.click_timer:self.root.after_cancel(self.click_timer);self.click_timer=None
        from navigation import open_thread
        if reference:
            try:
                result=open_thread(reference)
                if result and result.get('needs_link'):
                    if not self.link_chat(result.get('link_reference',reference)):return
                    result=open_thread(reference)
                self.open_hint=None
                if result and not result.get('exact',True):self.open_hint=result.get('message');self.error_until=time.monotonic()+5
            except (OSError,ValueError):self.open_hint=None;self.error_until=time.monotonic()+5

    def open_chat(self,e=None):
        reference=self.reference_at(e.x,e.y) if e is not None else self.visible_thread
        # The first click can expand a different row and move its header.
        # Keep the original click's identity for the OS double-click gesture.
        if e is not None and self.click_reference and self.click_position and hasattr(e,'x_root'):
            interval=.8
            if os.name=='nt':
                import ctypes
                interval=ctypes.windll.user32.GetDoubleClickTime()/1000+.1
            if time.monotonic()-self.click_started<=interval and max(abs(e.x_root-self.click_position[0]),abs(e.y_root-self.click_position[1]))<=6:
                reference=self.click_reference
        self.press_target=None
        self.drag=None
        self.open_reference(reference)
        return 'break'

    def refresh(self):
        started=time.monotonic()
        try:
            if hasattr(self.monitor,'panel_snapshot'):state,count,sid,entries=self.monitor.panel_snapshot()
            else:
                state,count,sid=self.monitor.poll()
                entries=getattr(self.monitor,'entries',[])
            self.visible_thread=sid or None
            px,py=self.root.winfo_pointerxy()
            now=time.monotonic()
            if now-self.last_activation_check>=.1:
                self.last_activation_check=now
                request=self.activation.poll()
                if request:
                    self.pending_activation=request
                    self.forced_open_until=now+3
                    self.root.deiconify();self.root.lift()
                    if request.get('thread') and hasattr(self.monitor,'follow_thread'):self.monitor.follow_thread(request['thread'])
                    if not 0<=self.center()<self.root.winfo_screenwidth() or not 0<=self.root.winfo_y()<self.root.winfo_screenheight():self.anchor=None;self.vertical_centered=False
            language=self.language.poll()
            if now-self.last_model>=.5:
                self.last_model=now
                interacting=self.hovered or self.drag is not None or self.click_timer is not None or bool(self.expand_target)
                self.panel.update(state,sid,entries,language,preserve_order=interacting)
                if not self.panel.expanded:self.expand_target=None
            reveal=self.detail_morph.aim(bool(self.expand_target),now,.25 if self.expand_target else .20)
            if not self.expand_target and reveal<.002:self.panel.expanded=None
            self.layout=self.panel.layout(reveal)
            previous=self.morph.value(now)
            current_width=32+(WIDTH-32)*previous
            current_height=32+(self.layout.height-32)*previous
            y=self.root.winfo_y() if self.anchor is not None else 10
            if self.vertical_centered:y=round((self.root.winfo_screenheight()-current_height)/2)
            left=self.center()-current_width/2
            inside=left<=px<left+current_width and y<=py<y+current_height
            if inside:
                self.hold_open_until=now+.26
                # Activation's temporary reveal ends after the first visit.
                # It must not override the user's subsequent pointer exit.
                self.forced_open_until=0
            self.hovered=inside or now<self.hold_open_until or now<self.forced_open_until or self.drag is not None
            if not self.hovered:self.collapse_subprocess()
            progress=self.morph.aim(self.hovered,now,.28 if self.hovered else .23)
            if not self.hovered and progress<.002:
                # A new hover starts at the task list, not a previously opened
                # subprocess or an old scroll position.
                self.panel.expanded=None
                self.panel.detail_scroll=0
                self.panel.offset=0
            if self.vertical_centered:y=round((self.root.winfo_screenheight()-(32+(self.layout.height-32)*progress))/2)
            x=self.center()-WIDTH//2
            if (x,y)!=self.last_position:
                self.root.geometry(f'+{x}+{y}')
                self.last_position=(x,y)
            if (px,py)!=self.last_pointer:
                self.last_pointer=(px,py)
                self.focused_ref=None
            if inside:
                self.hovered_ref=self.hit(px-x,py-y)
                self.canvas.configure(cursor='hand2' if self.hovered_ref else '')
            else:self.hovered_ref=None
            focused=self.focused_ref or self.hovered_ref
            spinning=int(now*30) if any(c.working and c.percent is None for c in self.panel.cards) else 0
            paint=(tuple(self.panel.visible),self.panel.expanded,self.panel.detail_scroll,focused,
                   round(progress,4),round(reveal,4),x,y,self.error_until>now,spinning,language,self.drag is not None,self.aligned)
            if paint!=self.last_paint:
                error=(self.open_hint or True) if self.error_until>now else False
                image=self.painter.draw_panel(self.panel,progress,reveal,now,language,focused,error,self.aligned if self.drag else (False,False))
                self.surface.show(image,x,y)
                self.last_paint=paint
            if self.pending_activation and (not self.pending_activation.get('thread') or self.pending_activation['thread']==sid) and progress>.9:
                self.activation.ack(self.pending_activation,sid);self.pending_activation=None
        except (OSError,ValueError):self.visible_thread=None
        elapsed=time.monotonic()-started
        self.root.after(max(1,round((1/60-elapsed)*1000)),self.refresh)

    def run(self):
        try:self.root.mainloop()
        finally:self.surface.close()
