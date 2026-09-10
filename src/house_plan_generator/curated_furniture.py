"""Draw authored furniture footprints, without moving or resizing them."""
def draw_curated_furniture(draw, plan, ox, oy, scale):
    def box(x,y,w,d):return (ox+x*scale,oy+y*scale,ox+(x+w)*scale,oy+(y+d)*scale)
    def line(points,fill='#8d867c',width=1):draw.line([(ox+x*scale,oy+y*scale) for x,y in points],fill=fill,width=width)
    for f in plan['furniture']:
        x,y,w,d=(f[k] for k in ('x_ft','y_ft','width_ft','depth_ft'))
        k=f['kind']; b=box(x,y,w,d)
        fill={'counter':'#c8b798','wardrobe':'#c8b798','table':'#cfbfa4','shower':'#c5dce2','car':'#f1f0e9','tv':'#44413c'}.get(k,'#d9d3c5')
        draw.rounded_rectangle(b,radius=3 if k!='car' else 12,fill=fill,outline='#8d867c',width=2)
        if k=='bed':
            # Headboard sits flush against one wall; pillows tuck against it; a body line
            # marks the foot side. All strictly inside the authored footprint.
            head=f.get('head')
            if head not in ('north','south','east','west'):head='south'
            hb=.2  # headboard slab thickness (ft)
            pl=min(.65,(min(w,d)-.5)/2 if min(w,d)>1 else .3)  # pillow depth (ft)
            if head in ('north','south'):
                # Headboard runs along the full width; pillows sit side by side.
                if head=='north':
                    draw.rectangle(box(x,y,w,hb),fill='#b9a484')
                    py=y+hb+.05;line([(x,y+1.5),(x+w,y+1.5)])
                else:
                    draw.rectangle(box(x,y+d-hb,w,hb),fill='#b9a484')
                    py=y+d-hb-.05-pl;line([(x,y+d-1.5),(x+w,y+d-1.5)])
                pw=max(.2,(w-.9)/2)
                for xx in (x+.3,x+w/2+.15):draw.rounded_rectangle(box(xx,py,pw,pl),radius=4,fill='#f7f3e9',outline='#aaa08e')
            else:
                # Headboard runs along the full depth; pillows stack along depth.
                if head=='west':
                    draw.rectangle(box(x,y,hb,d),fill='#b9a484')
                    px=x+hb+.05;line([(x+1.5,y),(x+1.5,y+d)])
                else:
                    draw.rectangle(box(x+w-hb,y,hb,d),fill='#b9a484')
                    px=x+w-hb-.05-pl;line([(x+w-1.5,y),(x+w-1.5,y+d)])
                ph=max(.2,(d-.9)/2)
                for yy in (y+.3,y+d/2+.15):draw.rounded_rectangle(box(px,yy,pl,ph),radius=4,fill='#f7f3e9',outline='#aaa08e')
        elif k=='sofa':
            # Cushions run along the sofa's long axis so rotated/horizontal sofas read right.
            if w>=d:
                cw=(w-.7)/3
                for n in range(3):draw.rounded_rectangle(box(x+.35+n*(w-.7)/3,y+.25,cw-.12,d-.5),radius=5,outline='#aaa08e',width=2)
            else:
                cd=(d-.7)/3
                for n in range(3):draw.rounded_rectangle(box(x+.25,y+.35+n*(d-.7)/3,w-.5,cd-.12),radius=5,outline='#aaa08e',width=2)
        elif k=='car':
            draw.rounded_rectangle(box(x+.35,y+2,w-.7,3),radius=7,fill='#c6d3da',outline='#8d867c')
            draw.rounded_rectangle(box(x+.35,y+d-3.5,w-.7,2),radius=5,fill='#c6d3da',outline='#8d867c')
            for xx in (x,x+w-.25):
                for yy in (y+2,y+d-3):draw.rectangle(box(xx,yy,.25,1.1),fill='#504e4a')
        elif k=='wardrobe':
            if w>=d:line([(x+w/2,y),(x+w/2,y+d)])
            else:line([(x,y+d/2),(x+w,y+d/2)])
        elif k=='shower':
            line([(x,y),(x+w,y+d)]);line([(x+w,y),(x,y+d)])
            draw.ellipse(box(x+w/2-.12,y+d/2-.12,.24,.24),fill='#7c9fa8')
        elif k=='wc':
            # rotation 0..3 quarter-turns: tank hugs the wall named by the rotation,
            # bowl fills the rest. Footprint (b) is never changed.
            rot=f.get('rotation',0)%4
            tank=.6  # tank slab depth (ft)
            if rot==0:  # tank at top
                draw.rectangle(box(x+.1,y+.1,w-.2,tank),fill='#fafafa',outline='#99a9ad')
                draw.ellipse(box(x+.1,y+.1+tank,w-.2,d-.2-tank),fill='#fafafa',outline='#99a9ad',width=2)
            elif rot==1:  # tank at right
                draw.rectangle(box(x+w-.1-tank,y+.1,tank,d-.2),fill='#fafafa',outline='#99a9ad')
                draw.ellipse(box(x+.1,y+.1,w-.2-tank,d-.2),fill='#fafafa',outline='#99a9ad',width=2)
            elif rot==2:  # tank at bottom
                draw.rectangle(box(x+.1,y+d-.1-tank,w-.2,tank),fill='#fafafa',outline='#99a9ad')
                draw.ellipse(box(x+.1,y+.1,w-.2,d-.2-tank),fill='#fafafa',outline='#99a9ad',width=2)
            else:  # rot==3, tank at left
                draw.rectangle(box(x+.1,y+.1,tank,d-.2),fill='#fafafa',outline='#99a9ad')
                draw.ellipse(box(x+.1+tank,y+.1,w-.2-tank,d-.2),fill='#fafafa',outline='#99a9ad',width=2)
        elif k=='sink':draw.ellipse(box(x+.15,y+.15,w-.3,d-.3),fill='#fafafa',outline='#99a9ad',width=2)
        elif k=='shelves':
            # Parallel shelf lines across the long axis, inside the footprint.
            if w>=d:
                for n in range(1,3):
                    yy=y+n*d/3
                    if yy<y+d:line([(x+.1,yy),(x+w-.1,yy)])
            else:
                for n in range(1,3):
                    xx=x+n*w/3
                    if xx<x+w:line([(xx,y+.1),(xx,y+d-.1)])
        elif k=='counter':
            if w>d:
                # Long horizontal counter: hob burners spaced along the width, kept inside.
                bx=min(x+2,x+w-1);by=min(y+.55,y+d-.9)
                for xx in (bx,min(bx+.65,x+w-.4)):
                    for yy in (by,min(by+.7,y+d-.4)):draw.ellipse(box(xx,yy,.35,.35),outline='#56504a',width=2)
            else:
                # Short / rotated counter: a sink basin fully inside the footprint.
                sink_depth = min(1.4, d - .4)
                sink_offset = min(2, d - sink_depth - .2)
                if w > .5 and sink_depth > 0:
                    draw.rounded_rectangle(box(x+.25,y+sink_offset,w-.5,sink_depth),radius=4,fill='#dce8ec',outline='#8d867c')
        elif k=='puja':
            draw.ellipse(box(x+w/2-.15,y+.3,.3,.3),fill='#c07b36')
        elif k=='fridge':line([(x,y+.4),(x+w,y+.4)],width=2)
        elif k=='table':
            draw.rectangle(box(x+.15,y+.15,w-.3,d-.3),outline='#b5a386')
    def rect_ft(x0,y0,x1,y1,**kw):
        draw.rectangle((ox+x0*scale,oy+y0*scale,ox+x1*scale,oy+y1*scale),**kw)
    for st in plan.get('stairs',[]):
        if st.get('layout')!='dogleg':continue
        if 'clear_bounds_ft' in st and 'orientation' in st:
            _draw_oriented_stair(st,line,rect_ft)
        else:
            _draw_legacy_stair(st,line)


