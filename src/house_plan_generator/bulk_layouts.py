"""Bounded CP-SAT layout search. No mirroring, relabelled padding or silent fallbacks.

One-foot coordinate grid, exact cell coverage, common-area topology and explicit
room-size domains. These are design targets, not statutory building standards.
"""
from ortools.sat.python import cp_model
import random,json,time
from pathlib import Path

def solve_layout(width, depth, beds, store=False, seed=1, timeout=6, hint=None):
 W,D=width,depth
 combined=beds>=3 and (width==20 or seed%2==0)
 rng=random.Random(seed);m=cp_model.CpModel();rooms={};xs=[];ys=[]
 specs=[('parking',[(18,32),(20,32)]),('living',(20,48,20,40,440,1360)),('dining',(16,44,16,32,256,800)),('kitchen',(14,24,16,26,224,600)),('staircase',[(16,26),(26,16)]),('bath1',(12,18,12,18,168,288))]
 if combined:
  specs=[(i,(20,48,30,44,700,1600) if i=='living' else spec) for i,spec in specs if i!='dining']
 for n in range(beds):specs.append(('master' if n==0 else f'bed{n+1}',(20 if n==0 else 18,32,20 if n==0 else 18,32,440 if n==0 else 396,800)))
 specs.append(('hall',(8,60,8,40,64,480)))
 if seed%3==0:specs.append(('hall2',(8,60,8,44,64,400)))
 if store:specs.append(('store',(12,16,12,16,144,224)))
 if width==30 and beds>=3:specs.append(('bath2',(12,18,12,18,168,288)))
 for i,spec in specs:
  if isinstance(spec,list):opts=spec
  else:
   a,b,c,d,lo,hi=spec;opts=[(w,h) for w in range(a,min(b,2*W)+1,2) for h in range(c,min(d,2*D)+1,2) if lo<=w*h<=hi and (i.startswith('hall') or max(w,h)<=(2.75 if i in ('living','dining') else 2.2 if i=='kitchen' else 1.8)*min(w,h))]
   if i.startswith('hall'):opts=[(w,h) for w,h in opts if min(w,h)<=14]
  opts=[(a//2,b//2) for a,b in opts]
  w=m.new_int_var(min(a for a,b in opts),max(a for a,b in opts),i+'w');h=m.new_int_var(min(b for a,b in opts),max(b for a,b in opts),i+'h');a=m.new_int_var(min(a*b for a,b in opts),max(a*b for a,b in opts),i+'a')
  m.add_allowed_assignments([w,h,a],[(u,v,u*v) for u,v in opts]);x=m.new_int_var(0,W,i+'x');y=m.new_int_var(0,D,i+'y');xe=m.new_int_var(0,W,i+'xe');ye=m.new_int_var(0,D,i+'ye');m.add(xe==x+w);m.add(ye==y+h)
  xs.append(m.new_interval_var(x,w,xe,i+'xi'));ys.append(m.new_interval_var(y,h,ye,i+'yi'));rooms[i]=(x,y,w,h,xe,ye,a)
 m.add_no_overlap_2d(xs,ys);m.add(sum(r[6] for r in rooms.values())==W*D)
 park=rooms['parking'];m.add(park[1]==0);m.add(park[0]==(0 if seed%2 else W-9));
 if not seed%2:m.add(park[2]==9)
 m.add(rooms['master'][0]==0);m.add(rooms['master'][5]==D)
 m.add(rooms['kitchen'][4]==W)
 m.add(2*rooms['kitchen'][1]+rooms['kitchen'][3]>=D)
 m.add(sum(r[6] for i,r in rooms.items() if i.startswith('hall')) <= int(W*D*.18))
 entry='living' if width==20 or seed%4 else 'hall';m.add(rooms[entry][1]==0)
 def adjacent(i,j):
  a,b=rooms[i],rooms[j];bits=[]
  for side in range(4):
   bit=m.new_bool_var(f'{i}_{j}_{side}');bits.append(bit)
   if side<2:
    m.add((a[0]==b[4]) if side==0 else (a[4]==b[0])).only_enforce_if(bit)
    m.add(a[1]+4<=b[5]).only_enforce_if(bit);m.add(b[1]+4<=a[5]).only_enforce_if(bit)
   else:
    m.add((a[1]==b[5]) if side==2 else (a[5]==b[1])).only_enforce_if(bit)
    m.add(a[0]+4<=b[4]).only_enforce_if(bit);m.add(b[0]+4<=a[4]).only_enforce_if(bit)
  return bits
 m.add_bool_or(adjacent('hall','living'))
 common=['living','hall']
 if 'dining' in rooms:
  m.add_bool_or(adjacent('dining','living')+adjacent('dining','hall'));common.append('dining')
 if 'hall2' in rooms:
  m.add_bool_or(adjacent('hall2','hall')+(adjacent('hall2','dining') if 'dining' in rooms else []));common.append('hall2')
 for i,r in rooms.items():
  if i in common+['parking']:continue
  options=[j for j in common if not i.startswith('bath') or j.startswith('hall')]
  if i=='store':options.append('kitchen')
  m.add_bool_or([bit for j in options for bit in adjacent(i,j)])
 for i,r in rooms.items():
  if i not in ['master','bed2','bed3','bed4','living','kitchen']:continue
  sides=[]
  for var,target in [(r[0],0),(r[1],0),(r[4],W),(r[5],D)]:
   b=m.new_bool_var(i+'ext'+str(len(sides)));m.add(var==target).only_enforce_if(b);sides.append(b)
  m.add_bool_or(sides)
 # Architecture preferences vary actual arrangement, not facing labels.
 terms=[]
 for i,r in rooms.items():
  tx,ty=rng.randrange(W),rng.randrange(D)
  if i=='master':tx,ty=0,D
  if i=='kitchen':tx=W
  dx=m.new_int_var(0,2*W,i+'dx');dy=m.new_int_var(0,2*D,i+'dy');m.add_abs_equality(dx,2*r[0]+r[2]-2*tx);m.add_abs_equality(dy,2*r[1]+r[3]-2*ty)
  terms.extend([dx,dy])
 for i,values in (hint or {}).get('rooms',{}).items():
  if i in rooms:
   for variable,value in zip(rooms[i][:4],values):m.add_hint(variable,round(value))
 m.minimize(sum(terms));solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=timeout;solver.parameters.num_search_workers=2;solver.parameters.random_seed=seed
 status=solver.solve(m)
 if status not in [cp_model.OPTIMAL,cp_model.FEASIBLE]:return {'status':solver.status_name(status)}
 return {'status':solver.status_name(status),'entry':entry,'combined_living_dining':combined,'rooms':{i:[solver.value(v) for v in r[:4]] for i,r in rooms.items()}}
