"""Explicit furniture and doors for solver candidates; rejects a candidate on failure."""
from collections import deque
from itertools import product
from .concept_review import overlap
from .openings import door_interval, door_swing
from .validator import _rect, _touches

OPPOSITE={'north':'south','south':'north','east':'west','west':'east'}

def clear_bounds(r,p):
 x,y,x2,y2=_rect(r);W,D=p['plot']['width_ft'],p['plot']['depth_ft']
 return (x+(.75 if x==0 else .25), y+(.75 if y==0 else .25), x2-(.75 if x2==W else .25), y2-(.75 if y2==D else .25))

def inside(a,b):return a[0]>=b[0]-1e-7 and a[1]>=b[1]-1e-7 and a[2]<=b[2]+1e-7 and a[3]<=b[3]+1e-7

def item(r,k,x,y,w,d,**kw):return dict(id='',room_id=r['id'],kind=k,x_ft=x,y_ft=y,width_ft=w,depth_ft=d,**kw)

def clearance(r,name,x,y,w,d):return item(r,'clearance',x,y,w,d,purpose=name)

def incoming(r,p):
 by={q['id']:q for q in p['rooms']};out=[]
 for door in p['doors']:
  if door['room_id']==r['id']:out.append(door)
  elif door['connects_to']==r['id']:
   src=by[door['room_id']];s,e=door_interval(src,door,p);side=OPPOSITE[door['side']]
   origin=src['x_ft']-r['x_ft'] if side in ('north','south') else src['y_ft']-r['y_ft']
   out.append(dict(door,room_id=r['id'],side=side,offset_ft=origin+s,width_ft=e-s,connects_to=src['id']))
 return out

def door_choices(r,target,p,width=3,kind='swing'):
 rb=clear_bounds(r,p);tb=clear_bounds(target,p)
 for side in ('north','south','west','east'):
  if not _touches(r,target,side):continue
  axis=0 if side in ('north','south') else 1
  lo=max(rb[axis],tb[axis]);hi=min(rb[axis+2],tb[axis+2]);origin=r['x_ft'] if axis==0 else r['y_ft']
  if hi-lo+1e-6<width:continue
  for start in dict.fromkeys((lo,hi-width,(lo+hi-width)/2,*[lo+.25*n for n in range(int((hi-lo-width)/.25)+1)])):
   for hinge in ('start','end') if kind=='swing' else ('start',):
    yield dict(id='',room_id=r['id'],side=side,offset_ft=round(start-origin,4),width_ft=width,connects_to=target['id'],opening_type=kind,hinge=hinge)

def door_zones(r,p,depth=2.5):
 out=[]
 for d in incoming(r,p):
  b=list(door_swing(r,d,p)['bounds_ft']);x,y,x2,y2=_rect(r)
  if d['side']=='north':b[3]=y+depth
  elif d['side']=='south':b[1]=y2-depth
  elif d['side']=='west':b[2]=x+depth
  else:b[0]=x2-depth
  out.append(tuple(b))
 return out

def valid_furniture(r,p,fs,cs,avoid_doors=True):
 b=clear_bounds(r,p)
 if any(not inside(_rect(f),b) for f in fs+cs):return False
 if any(overlap(_rect(f),_rect(g)) for i,f in enumerate(fs) for g in fs[i+1:]):return False
 if any(overlap(_rect(f),_rect(c)) for f in fs for c in cs):return False
 zones=door_zones(r,p,2.5) if avoid_doors else []
 # Bedrooms/bathrooms keep their full inward swing free; other sides are passage approaches.
 for d in p['doors']:
  if d['room_id']==r['id'] and d.get('opening_type')=='swing':zones.append(door_swing(r,d,p)['bounds_ft'])
 return not any(overlap(_rect(f),z) for f in fs for z in zones)

def _bedroom_width(r,p,bed_width):
 x,y,x2,y2=clear_bounds(r,p);w,d=x2-x,y2-y
 beds=[]
 for head in ('south','north','west','east'):
  if head in ('south','north'):
   if w<bed_width+3 or d<9.5:continue
   bx=x+(w-bed_width)/2;by=y2-6.5 if head=='south' else y
   bed=item(r,'bed',bx,by,bed_width,6.5,head=head)
   cs=[clearance(r,'bedside',bx-1.5,by,1.5,6.5),clearance(r,'bedside',bx+bed_width,by,1.5,6.5),clearance(r,'bedfoot',bx,by-2.5 if head=='south' else by+6.5,bed_width,2.5)]
  else:
   if d<bed_width+3 or w<9.5:continue
   bx=x if head=='west' else x2-6.5;by=y+(d-bed_width)/2
   bed=item(r,'bed',bx,by,6.5,bed_width,head=head)
   cs=[clearance(r,'bedside',bx,by-1.5,6.5,1.5),clearance(r,'bedside',bx,by+bed_width,6.5,1.5),clearance(r,'bedfoot',bx+6.5 if head=='west' else bx-2.5,by,2.5,bed_width)]
  for length in (5,4,3):
   wards=[]
   for wx in (x,x2-length):
    wards.extend([(item(r,'wardrobe',wx,y,length,2),clearance(r,'wardrobe_use',wx,y+2,length,2.5)),(item(r,'wardrobe',wx,y2-2,length,2),clearance(r,'wardrobe_use',wx,y2-4.5,length,2.5))])
   for wy in (y,y2-length):
    wards.extend([(item(r,'wardrobe',x,wy,2,length),clearance(r,'wardrobe_use',x+2,wy,2.5,length)),(item(r,'wardrobe',x2-2,wy,2,length),clearance(r,'wardrobe_use',x2-4.5,wy,2.5,length))])
   for ward,use in wards:
    if valid_furniture(r,p,[bed,ward],cs+[use]):return [bed,ward],cs+[use]
 return None

