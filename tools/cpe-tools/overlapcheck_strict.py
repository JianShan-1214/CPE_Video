"""嚴格幾何檢查：與 overlapcheck.py 相同的重放，但 plain 標籤也列入（只豁免 plain 與「同一元件自己的」元素，以及 sl_/pc_ 卡片落槽）。
用法: python3 overlapcheck_strict.py <folder> ；輸出重疊的元素對（含重疊面積）。"""
import json, sys, os
folder = sys.argv[1]
st = json.load(open(folder + '/story.json' if os.path.isabs(folder) else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'public', folder, 'story.json')))
cur = {}; bad = {}; n = 0
box = lambda p: (p['x'], p['y'], p['x'] + p['w'], p['y'] + p['h'])
def fam(e):   # 同一元件群組不互比
    for pre in ('pc_', 'sl_', 'sb_', 'pcap_', 'sn_', 'lb_'): 
        if e.startswith(pre): return 'slots'
    return None
for s in st['scenes']:
    for c in s['cues']:
        for o in sorted(c.get('ops', []), key=lambda o: o.get('at', 0) + o.get('dt', 0) / 100):
            for e, p in o['set'].items(): cur[e] = {**cur.get(e, {}), **p}
        vis = {e: p for e, p in cur.items() if p.get('opacity', 1) > 0 and p.get('shape') != 'line' and 'w' in p and (p.get('text') or p.get('sub') or not p.get('plain'))}
        n += 1; ids = sorted(vis)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                if a.startswith('qf_') or b.startswith('qf_'): continue
                if a.startswith('m_') and b.startswith('m_'): continue   # 同一陣列的多列指標▲（標籤框相疊 4px 屬設計）
                if (a.startswith('gl_') and b.startswith('gn_')) or (b.startswith('gl_') and a.startswith('gn_')): continue   # 邊線端點接在節點上
                if fam(a) == 'slots' and fam(b) == 'slots':
                    pa, pb = a[:2], b[:2]
                    if {pa, pb} == {'sl', 'pc'}: continue
                A, B = box(vis[a]), box(vis[b])
                ov = min(A[2], B[2]) - max(A[0], B[0]), min(A[3], B[3]) - max(A[1], B[1])
                if ov[0] > 1 and ov[1] > 1: bad.setdefault((a, b), (c['id'], ov))
print(folder, 'cues', n, '嚴格重疊', len(bad))
for k, v in list(bad.items())[:25]: print('  ', k, '首見於', v[0], 'ov(w,h)=', v[1])
