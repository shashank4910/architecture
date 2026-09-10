"""Geometry-based diversity checks; names, IDs, timestamps and style never count."""
import hashlib
import json
from collections import Counter

# numpy backs the raster near-duplicate comparison only. Import it lazily so the
# geometry_key / family_key / role helpers (and modules that import this one)
# remain usable for pure-Python tests in environments without numpy installed.
np=None

def _numpy():
 global np
 if np is None:
  import numpy as _np;np=_np
 return np

ROLES={'bedroom':1,'living':2,'dining':3,'kitchen':4,'bathroom':5,'parking':6,'staircase':7,'circulation':8,'store':9,'puja':10}

def role(r):
 if r.get('role'):return r['role']
 k=r.get('kind','habitable');name=r.get('name','').lower()
 if k=='habitable':
  if 'bedroom' in name:return 'bedroom'
  if 'dining' in name:return 'dining'
  return 'living'
 return 'store' if k in ('store','utility') else k

def raster(plan):
 np=_numpy()
 w,d=plan['plot']['width_ft'],plan['plot']['depth_ft'];grid=np.zeros((round(d*2),round(w*2)),dtype=np.uint8)
 for r in plan['rooms']:
  x,y,x2,y2=[round(v*2) for v in (r['x_ft'],r['y_ft'],r['x_ft']+r['width_ft'],r['y_ft']+r['depth_ft'])]
  grid[y:y2,x:x2]=ROLES.get(role(r),11)
 return grid

def orientations(grid):return (grid,grid[:,::-1],grid[::-1,:],grid[::-1,::-1])

def geometry_key(plan):
 w,d=plan['plot']['width_ft'],plan['plot']['depth_ft'];variants=[]
 for mx,my in ((0,0),(1,0),(0,1),(1,1)):
  data=[]
  for r in plan['rooms']:
   rw,rd=r['width_ft'],r['depth_ft'];x=w-r['x_ft']-rw if mx else r['x_ft'];y=d-r['y_ft']-rd if my else r['y_ft']
   data.append((role(r),round(x,3),round(y,3),round(rw,3),round(rd,3)))
  variants.append(sorted(data))
 canonical=min(variants)
 return hashlib.sha256(json.dumps([w,d,canonical],separators=(',',':')).encode()).hexdigest()

def family_key(plan):
 w,d=plan['plot']['width_ft'],plan['plot']['depth_ft'];by={r['id']:role(r) for r in plan['rooms']};variants=[]
 edges=sorted(tuple(sorted((by[dr['room_id']],by[dr['connects_to']]))) for dr in plan['doors'] if dr['connects_to'] in by)
 for mx,my in ((0,0),(1,0),(0,1),(1,1)):
  zones=[]
  for r in plan['rooms']:
   x=(r['x_ft']+r['width_ft']/2)/w;y=(r['y_ft']+r['depth_ft']/2)/d
   if mx:x=1-x
   if my:y=1-y
   zones.append((role(r),min(2,int(x*3)),min(2,int(y*3))))
  variants.append(sorted(zones))
 return hashlib.sha256(json.dumps([min(variants),edges],separators=(',',':')).encode()).hexdigest()[:16]

class DiversityIndex:
 def __init__(self,threshold=.88,family_limit=8):
  self.threshold=threshold;self.family_limit=family_limit;self.keys=set();self.grids={};self.families=Counter()
 def check(self,plan):
  key=geometry_key(plan);family=family_key(plan);size=(plan['plot']['width_ft'],plan['plot']['depth_ft'])
  if key in self.keys:return 'duplicate_or_mirror',1.0
  if self.families[(size,family)]>=self.family_limit:return 'family_limit',None
  np=_numpy();grid=raster(plan);highest=0
  for old in self.grids.get(size,[]):
   score=max(float(np.mean(g==old)) for g in orientations(grid));highest=max(highest,score)
   if score>=self.threshold:return 'near_duplicate',score
  return None,highest
 def add(self,plan):
  reason,score=self.check(plan)
  if reason:raise ValueError(reason)
  size=(plan['plot']['width_ft'],plan['plot']['depth_ft'])
  self.keys.add(geometry_key(plan));self.grids.setdefault(size,[]).append(raster(plan));self.families[(size,family_key(plan))]+=1
  return score
