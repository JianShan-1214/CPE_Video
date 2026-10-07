import json,sys
folder=sys.argv[1]; pre=sys.argv[2:] 
from pathlib import Path
st=json.load(open(Path(__file__).resolve().parents[2]/'public'/folder/'story.json'))
cur={}
for s in st['scenes']:
  for c in s['cues']:
    for o in sorted(c.get('ops',[]),key=lambda o:o.get('at',0)+o.get('dt',0)/100):
        for e,p in o['set'].items(): cur[e]={**cur.get(e,{}),**p}
    vis={e:p for e,p in cur.items() if p.get('opacity',1)>0}
    out=[]
    for e in sorted(vis):
        if any(e.startswith(x) for x in pre):
            p=vis[e]; out.append(f"{e}={p.get('text','')}{'/'+str(p['sub']) if p.get('sub') else ''}[{p.get('color','')[0] if p.get('color') else ''}{'d' if p.get('dashed') else ''}]")
    print(c['id'],c['cap'],' '.join(out))
