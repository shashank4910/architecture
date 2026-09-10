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
            east=f.get('head')=='east'
            if east:
                draw.rectangle(box(x+w-.2,y,.2,d),fill='#b9a484')
                draw.rounded_rectangle(box(x+w-1.1,y+.25,.7,d-.5),radius=4,fill='#f7f3e9',outline='#aaa08e')
                line([(x+1.5,y),(x+1.5,y+d)])
            else:
                draw.rectangle(box(x,y+d-.2,w,.2),fill='#b9a484')
                for xx in (x+.3,x+w/2+.15):draw.rounded_rectangle(box(xx,y+d-1,w/2-.45,.65),radius=4,fill='#f7f3e9',outline='#aaa08e')
                line([(x,y+1.5),(x+w,y+1.5)])
        elif k=='sofa':
            for n in range(3):draw.rounded_rectangle(box(x+.5,y+.25+n*(d-.5)/3,w-.7,(d-.5)/3-.12),radius=5,outline='#aaa08e',width=2)
        elif k=='car':
            draw.rounded_rectangle(box(x+.35,y+2,w-.7,3),radius=7,fill='#c6d3da',outline='#8d867c')
            draw.rounded_rectangle(box(x+.35,y+d-3.5,w-.7,2),radius=5,fill='#c6d3da',outline='#8d867c')
            for xx in (x,x+w-.25):
                for yy in (y+2,y+d-3):draw.rectangle(box(xx,yy,.25,1.1),fill='#504e4a')
        elif k=='wardrobe':
            line([(x+w/2,y),(x+w/2,y+d)])
        elif k=='shower':
            line([(x,y),(x+w,y+d)]);line([(x+w,y),(x,y+d)])
            draw.ellipse(box(x+w/2-.12,y+d/2-.12,.24,.24),fill='#7c9fa8')
        elif k=='wc':
            draw.rectangle(box(x+.1,y+.1,w-.2,.6),fill='#fafafa',outline='#99a9ad')
            draw.ellipse(box(x+.1,y+.55,w-.2,d-.7),fill='#fafafa',outline='#99a9ad',width=2)
        elif k=='sink':draw.ellipse(box(x+.15,y+.15,w-.3,d-.3),fill='#fafafa',outline='#99a9ad',width=2)
        elif k=='counter':
            if w>d:
                for xx in (x+2,x+2.65):
                    for yy in (y+.55,y+1.25):draw.ellipse(box(xx,yy,.35,.35),outline='#56504a',width=2)
            else:
                # Keep the sink symbol inside short, explicitly authored counters.
                sink_depth = min(1.4, d - .4)
                sink_offset = min(2, d - sink_depth - .2)
                if w > .5 and sink_depth > 0:
                    draw.rounded_rectangle(box(x+.25,y+sink_offset,w-.5,sink_depth),radius=4,fill='#dce8ec',outline='#8d867c')
        elif k=='puja':
            draw.ellipse(box(x+w/2-.15,y+.3,.3,.3),fill='#c07b36')
        elif k=='fridge':line([(x,y+.4),(x+w,y+.4)],width=2)
        elif k=='table':
            draw.rectangle(box(x+.15,y+.15,w-.3,d-.3),outline='#b5a386')
    for st in plan.get('stairs',[]):
        if st.get('layout')!='dogleg':continue
        y=st['flight_y_ft']; run=(st['riser_count']//2-1)*st['going_ft']; w=st['flight_width_ft']
        for j,x in enumerate(st['flight_x_ft']):
            for n in range(st['riser_count']//2):line([(x,y+n*st['going_ft']),(x+w,y+n*st['going_ft'])])
            line([(x,y),(x,y+run)],width=2);line([(x+w,y),(x+w,y+run)],width=2)
            a,b=(y+.4,y+run-.4) if j==1 else (y+run-.4,y+.4)
            line([(x+w/2,a),(x+w/2,b)],'#1f1d1a',2)
            sign=1 if b>a else -1
            line([(x+w/2-.17,b-sign*.3),(x+w/2,b),(x+w/2+.17,b-sign*.3)],'#1f1d1a',2)
