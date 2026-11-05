"""Antialiased RGBA drawing and native per-pixel Windows composition."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageChops

SCALE=4
WIDTH,HEIGHT=410,174
MAX_HEIGHT=590
FONTS=Path('C:/Windows/Fonts')


class Painter:
    def __init__(self):
        self.fonts={}

    def font(self,size,bold=False):
        key=size,bold
        if key not in self.fonts:
            self.fonts[key]=ImageFont.truetype(str(FONTS/('segoeuib.ttf' if bold else 'segoeui.ttf')),size*SCALE)
        return self.fonts[key]

    @lru_cache(maxsize=256)
    def fit(self,text,width,size=13,bold=False):
        text=' '.join(str(text).split())
        f=self.font(size,bold)
        if f.getlength(text)<=width*SCALE:return text
        while text and f.getlength(text+'…')>width*SCALE:text=text[:-1]
        return text+'…'

    @lru_cache(maxsize=8)
    def content(self,title,badge,pct,current,next_step,note,metrics,health,color):
        overlay=Image.new('RGBA',(WIDTH*SCALE,HEIGHT*SCALE))
        draw=ImageDraw.Draw(overlay)
        def text(x,y,value,size=13,color='#bec0ca',bold=False):
            draw.text((x*SCALE,y*SCALE),value,font=self.font(size,bold),fill=color)
        text(32,8,self.fit(title,WIDTH-146,14,True),14,'#f5f5f7',True)
        text(WIDTH-110,9,badge,12,color,True)
        text(16,34,self.fit(current,WIDTH-32),13)
        text(16,56,self.fit(metrics,WIDTH-32,13),13,'#e2e7ef')
        text(16,78,self.fit(health,WIDTH-32,11),11,color)
        text(16,103,self.fit(next_step,WIDTH-32,11),11,'#9ea7b9')
        summary=note+(f' · {pct}%' if pct is not None else '')
        text(16,146,self.fit(summary,WIDTH-32,11),11,'#9097a6')
        return overlay.resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS)

    def draw(self,state,progress,now,error=False,language='az',aligned=(False,False)):
        image=Image.new('RGBA',(WIDTH*SCALE,HEIGHT*SCALE))
        overlay=None
        d=ImageDraw.Draw(image)
        width=32+(WIDTH-32)*progress
        height=32+(HEIGHT-32)*progress
        left=(WIDTH-width)/2
        def box(a):return tuple(round(v*SCALE) for v in a)
        def line(a,fill,width=2):d.line(box(a),fill=fill,width=width*SCALE)
        def text(x,y,value,size=13,color='#bec0ca',bold=False,alpha=255):
            rgb=tuple(bytes.fromhex(color.lstrip('#')))
            d.text((round(x*SCALE),round(y*SCALE)),value,font=self.font(size,bold),fill=rgb+(alpha,))
        radius=16+6*progress
        d.rounded_rectangle(box((left,0,left+width-1,height-1)),radius=round(radius*SCALE),fill='#08090b')
        color={'green':'#68f0b0','amber':'#ffc56d','red':'#ff7878','gray':'#9fa3ae'}.get(state.live_tone,'#9fa3ae')
        pct=state.percent
        # The same icon moves continuously from the dot to the bar's left edge.
        cx=WIDTH/2+(18-WIDTH/2)*progress
        cy=16+4*progress
        d.ellipse(box((cx-8,cy-8,cx+8,cy+8)),outline='#252832',width=2*SCALE)
        if pct is not None or state.working:
            start=-90 if pct is not None else (now*140)%360
            extent=max(1,min(100,pct)*3.59) if pct is not None else 100
            d.arc(box((cx-8,cy-8,cx+8,cy+8)),start,start+extent,fill=color,width=2*SCALE)
        d.ellipse(box((cx-3,cy-3,cx+3,cy+3)),fill=color)
        # Fade text instead of making it pop in at the end of the morph.
        alpha=round(255*max(0,min(1,(progress-.65)/.35)))
        if alpha:
            from languages import translate
            note=translate(error if isinstance(error,str) else 'Söhbət açıla bilmədi · yenidən yoxlayın',language) if error else state.progress_scope
            freshness={'live':'CANLI' if language=='az' else 'LIVE','stale':'KÖHNƏ' if language=='az' else 'STALE','offline':'ƏLAQƏ YOX' if language=='az' else 'OFFLINE','recorded':'QEYD' if language=='az' else 'RECORDED'}[state.freshness]
            overlay=self.content(state.live_title,freshness,pct,state.current,state.next_step,note,state.live_metrics,state.live_health,color)
            if alpha<255:
                overlay=overlay.copy()
                overlay.putalpha(overlay.getchannel('A').point([round(n*alpha/255) for n in range(256)]))
            if pct is not None:
                line((16,132,WIDTH-16,132),'#252832')
                if pct>0:line((16,132,16+(WIDTH-32)*pct/100,132),color)
            elif state.working:
                import math
                x=16+(WIDTH-78)*(math.sin(now*2.4)+1)/2
                line((x,132,x+46,132),color)
        if aligned[0]:line((WIDTH/2,1,WIDTH/2,height-2),'#407b69',1)
        if aligned[1]:line((left+1,height/2,left+width-2,height/2),'#407b69',1)
        result=image.resize((WIDTH,HEIGHT),Image.Resampling.LANCZOS)
        if overlay is not None:
            if progress<1:
                overlay=overlay.copy()
                overlay.putalpha(ImageChops.multiply(overlay.getchannel('A'),result.getchannel('A')))
            result=Image.alpha_composite(result,overlay)
        return result


class Surface:
    def __init__(self,root):
        u=C.WinDLL('user32',use_last_error=True)
        g=C.WinDLL('gdi32',use_last_error=True)
        self.u,self.g=u,g
        self.flush=C.WinDLL('dwmapi').DwmFlush
        self.flush.argtypes=[]
        self.flush.restype=C.c_long
        u.GetAncestor.argtypes=[W.HWND,W.UINT];u.GetAncestor.restype=W.HWND
        u.GetWindowLongW.argtypes=[W.HWND,C.c_int];u.GetWindowLongW.restype=W.LONG
        u.SetWindowLongW.argtypes=[W.HWND,C.c_int,W.LONG]
        u.GetDC.argtypes=[W.HWND];u.GetDC.restype=W.HDC
        u.ReleaseDC.argtypes=[W.HWND,W.HDC]
        g.CreateCompatibleDC.argtypes=[W.HDC];g.CreateCompatibleDC.restype=W.HDC
        g.SelectObject.argtypes=[W.HDC,W.HGDIOBJ];g.SelectObject.restype=W.HGDIOBJ
        g.DeleteObject.argtypes=[W.HGDIOBJ];g.DeleteDC.argtypes=[W.HDC]
        class Header(C.Structure):
            _fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),('bits',W.WORD),('compression',W.DWORD),('image_size',W.DWORD),('x',W.LONG),('y',W.LONG),('used',W.DWORD),('important',W.DWORD)]
        class Info(C.Structure):_fields_=[('header',Header),('colors',W.DWORD*3)]
        class Blend(C.Structure):_fields_=[('op',C.c_byte),('flags',C.c_byte),('alpha',C.c_ubyte),('format',C.c_byte)]
        self.blend=Blend(0,0,255,1)
        u.UpdateLayeredWindow.argtypes=[W.HWND,W.HDC,C.POINTER(W.POINT),C.POINTER(W.SIZE),W.HDC,C.POINTER(W.POINT),W.DWORD,C.POINTER(Blend),W.DWORD]
        u.UpdateLayeredWindow.restype=W.BOOL
        g.CreateDIBSection.argtypes=[W.HDC,C.POINTER(Info),W.UINT,C.POINTER(C.c_void_p),W.HANDLE,W.DWORD]
        g.CreateDIBSection.restype=W.HBITMAP
        self.hwnd=u.GetAncestor(root.winfo_id(),2)
        u.SetWindowLongW(self.hwnd,-20,u.GetWindowLongW(self.hwnd,-20)|0x80000)
        self.screen=u.GetDC(None)
        self.dc=g.CreateCompatibleDC(self.screen)
        info=Info(Header(C.sizeof(Header),WIDTH,-MAX_HEIGHT,1,32,0,WIDTH*MAX_HEIGHT*4,0,0,0,0))
        self.bits=C.c_void_p()
        self.bitmap=g.CreateDIBSection(self.screen,C.byref(info),0,C.byref(self.bits),None,0)
        if not self.bitmap:raise C.WinError(C.get_last_error())
        self.old=g.SelectObject(self.dc,self.bitmap)

    def show(self,image,x,y):
        if image.width!=WIDTH or not 0<image.height<=MAX_HEIGHT:raise ValueError('Surface image exceeds its buffer')
        r,g,b,a=image.split()
        data=Image.merge('RGBA',(ImageChops.multiply(r,a),ImageChops.multiply(g,a),ImageChops.multiply(b,a),a)).tobytes('raw','BGRA')
        C.memmove(self.bits,data,len(data))
        if not self.u.UpdateLayeredWindow(self.hwnd,self.screen,C.byref(W.POINT(x,y)),C.byref(W.SIZE(image.width,image.height)),self.dc,C.byref(W.POINT(0,0)),0,C.byref(self.blend),2):
            raise C.WinError(C.get_last_error())
        self.flush()

    def close(self):
        self.g.SelectObject(self.dc,self.old)
        self.g.DeleteObject(self.bitmap)
        self.g.DeleteDC(self.dc)
        self.u.ReleaseDC(None,self.screen)
