"""Additional, deliberately bounded checks for authored catalogue concepts.

This is not a code-compliance or professional architectural approval system.
"""
from collections import defaultdict, deque
from .openings import door_interval, door_swing
from .validator import validate_plan, _rect, _touches, _room_category


def overlap(a,b):
    return min(a[2],b[2])-max(a[0],b[0])>1e-6 and min(a[3],b[3])-max(a[1],b[1])>1e-6


def review_concept(plan):
    base=validate_plan(plan)
    errors=list(base['errors']); by={r['id']:r for r in plan['rooms']}
    graph=defaultdict(set); intervals=defaultdict(list); routes={}
    for d in plan['doors']:
        r=by[d['room_id']]; start,end=door_interval(r,d,plan)
        side=d['side']; horizontal=side in {'north','south'}
        span=r['width_ft'] if horizontal else r['depth_ft']
        valid=0<=start<end<=span
        target=by.get(d['connects_to'])
        origin=r['x_ft'] if horizontal else r['y_ft']
        if target:
            lo=max(origin,target['x_ft'] if horizontal else target['y_ft'])
            hi=min(origin+span,(target['x_ft']+target['width_ft']) if horizontal else (target['y_ft']+target['depth_ft']))
            valid=valid and _touches(r,target,side) and origin+start>=lo and origin+end<=hi
            if _room_category(r)=='private' and _room_category(target)=='private':
                errors.append(f"{d['id']}: bedroom-to-bedroom door forbidden, regardless of suite metadata")
        if not valid:errors.append(f"{d['id']}: opening does not fit the actual shared wall")
        else:
            graph[r['id']].add(d['connects_to']);graph[d['connects_to']].add(r['id'])
        intervals[(r['id'],side)].append((start,end,d['id']))
        if d.get('opening_type','swing')=='swing':
            swing=door_swing(r,d,plan)['bounds_ft']
            for f in plan.get('furniture',[]):
                if f['room_id']==r['id'] and overlap(swing,_rect(f)):
                    errors.append(f"{d['id']}: conservative door swing envelope hits {f['id']}")
    for wn in plan['windows']:
        for a,b,i in intervals[(wn['room_id'],wn['side'])]:
            if min(b,wn['offset_ft']+wn['width_ft'])>max(a,wn['offset_ft']):errors.append(f"{i}: overlaps window {wn['id']}")
    for key,items in intervals.items():
        for n,(a,b,i) in enumerate(items):
            for c,d,j in items[n+1:]:
                if min(b,d)>max(a,c):errors.append(f'{i}: overlaps opening {j}')
    # Start only at the actual exterior, never at all common rooms simultaneously.
    for rid,r in by.items():
        queue=deque([('exterior',['exterior'])]); visited=set()
        while queue:
            node,path=queue.popleft()
            if node in visited:continue
            visited.add(node)
            if node==rid:routes[rid]=path;break
            if node!='exterior' and (_room_category(by[node]) in {'private','service'} or by[node]['kind'] in {'parking','staircase'}):continue
            for nxt in sorted(graph[node]):queue.append((nxt,path+[nxt]))
        if rid not in routes:errors.append(f'{rid}: no entrance-rooted route without traversing private/service rooms')
    clear={}; W,D=plan['plot']['width_ft'],plan['plot']['depth_ft']
    ext=plan['walls']['external_reserve_ft']; half=plan['walls']['internal_half_ft']
    for rid,r in by.items():
        x,y,x2,y2=_rect(r)
        bounds=(x+(ext if x==0 else half),y+(ext if y==0 else half),x2-(ext if x2==W else half),y2-(ext if y2==D else half))
        clear[rid]={'width_ft':round(bounds[2]-bounds[0],3),'depth_ft':round(bounds[3]-bounds[1],3)}
        if r['kind']=='circulation' and min(clear[rid].values())<3:errors.append(f'{rid}: clear passage under 3 ft')
        if _room_category(r)=='private' and min(clear[rid].values())<8:errors.append(f'{rid}: clear bedroom dimension under design target of 8 ft')
        for f in plan.get('furniture',[]):
            if f['room_id']!=rid:continue
            a,b,c,d=_rect(f)
            if a<bounds[0]-1e-6 or b<bounds[1]-1e-6 or c>bounds[2]+1e-6 or d>bounds[3]+1e-6:errors.append(f"{f['id']}: violates reserved wall envelope")
    furniture=plan.get('furniture',[])
    for n,f in enumerate(furniture):
        for other in furniture[n+1:]:
            if overlap(_rect(f),_rect(other)):errors.append(f"{f['id']}: overlaps {other['id']}")
    for c in plan.get('clearances',[]):
        for f in furniture:
            if overlap(_rect(c),_rect(f)):errors.append(f"{c['id']}: use clearance obstructed by {f['id']}")
    for st in plan['stairs']:
        r=by[st['room_id']]; run=(st['riser_count']//2-1)*st['going_ft']
        horizontal=st.get('orientation')=='horizontal'
        length=clear[r['id']]['width_ft' if horizontal else 'depth_ft']
        breadth=clear[r['id']]['depth_ft' if horizontal else 'width_ft']
        if run+2*st['landing_ft']>length:errors.append('stair: flights and landings do not fit')
        if 2*st['flight_width_ft']>breadth:errors.append('stair: two flights do not fit')
    accounted=sum(r['width_ft']*r['depth_ft'] for r in by.values())
    if abs(accounted-W*D)>.01:errors.append('unaccounted planning-cell area')
    entrance=next(d for d in plan['doors'] if d['id']=='entrance')
    if entrance['side']!=plan['plot']['facing']:errors.append('entrance/facing mismatch')
    return {'design_id':plan['design_id'],'automated_concept_checks':'FAIL' if errors else 'PASS',
            'errors':errors,'legacy_warnings':base['warnings'],'entrance_routes':routes,'estimated_clear_dimensions':clear,
            'planning_cell_area_sqft':accounted,'circulation_cell_area_sqft':sum(r['width_ft']*r['depth_ft'] for r in by.values() if r['kind']=='circulation'),
            'limitations':plan['assumptions']+['Furniture path widths, full door-to-furniture movement, daylight adequacy and stair headroom require visual/site review; these checks are not an approval.']}
