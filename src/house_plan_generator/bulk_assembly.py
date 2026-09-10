"""Turn a feasible room arrangement into explicit canonical geometry and furniture."""
from itertools import combinations
from copy import deepcopy
import random
from .bulk_furnishing import (door_choices,clear_bounds,furnish,staircase,walkable,item,door_zones)
from .concept_review import review_concept,overlap
from .validator import _rect


def attach_items(p,fs,cs):
 for f in fs:
  f['id']=f"{f['room_id']}_{f['kind']}_{len(p['furniture'])+1}"
  p['furniture'].append(f)
 for c in cs:
  c['id']=f"{c['room_id']}_{c['purpose']}_{len(p['clearances'])+1}"
  p['clearances'].append(c)

def add_door(p,d):
 d['id']=f"d_{d['room_id']}_{d['connects_to']}_{len(p['doors'])}"
 p['doors'].append(d)
 return d

def _tree(edges,nodes):
 seen={nodes[0]}
 for _ in nodes:
  for a,b in edges:
   if a in seen:seen.add(b)
   if b in seen:seen.add(a)
 return len(seen)==len(nodes)

def labels(p):
 """Put compact labels in actual empty room floor; do not change the room geometry."""
 for r in p['rooms']:
  x,y,x2,y2=clear_bounds(r,p)
  lines=r['name'].upper().split(' ')
  if len(lines)>1:r['label_lines']=lines
  r['label_font_size']=18;r['dimension_font_size']=11
  lw=min(x2-x-.1,max(len(s) for s in lines)*.4)
  lh=1.8 if len(lines)>1 else 1.35
  obstacles=[_rect(f) for f in p['furniture'] if f['room_id']==r['id']]+door_zones(r,p,1.2)
  candidates=[]
  for ix in range(1,20):
   for iy in range(1,20):
    cx=x+(x2-x)*ix/20;cy=y+(y2-y)*iy/20
    box=(cx-lw/2,cy-lh/2,cx+lw/2,cy+lh/2)
    if box[0]<x or box[2]>x2 or box[1]<y or box[3]>y2:continue
    score=sum(max(0,min(box[2],b[2])-max(box[0],b[0]))*max(0,min(box[3],b[3])-max(box[1],b[1])) for b in obstacles)
    score+=.01*((cx-(x+x2)/2)**2+(cy-(y+y2)/2)**2)
    candidates.append((score,cx,cy))
  if candidates:
   _,cx,cy=min(candidates);r['label_position_ft']=[round(cx,3),round(cy,3)]

def add_windows(p):
 W,D=p['plot']['width_ft'],p['plot']['depth_ft']
 for r in p['rooms']:
  if r['role'] in ('parking','circulation','store'):continue
  x,y,x2,y2=_rect(r)
  sides=[s for s,ok in [('north',y==0),('south',y2==D),('west',x==0),('east',x2==W)] if ok]
  for side in sides:
   span=r['width_ft'] if side in ('north','south') else r['depth_ft'];width=min(4,span-2)
   if r['role']=='bathroom':width=2
   for start in ((span-width)/2,.8,span-width-.8):
    blocked=any(d['room_id']==r['id'] and d['side']==side and min(start+width,d['offset_ft']+d['width_ft'])>max(start,d['offset_ft']) for d in p['doors'])
    if not blocked:
     p['windows'].append(dict(id=f"w_{r['id']}",room_id=r['id'],side=side,offset_ft=start,width_ft=width,sill_height_ft=5 if r['role']=='bathroom' else 3));break
   else:continue
   break

