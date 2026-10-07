"""畫面對拍共用：checks 的鍵格式
  "eid"        → 文字須等於 want（want=None 表示該元素必須隱藏）
  "eid#sub"    → 副標須等於 want
  "eid@x"／"eid@y"／"eid@w"／"eid@h" → 位置／尺寸數值須相等（卡片移動、槽位、節點座標）
  "eid%color"  → 顏色須等於 want
"""

def apply_patch(cur, o):
    for eid, patch in o["set"].items():
        cur[eid] = {**cur.get(eid, {}), **patch}


def key_of(o):
    return (o.get("at", 0) if "at" in o else 0) + o.get("dt", 0) / 100


def _visible(cur):
    return {e: p for e, p in cur.items() if p.get("opacity", 1) > 0}


def check_key(cur, key, want):
    if key.startswith("set:"):          # 可見元素（id 前綴）的後綴集合
        pre = key[4:]
        return sorted(e[len(pre):] for e in _visible(cur) if e.startswith(pre)) == sorted(want)
    if key.startswith("seq:"):          # 可見卡片依軸排序後的文字序列（axis=x 由左到右；y 由下到上）
        _, pre, axis = key.split(":")
        items = [(p.get(axis, 0), p.get("text", "")) for e, p in _visible(cur).items() if e.startswith(pre)]
        items.sort(key=lambda t: t[0], reverse=(axis == "y"))
        return [t for _, t in items] == list(want)
    if key.startswith("pos:"):          # 卡片位置：{eid: [x,y]}
        return all(abs(float(cur.get(e, {}).get("x", -9e9)) - xy[0]) < 1e-6 and abs(float(cur.get(e, {}).get("y", -9e9)) - xy[1]) < 1e-6 for e, xy in want.items())
    if "@" in key:
        eid, k = key.split("@")
        got = cur.get(eid, {}).get(k)
        return got is not None and abs(float(got) - float(want)) < 1e-6
    if "%" in key:
        eid, _ = key.split("%")
        return cur.get(eid, {}).get("color") == want
    if "#" in key:
        eid, _ = key.split("#")
        g = cur.get(eid, {})
        return g.get("sub") == want and g.get("opacity", 1) > 0
    g = cur.get(key)
    if want is None:
        return g is None or g.get("opacity", 1) == 0
    return g is not None and g.get("text") == want and g.get("opacity", 1) > 0


def got_of(cur, key):
    if key.startswith("set:"):
        pre = key[4:]; return sorted(e[len(pre):] for e in _visible(cur) if e.startswith(pre))
    if key.startswith("seq:"):
        _, pre, axis = key.split(":")
        items = [(p.get(axis, 0), p.get("text", "")) for e, p in _visible(cur).items() if e.startswith(pre)]
        items.sort(key=lambda t: t[0], reverse=(axis == "y")); return [t for _, t in items]
    if key.startswith("pos:"):
        return "(位置不符)"
    if "@" in key: eid, k = key.split("@"); return cur.get(eid, {}).get(k)
    if "%" in key: return cur.get(key.split("%")[0], {}).get("color")
    if "#" in key: return cur.get(key.split("#")[0], {}).get("sub")
    g = cur.get(key); return None if g is None else (g.get("text") if g.get("opacity", 1) > 0 else None)
