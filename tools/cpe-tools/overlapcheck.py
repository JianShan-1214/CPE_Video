"""影格幾何檢查（不需渲染）：重放每個 cue 結束時的可見元素，找出矩形互相重疊、超出舞台 1200×460 的元素。
用法: python3 overlapcheck.py <folder>"""
import json,sys
folder=sys.argv[1]
import os
st=json.load(open(folder+'/story.json' if os.path.isabs(folder) else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'public', folder, 'story.json')))
cur={}; bad={}; n=0
def box(p):
    return (p['x'],p['y'],p['x']+p['w'],p['y']+p['h'])
for s in st['scenes']:
  for c in s['cues']:
    for o in sorted(c.get('ops',[]),key=lambda o:o.get('at',0)+o.get('dt',0)/100):
        for e,p in o['set'].items(): cur[e]={**cur.get(e,{}),**p}
    vis={e:p for e,p in cur.items() if p.get('opacity',1)>0 and p.get('shape')!='line' and 'w' in p}
    n+=1
    ids=sorted(vis)
    for e in ids:
        x0,y0,x1,y1=box(vis[e])
        if x0<-1 or y0<-1 or x1>1201 or y1>585: bad.setdefault(('out',e),c['id'])
    for i,a in enumerate(ids):
        for b in ids[i+1:]:
            A,B=box(vis[a]),box(vis[b])
            if (a.startswith('qf_') or b.startswith('qf_')) or (a.startswith('sl_') and b.startswith('pc_')) or (b.startswith('sl_') and a.startswith('pc_')): continue
            if A[0]<B[2]-1 and B[0]<A[2]-1 and A[1]<B[3]-1 and B[1]<A[3]-1:
                # 標籤類 (plain) 與同列元件不計
                if vis[a].get('plain') or vis[b].get('plain'): 
                    if not (a.startswith('o') or b.startswith('o')): continue
                bad.setdefault((a,b),c['id'])
print(folder,'cues',n,'重疊/出界',len(bad))
for k,v in list(bad.items())[:15]: print('  ',k,'首見於',v)