def assemble_layout(raw,width,depth,beds,with_store,seed):
 if 'rooms' not in raw:return None,'solver_'+raw['status'].lower()
 rng=random.Random(seed)
 rooms=[]
 for rid,(x,y,w,d) in raw['rooms'].items():
  role='bedroom' if rid=='master' or rid.startswith('bed') else 'bathroom' if rid.startswith('bath') else 'circulation' if rid.startswith('hall') else rid
  kind='habitable' if role in ('bedroom','living','dining') else role
  name=('Master Bedroom' if rid=='master' else f"Bedroom {rid[3:]}" if role=='bedroom' else 'Common Bath' if role=='bathroom' else 'Lobby' if role=='circulation' else 'Terrace Stair' if role=='staircase' else 'Car Porch' if role=='parking' else role.title())
  rooms.append(dict(id=rid,name=name,kind=kind,role=role,x_ft=x,y_ft=y,width_ft=w,depth_ft=d))
 if raw.get('combined_living_dining'):
  for r in rooms:
   if r['id']=='living':r.update(name='Living Dining',combined_living_dining=True)
 by={r['id']:r for r in rooms};common=[r['id'] for r in rooms if r['role'] in ('living','dining','circulation')]
 edges=[(a,b) for a,b in combinations(common,2) if list(door_choices(by[a],by[b],{'plot':{'width_ft':width,'depth_ft':depth}},kind='open'))]
 trees=[tree for tree in combinations(edges,len(common)-1) if _tree(tree,common)]
 if not trees:return None,'common_topology'
 rng.shuffle(trees)
 base=dict(design_id=f'candidate_{seed}',plot=dict(width_ft=width,depth_ft=depth,facing='north'),floors=1,bedrooms=beds,bathrooms=sum(r['role']=='bathroom' for r in rooms),rooms=rooms,door_offset_convention='start',walls=dict(external_reserve_ft=.75,internal_half_ft=.25),assumptions=[
 'North-facing conceptual full-plot planning envelope. Statutory setbacks have not been deducted.',
 'Side/rear windows assume legally available open air; party-wall sites require redesign.',
 'Interior bathrooms require a designed mechanical exhaust route to the roof; daylight and ventilation remain site-review items.',
 'Wall allowances: 9 in at plot edge, 3 in each side of internal centerlines; printed dimensions are planning cells.',
 'Stair assumes 9 ft floor height, 16 risers and 10 in goings; headroom, structure and upper arrival need local review.',
 'Southwest master and east kitchen are selected Vastu preferences, not a guarantee of full compliance.',
 'Master bed is 5 x 6.5 ft; secondary rooms may use a 3.5 x 6.5 ft single where a double does not fit. Minimum declared bedside space is 1.5 ft.',
 'Automated checks and contact-sheet review do not constitute professional architectural or code approval.'
 ],dimension_note='ROOM SIZES: PLANNING CELLS; CLEAR SIZES ALLOW FOR WALLS',disclaimer='CONCEPT ONLY. Setbacks, ventilation rights, structural design and stair headroom require local review.')
 failure='furniture'
 for attempt in range(10):
  p=deepcopy(base);p.update(doors=[],windows=[],stairs=[],parking=[],furniture=[],clearances=[])
  entry=by[raw['entry']];eb=clear_bounds(entry,p);start=(eb[0]-entry['x_ft']) if attempt%2==0 else eb[2]-entry['x_ft']-3
  p['doors'].append(dict(id='entrance',room_id=entry['id'],side='north',offset_ft=start,width_ft=3,connects_to='exterior',opening_type='swing',hinge='end' if attempt%2 else 'start'))
  park=by['parking'];p['doors'].append(dict(id='car_gate',room_id='parking',side='north',offset_ft=.75,width_ft=park['width_ft']-1.5,connects_to='exterior',opening_type='gate'))
  for a,b in trees[attempt%len(trees)]:
   opts=list(door_choices(by[a],by[b],p,kind='open'));add_door(p,opts[(attempt//len(trees))%len(opts)])
  ok=True
  for r in sorted(rooms,key=lambda r:0 if r['role']=='staircase' else 1):
   if r['id'] in common or r['role']=='parking':continue
   targets=[by[i] for i in common if r['role']!='bathroom' or by[i]['role']=='circulation']
   if r['role']=='store':targets.append(by['kitchen'])
   opts=[d for target in targets for d in door_choices(r,target,p,width=2.75 if r['role'] in ('bathroom','store','kitchen') else 3,kind='open' if r['role'] in ('staircase','kitchen') else 'swing')]
   rng.shuffle(opts);opts.sort(key=lambda d:0 if by[d['connects_to']]['role']=='circulation' else 1)
   chosen=False
   for door in opts:
    add_door(p,door)
    if r['role']=='staircase':
     result=staircase(r,p)
     if result:p['stairs'].append(result);chosen=True;break
    else:
     result=furnish(r,p)
     if result:attach_items(p,*result);chosen=True;break
    p['doors'].pop()
   if not chosen:ok=False;failure='fit_'+r['id'];break
  if not ok:continue
  for rid in common:
   r=by[rid]
   if r['role']=='circulation':continue
   result=furnish(r,p)
   if not result:ok=False;failure='fit_'+rid;break
   fs,cs=result
   if not walkable(r,p,fs):ok=False;failure='walk_'+rid;break
   attach_items(p,fs,cs)
  if not ok:continue
  pb=clear_bounds(park,p);attach_items(p,[item(park,'car',pb[0]+.1,pb[1]+1,5.8,12)],[])
  p['parking']=[dict(id='car_1',room_id='parking',width_ft=park['width_ft'],depth_ft=park['depth_ft'])]
  add_windows(p)
  for r in p['rooms']:
   if r['role']=='bathroom' and not any(w['room_id']==r['id'] for w in p['windows']):r['ventilation']='mechanical_exhaust_to_roof_required'
  labels(p)
  result=review_concept(p)
  if result['errors']:return None,'validation:'+result['errors'][0]
  if bool(any(r['role']=='store' for r in rooms))!=with_store:return None,'store_mismatch'
  return p,None
 return None,failure