def _draw_legacy_stair(st,line):
    # Legacy C01/C02 vertical dogleg drawing, preserved unchanged.
    y=st['flight_y_ft']; run=(st['riser_count']//2-1)*st['going_ft']; w=st['flight_width_ft']
    for j,x in enumerate(st['flight_x_ft']):
        for n in range(st['riser_count']//2):line([(x,y+n*st['going_ft']),(x+w,y+n*st['going_ft'])])
        line([(x,y),(x,y+run)],width=2);line([(x+w,y),(x+w,y+run)],width=2)
        a,b=(y+.4,y+run-.4) if j==1 else (y+run-.4,y+.4)
        line([(x+w/2,a),(x+w/2,b)],'#1f1d1a',2)
        sign=1 if b>a else -1
        line([(x+w/2-.17,b-sign*.3),(x+w/2,b),(x+w/2+.17,b-sign*.3)],'#1f1d1a',2)


def _draw_oriented_stair(st,line,rect_ft):
    # New bulk stair: draw in a local frame (u along flight run, v across width) then
    # map to plan coordinates via clear_bounds_ft, so horizontal + reverse stairs draw
    # correctly. Nothing here changes the authored footprint (clear_bounds_ft).
    bx,by,bx2,by2=st['clear_bounds_ft']
    horizontal=st['orientation']=='horizontal'
    reverse=bool(st.get('reverse'))
    going=st['going_ft']; fw=st['flight_width_ft']; landing=st.get('landing_ft',3)
    steps=st['riser_count']//2
    run=(steps-1)*going
    # Local frame: u = distance along the run direction; v = across-width.
    span_u=(bx2-bx) if horizontal else (by2-by)

    def to_plan(u,v):
        # u measured from the near bound into the flights; reverse flips the run direction.
        if reverse:u=span_u-u
        return (bx+u,by+v) if horizontal else (bx+v,by+u)

    def pline(pts,fill='#8d867c',width=1):line([to_plan(u,v) for u,v in pts],fill,width)

    # Two flights side by side across the width, with a landing at the start.
    flight_u0=landing
    for j in range(2):
        v0=j*fw
        # Treads run across each flight width at each going step.
        for n in range(steps):
            uu=flight_u0+n*going
            pline([(uu,v0),(uu,v0+fw)])
        # Flight side rails along the run.
        pline([(flight_u0,v0),(flight_u0+run,v0)],width=2)
        pline([(flight_u0,v0+fw),(flight_u0+run,v0+fw)],width=2)
        # Direction arrow: flight 0 goes up-run, flight 1 comes back.
        if j==0:a,b=flight_u0+.4,flight_u0+run-.4
        else:a,b=flight_u0+run-.4,flight_u0+.4
        vc=v0+fw/2
        pline([(a,vc),(b,vc)],'#1f1d1a',2)
        sign=1 if b>a else -1
        pline([(b-sign*.3,vc-.17),(b,vc),(b-sign*.3,vc+.17)],'#1f1d1a',2)
    # Landing rectangle at the entry end, inside the bounds (never past clear_bounds_ft).
    l0=to_plan(0,0);l1=to_plan(landing,2*fw)
    rect_ft(min(l0[0],l1[0]),min(l0[1],l1[1]),max(l0[0],l1[0]),max(l0[1],l1[1]),outline='#8d867c')
