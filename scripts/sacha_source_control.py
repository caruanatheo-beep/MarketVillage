"""Pause/abandon or resume one research candidate without deleting its proposal."""
import argparse,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from internships_project.city_source_strategy import set_source_pause,source_selection_context
parser=argparse.ArgumentParser()
parser.add_argument('action',choices=['stop','resume','status'])
parser.add_argument('source',nargs='?')
parser.add_argument('--hours',type=float)
parser.add_argument('--reason',default='Arrêt demandé')
args=parser.parse_args()
if args.action=='status':print(source_selection_context(root))
else:
    if not args.source:parser.error('source requise')
    print(json.dumps(set_source_pause(root,args.source,resume=args.action=='resume',
        hours=args.hours,reason=args.reason),ensure_ascii=False))
