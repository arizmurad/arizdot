def snap(cx,top,width,height,visible_height,threshold=18):
    horizontal=abs(cx-width/2)<=threshold
    vertical=abs(top+visible_height/2-height/2)<=threshold
    return (width//2 if horizontal else cx,
            round((height-visible_height)/2) if vertical else top,
            horizontal,vertical)
