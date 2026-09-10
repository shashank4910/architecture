"""Bounded, resumable catalogue search with strict quotas and no padding."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
from .catalog_diversity import DiversityIndex,geometry_key,family_key,role
from .catalog_validation import validate_catalog_plan

# The CP-SAT solver (ortools) and its assembly step are only needed when a live
# search runs. Import them lazily so read_config / group_key / spec_key and the
# render gate stay importable for pure-Python tests without ortools installed.
def solve_layout(*a,**k):
 from .bulk_layouts import solve_layout as _f;return _f(*a,**k)

def assemble_layout(*a,**k):
 from .bulk_assembly import assemble_layout as _f;return _f(*a,**k)

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_TARGETS=ROOT/'data/catalog_targets.json'

def group_key(p):
 return (p['plot']['width_ft'],p['plot']['depth_ft'],p['bedrooms'],any(role(r)=='store' for r in p['rooms']))

def spec_key(g):return (g['width'],g['depth'],g['bedrooms'],g['store'])

def read_config(path=DEFAULT_TARGETS):
 cfg=json.loads(Path(path).read_text());groups=cfg['groups']
 if any(g['count']<0 for g in groups):raise ValueError('Negative quota count')
 if sum(g['count'] for g in groups)!=cfg['total']:raise ValueError('Quota total mismatch')
 if sum(g['count'] for g in groups if g['store'])!=cfg['store_total']:raise ValueError('Store quota mismatch')
 if len({spec_key(g) for g in groups})!=len(groups):raise ValueError('Duplicate quota group')
 return cfg


def _renderer_hash():
 return __import__('hashlib').sha256(b''.join((Path(__file__).parent/n).read_bytes() for n in ('renderer_2d.py','curated_furniture.py','openings.py'))).hexdigest()


def _content_hash(p):
 # Canonical content fingerprint, independent of review/status/id bookkeeping.
 payload={k:v for k,v in p.items() if k not in ('catalog_status','review','generation_source','design_id','layout_family','layout_strategy','nearest_accepted_similarity','content_hash','renderer_hash')}
 return __import__('hashlib').sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

def _job(g,seed,seconds,hint=None):
 raw=solve_layout(g['width'],g['depth'],g['bedrooms'],g['store'],seed,seconds,hint=hint)
 p,error=assemble_layout(raw,g['width'],g['depth'],g['bedrooms'],g['store'],seed)
 return p,error,raw

def generate_catalog(requested=300,*,root=None,max_attempts=120,seconds=8,workers=2,config_path=DEFAULT_TARGETS,progress=None):
 cfg=read_config(config_path)
 if requested!=cfg['total']:raise ValueError('Use an explicit target config for a different catalogue size; quotas are never silently truncated')
 if max_attempts<0 or not 1<=workers<=8 or seconds<=0:raise ValueError('Invalid search bounds')
 root=Path(root or ROOT/'generated/catalog_v2');plans_dir=root/'plans';plans_dir.mkdir(parents=True,exist_ok=True)
 state_path=root/'search_state.json';state=json.loads(state_path.read_text()) if state_path.exists() else {}
 seed=state.get('next_seed',1000);rejected=Counter(state.get('rejected',{}));attempted=state.get('attempted',0)
 index=DiversityIndex(cfg['near_duplicate_threshold'],cfg['max_per_layout_family']);accepted=[];counts=Counter();hints={}
 quota={spec_key(g):g['count'] for g in cfg['groups']}
 renderer_hash=_renderer_hash();seed_attempts=state.get('bootstrap_attempts',0);solver_attempts=state.get('solver_attempts',0)
 def accept(p,origin,source_path=None):
  key=group_key(p)
  if key not in quota:return 'quota_no_such_group'
  if counts[key]>=quota[key]:return 'quota_full'
  result=validate_catalog_plan(p)
  if result['overall']!='PASS':return 'quality:'+result['errors'][0]
  reason,score=index.check(p)
  if reason:return reason
  design_id=f"plan_{int(key[0])}x{int(key[1])}_{key[2]}bhk_{'store_' if key[3] else ''}{geometry_key(p)[:12]}"
  target=plans_dir/(design_id+'.json')
  # A resumed file whose canonical content hashes to a different deterministic
  # filename would clobber another entry. Refuse rather than silently rename.
  if source_path is not None and Path(source_path).name!=target.name and target.exists():
   return f'filename_collision: {Path(source_path).name} maps to existing {target.name}'
  content_hash=_content_hash(p)
  # Preserve review evidence when canonical content is unchanged; invalidate only
  # when content or the renderer source changes.
  # Fail-closed on purpose: a plan that carries a `review` block but has NO stored
  # content_hash/renderer_hash (e.g. a file predating this scheme, or a review
  # annotated out-of-band) cannot have its approval verified against the current
  # geometry + renderer, so prior_review resolves to None and the plan reverts to
  # awaiting_visual_review on resume. Dropping an unverifiable/stale approval is
  # the safe direction; a human re-review re-establishes it with matching hashes.
  prior_review=p.get('review') if p.get('content_hash')==content_hash and p.get('renderer_hash')==renderer_hash else None
  p['design_id']=design_id
  p['layout_family']=family_key(p);p['layout_strategy']=f"{key[2]} BHK / {'combined living-dining' if any(r.get('combined_living_dining') for r in p['rooms']) else 'separate living and dining'} / {'with usable store' if key[3] else 'no store'}"
  p['generation_source']=p.get('generation_source',origin) if source_path is not None else origin
  p['nearest_accepted_similarity']=round(score or 0,4);p['content_hash']=content_hash;p['renderer_hash']=renderer_hash
  if prior_review is not None:
   p['review']=prior_review;p['catalog_status']=p.get('catalog_status','awaiting_visual_review')
  else:
   p['catalog_status']='awaiting_visual_review';p.pop('review',None)
  index.add(p);counts[key]+=1;accepted.append(p)
  target.write_text(json.dumps(p,indent=2)+'\n')
  return None
 # Existing JSON is revalidated and deduplicated on every resume. Never delete old work.
 for path in sorted(plans_dir.glob('*.json')):
  try:
   p=json.loads(path.read_text())
  except json.JSONDecodeError as exc:
   raise ValueError(f'Cannot resume: malformed JSON in {path.name} (line {exc.lineno}, col {exc.colno}): {exc.msg}')
  error=accept(p,p.get('generation_source','resumed'),source_path=path)
  if error:raise ValueError(f'Cannot resume with invalid/duplicate/out-of-quota plan {path.name}: {error}')
 seeds_path=ROOT/'data/structural_seeds.json'
 if not state.get('structural_seeds_checked') and seeds_path.exists():
  for n,g in enumerate(json.loads(seeds_path.read_text())):
   p,error=assemble_layout(g['raw'],g['width'],g['depth'],g['bedrooms'],g['store'],100+n);seed_attempts+=1
   if p:
    error=accept(p,'authored structural seed, same validation gate')
    hints[spec_key(g)]=g['raw']
   if error:rejected[error]+=1
  state['structural_seeds_checked']=True
 # Reuse known feasible geometry as a solver hint; it still must pass diversity.
 for p in accepted:
  hints[group_key(p)]={'rooms':{r['id']:[r[k] for k in ('x_ft','y_ft','width_ft','depth_ft')] for r in p['rooms']}}
 def save():
  groups=[dict(g,accepted=counts[spec_key(g)],shortfall=g['count']-counts[spec_key(g)]) for g in cfg['groups']]
  by_size=Counter();store_count=0
  for p in accepted:
   k=group_key(p);by_size[f'{int(k[0])}x{int(k[1])}']+=1;store_count+=k[3]
  summary=dict(requested=cfg['total'],accepted=len(accepted),status='READY_FOR_VISUAL_REVIEW' if len(accepted)==cfg['total'] else 'INCOMPLETE',production_ready=False,attempted=attempted,bootstrap_attempts=seed_attempts,solver_attempts=solver_attempts,rejected=dict(rejected),counts_by_plot_size=dict(by_size),store_utility=store_count,store_target=cfg['store_total'],groups=groups,near_duplicate_threshold=index.threshold,max_per_layout_family=index.family_limit,distinct_families=len(index.families),visual_review='pending; numerical PASS is not catalogue approval')
  (root/'generation_report.json').write_text(json.dumps(summary,indent=2)+'\n')
  state.update(next_seed=seed,attempted=attempted,bootstrap_attempts=seed_attempts,solver_attempts=solver_attempts,rejected=dict(rejected));state_path.write_text(json.dumps(state,indent=2)+'\n')
  return summary
 save();cursor=state.get('group_cursor',0)
 with ThreadPoolExecutor(max_workers=workers) as pool:
  remaining_attempts=max_attempts
  while remaining_attempts>0 and len(accepted)<cfg['total']:
   jobs=[]
   for _ in range(min(workers,remaining_attempts)):
    pending=[g for g in cfg['groups'] if counts[spec_key(g)]<g['count']]
    g=pending[cursor%len(pending)];cursor+=1;current=seed;seed+=1
    jobs.append((g,current,pool.submit(_job,g,current,seconds,hints.get(spec_key(g)))))
   for g,current,future in jobs:
    p,error,raw=future.result();attempted+=1;solver_attempts+=1;remaining_attempts-=1
    if 'rooms' in raw:hints[spec_key(g)]=raw
    if p:error=accept(p,f'CP-SAT seed {current}')
    if error:rejected[error]+=1
   state['group_cursor']=cursor;summary=save()
   if progress:progress({'accepted':len(accepted),'attempted':attempted,'target':cfg['total']})
 return {'plans':accepted,'summary':save(),'root':str(root)}


def write_catalog_outputs(root,catalog,*,preview=None,config_path=DEFAULT_TARGETS):
 from .catalog_outputs import render_catalog
 return render_catalog(Path(root),catalog,preview=preview,config_path=config_path)


def generate_and_write_catalog(root=None,config_path=DEFAULT_TARGETS):
 catalog=generate_catalog(root=root,config_path=config_path)
 if catalog['summary']['accepted']!=catalog['summary']['requested']:
  raise RuntimeError('Catalogue incomplete; see generation_report.json. No duplicate padding or unreviewed bulk render.')
 # Independently re-verify per-group quotas from config; never trust summary['accepted'].
 from .catalog_outputs import verify_group_quotas
 mismatched=verify_group_quotas(catalog['plans'],config_path)
 if mismatched:
  raise RuntimeError(f'Refusing render: per-group quota mismatch {mismatched}. No unreviewed bulk render on a wrong-quota bank.')
 return {'catalog':catalog,'report':write_catalog_outputs(Path(catalog['root']),catalog,config_path=config_path)}