def bedroom(r,p):
 for width in ((5,) if r['id']=='master' else (5,3.5)):
  result=_bedroom_width(r,p,width)
  if result:return result
 return None

def bathroom(r,p):
 x,y,x2,y2=clear_bounds(r,p);W,D=x2-x,y2-y
 for rot in range(4):
  w,d=(W,D) if rot%2==0 else (D,W)
  for sx in (0,w-3):
   shower=item(r,'shower',sx,d-3,3,3)
   shower_use=clearance(r,'shower_approach',sx,d-5,3,2)
   for wx in (.2,w-1.8):
    wc=item(r,'wc',wx,0,1.6,2.4,rotation=rot);wcuse=clearance(r,'wc_front',wx,2.4,1.6,2)
    for bx,by in ((0,0),(w-1.6,0),(0,2.6),(w-1.6,2.6)):
     sink=item(r,'sink',bx,by,1.6,1.4);sinkuse=clearance(r,'basin_front',bx,by+1.4,1.6,1.5)
     fs,cs=rotate_items([shower,wc,sink],[shower_use,wcuse,sinkuse],x,y,W,D,rot)
     if valid_furniture(r,p,fs,cs,avoid_doors=False):return fs,cs
 return None

def rotate_items(fs,cs,x,y,w,d,quarter):
 # Rotate a local recipe into the room; only furniture rotates, never whole plans.
 out=[]
 for group in (fs,cs):
  result=[]
  for f in group:
   a,b,c,e=f['x_ft'],f['y_ft'],f['width_ft'],f['depth_ft']
   if quarter==0:q=(x+a,y+b,c,e)
   elif quarter==1:q=(x+w-b-e,y+a,e,c)
   elif quarter==2:q=(x+w-a-c,y+d-b-e,c,e)
   else:q=(x+b,y+d-a-c,e,c)
   result.append(dict(f,**dict(zip(('x_ft','y_ft','width_ft','depth_ft'),q))))
  out.append(result)
 return out

def kitchen(r,p):
 x,y,x2,y2=clear_bounds(r,p);W,D=x2-x,y2-y
 for rot in range(4):
  w,d=(W,D) if rot%2==0 else (D,W)
  if w<5.5 or d<7.5:continue
  fs=[item(r,'counter',0,0,w,2),item(r,'counter',w-2,2,2,d-4.5),item(r,'fridge',0,d-2.5,2.5,2.5)]
  cs=[clearance(r,'kitchen_work',0,2,w-2,d-4.5),clearance(r,'fridge_use',0,d-5,2.5,2.5)]
  fs,cs=rotate_items(fs,cs,x,y,W,D,rot)
  if valid_furniture(r,p,fs,cs):return fs,cs
 return None

def living(r,p):
 x,y,x2,y2=clear_bounds(r,p);W,D=x2-x,y2-y
 for rot in range(4):
  w,d=(W,D) if rot%2==0 else (D,W)
  if w<8 or d<7:continue
  for fraction in (.5,.25,.75):
   sy=max(0,min(d-6.2,(d-6.2)*fraction))
   fs=[item(r,'sofa',0,sy,2.8,6.2),item(r,'table',4.3,sy+1.6,1.5,3),item(r,'tv',w-.5,sy+1.1,.5,4)]
   fs,cs=rotate_items(fs,[],x,y,W,D,rot)
   if valid_furniture(r,p,fs,cs):return fs,cs
 return None

def living_dining(r,p):
 x,y,x2,y2=clear_bounds(r,p);W,D=x2-x,y2-y
 for rot in range(4):
  w,d=(W,D) if rot%2==0 else (D,W)
  if w<8.5 or d<14.5:continue
  for tx in (.5,(w-3.5)/2,w-4):
   fs=[item(r,'sofa',0,.3,2.8,6.2),item(r,'table',4.3,1.9,1.5,3),item(r,'tv',w-.5,2.6,.5,4)]
   ty=d-4.45
   fs.append(item(r,'table',tx,ty,3.5,2.5))
   for cx in (tx+.15,tx+2.1):
    for cy in (ty-1.45,ty+2.7):fs.append(item(r,'chair',cx,cy,1.25,1.25))
   fs,cs=rotate_items(fs,[],x,y,W,D,rot)
   if valid_furniture(r,p,fs,cs):return fs,cs
 return None

