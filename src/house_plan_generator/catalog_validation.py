"""Release gate for bulk candidates, separate from numerical legacy PASS flags."""
import math
from .concept_review import review_concept,overlap
from .catalog_diversity import role
from .bulk_furnishing import clear_bounds,inside,walkable,door_zones
from .validator import _rect


def validate_catalog_plan(plan):
 errors=[]
 try:
  for r in plan['rooms']+plan.get('furniture',[])+plan.get('clearances',[]):
   if not all(isinstance(r[k],(int,float)) and not isinstance(r[k],bool) and math.isfinite(r[k]) for k in ('x_ft','y_ft','width_ft','depth_ft')):
    return {'overall':'FAIL','errors':['Non-finite or non-numeric geometry']}
  report=review_concept(plan);errors.extend(report['errors'])
  by={r['id']:r for r in plan['rooms']};furniture=plan.get('furniture',[])
  beds=[r for r in plan['rooms'] if role(r)=='bedroom'];baths=[r for r in plan['rooms'] if role(r)=='bathroom']
  if len(beds)!=plan.get('bedrooms'):errors.append('Declared BHK does not match actual bedrooms')
  if len(baths)!=plan.get('bathrooms'):errors.append('Declared bathroom count does not match actual rooms')
  if plan.get('door_offset_convention')!='start':errors.append('Bulk plans require explicit start offsets and door widths')
  if plan['plot'].get('facing')!='north':errors.append('Current solver supports north-facing plans only; no facing-label transforms')
  for r in plan['rooms']:
   fs=[f for f in furniture if f['room_id']==r['id']];kinds={f['kind'] for f in fs};kind=role(r);b=clear_bounds(r,plan)
   required={'bedroom':{'bed','wardrobe'},'kitchen':{'counter','fridge'},'bathroom':{'wc','sink','shower'},'store':{'shelves'},'living':{'sofa','table'},'dining':{'table','chair'},'parking':{'car'}}.get(kind,set())
   if not required<=kinds:errors.append(f"{r['id']}: missing required furniture {sorted(required-kinds)}")
   if r.get('combined_living_dining') and sum(f['kind']=='chair' for f in fs)<4:errors.append('Combined living/dining lacks four dining chairs')
   if kind=='store' and (min(b[2]-b[0],b[3]-b[1])<5 or (b[2]-b[0])*(b[3]-b[1])<25):errors.append('Store lacks a usable clear 5 ft minimum dimension / 25 sq ft area')
   if kind in ('bedroom','living','kitchen') and not any(w['room_id']==r['id'] for w in plan['windows']):errors.append(f"{r['id']}: no ventilation window")
   if kind=='bathroom' and not any(w['room_id']==r['id'] for w in plan['windows']) and r.get('ventilation')!='mechanical_exhaust_to_roof_required':errors.append('Interior bathroom lacks an explicit ventilation assumption')
   if kind in ('living','dining','circulation'):
    if not walkable(r,plan,fs):errors.append(f"{r['id']}: blocked furnished common route at 2.5 ft design clearance")
   if kind not in ('bathroom','parking','staircase'):
    if any(overlap(_rect(f),z) for f in fs for z in door_zones(r,plan,2.5)):errors.append(f"{r['id']}: furniture blocks an opening approach")
  for c in plan.get('clearances',[]):
   if c['room_id'] not in by or not inside(_rect(c),clear_bounds(by[c['room_id']],plan)):errors.append(f"{c['id']}: clearance extends outside usable room bounds")
  for st in plan['stairs']:
   if st.get('riser_count',0)<=0 or abs(st.get('floor_height_ft',9)/st.get('riser_count',16)-.5625)>.01:errors.append('Stair riser/height differs from the tested concept configuration')
  return dict(report,overall='FAIL' if errors else 'PASS',errors=errors,production_ready=False)
 except (KeyError,TypeError,ValueError,ZeroDivisionError) as exc:
  return {'overall':'FAIL','errors':[f'Malformed canonical plan: {exc}'],'production_ready':False}
