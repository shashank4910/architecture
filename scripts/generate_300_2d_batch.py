"""Bounded canonical search, explicit previews, no duplicate padding."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from house_plan_generator.catalog import generate_catalog, write_catalog_outputs

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"generated/catalog_v2")
    parser.add_argument("--max-attempts",type=int,default=120)
    parser.add_argument("--seconds",type=float,default=8)
    parser.add_argument("--workers",type=int,default=2)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--preview",type=int)
    mode.add_argument("--render",action="store_true")
    args=parser.parse_args(argv)
    c=generate_catalog(root=args.output,max_attempts=args.max_attempts,seconds=args.seconds,workers=args.workers,progress=lambda p:print(json.dumps(p),flush=True))
    if args.preview is not None or (args.render and c["summary"]["status"]!="INCOMPLETE"):
        print(json.dumps(write_catalog_outputs(args.output,c,preview=args.preview),indent=2))
    print(json.dumps(c["summary"],indent=2))
    return 2 if c["summary"]["status"]=="INCOMPLETE" else 0

if __name__=="__main__":
    raise SystemExit(main())