def dining(r,p):
 x,y,x2,y2=clear_bounds(r,p);W,D=x2-x,y2-y
 for rot in range(4):
  w,d=(W,D) if rot%2==0 else (D,W)
  for tx in (.5,(w-3.5)/2,w-4):
   ty=(d-2.5)/2
   fs=[item(r,'table',tx,ty,3.5,2.5)]
   for cx in (tx+.15,tx+2.1):
    for cy in (ty-1.45,ty+2.7):fs.append(item(r,'chair',cx,cy,1.25,1.25))
   fs,cs=rotate_items(fs,[],x,y,W,D,rot)
   if valid_furniture(r,p,fs,cs):return fs,cs
 return None

def store_room(r,p):
 x,y,x2,y2=clear_bounds(r,p);W,D=x2-x,y2-y
 if min(W,D)<5:return None
 for rot in range(4):
  w,d=(W,D) if rot%2==0 else (D,W)
  fs=[item(r,'shelves',0,0,w,1.25)];cs=[clearance(r,'shelf_use',0,1.25,w,2.5)]
  fs,cs=rotate_items(fs,cs,x,y,W,D,rot)
  if valid_furniture(r,p,fs,cs):return fs,cs
 return None

def staircase(r,p):
 x,y,x2,y2=clear_bounds(r,p);horizontal=r['width_ft']>r['depth_ft']
 w,d=(y2-y,x2-x) if horizontal else (x2-x,y2-y)
 if w<6.5 or d<11.8333:return None
 door=next(dr for dr in p['doors'] if dr['room_id']==r['id'])
 s,e=door_interval(r,door,p);side=door['side'];reverse=False
 if not horizontal:
  if side=='south':reverse=True
  elif side in ('east','west'):
   absolute=r['y_ft']+s
   if absolute>=y2-3-.01:reverse=True
   elif r['y_ft']+e>y+3+.01:return None
 else:
  if side=='east':reverse=True
  elif side in ('north','south'):
   absolute=r['x_ft']+s
   if absolute>=x2-3-.01:reverse=True
   elif r['x_ft']+e>x+3+.01:return None
 return dict(id='main_stair',room_id=r['id'],width_ft=w,depth_ft=d,riser_count=16,entrance_door_id=door['id'],layout='dogleg',floor_height_ft=9,flight_width_ft=3,going_ft=10/12,landing_ft=3,orientation='horizontal' if horizontal else 'vertical',reverse=reverse,clear_bounds_ft=[x,y,x2,y2],flight_x_ft=[x,x2-3],flight_y_ft=y+3)

FUNCTIONS={'kitchen':kitchen,'living':living,'dining':dining,'bathroom':bathroom,'store':store_room,'bedroom':bedroom}

def furnish(r,p):
 return living_dining(r,p) if r.get('combined_living_dining') else FUNCTIONS[r['role']](r,p)

def walkable(r,p,fs):
 """Conservative 2.5-ft square-person grid, joining all door approaches in shared rooms."""
 doors=incoming(r,p)
 if len(doors)<2:return True
 x,y,x2,y2=clear_bounds(r,p);step=.25;radius=1.25
 # Boundary door centers are projected inward by the clearance radius.
 points=[]
 for dr in doors:
  s,e=door_interval(r,dr,p);mid=(s+e)/2
  points.append({'north':(r['x_ft']+mid,y+radius),'south':(r['x_ft']+mid,y2-radius),'west':(x+radius,r['y_ft']+mid),'east':(x2-radius,r['y_ft']+mid)}[dr['side']])
 nx=int((x2-x-2*radius)/step)+1;ny=int((y2-y-2*radius)/step)+1
 if nx<1 or ny<1:return False
 def free(i,j):
  px=x+radius+i*step;py=y+radius+j*step
  return not any(overlap((px-radius,py-radius,px+radius,py+radius),_rect(f)) for f in fs)
 targets=[(max(0,min(nx-1,round((px-x-radius)/step))),max(0,min(ny-1,round((py-y-radius)/step)))) for px,py in points]
 if any(not free(*t) for t in targets):return False
 queue=deque([targets[0]]);seen={targets[0]}
 while queue:
  a,b=queue.popleft()
  for i,j in ((a+1,b),(a-1,b),(a,b+1),(a,b-1)):
   if 0<=i<nx and 0<=j<ny and (i,j) not in seen and free(i,j):seen.add((i,j));queue.append((i,j))
 return all(t in seen for t in targets)
