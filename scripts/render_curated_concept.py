"""Render the authored JSON directly; never invoke the layout generator."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from house_plan_generator.concept_review import review_concept
from house_plan_generator.renderer_2d import render_2d

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',type=Path,default=ROOT/'plans/curated/C01_north_20x50_2bhk.json')
    parser.add_argument('--output',type=Path,default=ROOT/'generated/curated/C01')
    args=parser.parse_args(); plan=json.loads(args.plan.read_text()); args.output.mkdir(parents=True,exist_ok=True)
    report=review_concept(plan)
    (args.output/'review.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['errors']:raise SystemExit('\n'.join(report['errors']))
    render_2d(plan,args.output/'floor_plan.png',args.output/'geometry.json')
    print(f"{report['automated_concept_checks']}: {args.output / 'floor_plan.png'}")

if __name__=='__main__':main()
