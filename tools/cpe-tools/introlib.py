"""introlib.py（CPE-004）：narrate.py extra_scenes 的「新式場景」獨立驗證器（不渲染，純資料檢查）。

新式 extra scene（narration.json 的 extra_scenes[i]）：
  {"after": "" | 基礎場景id, "id": "x1", "title": "題目說明",
   "layout": "concept" | "wide" | "split2" | "fullcode",   # split2（D-020 E2）：左程式（22px、≤58 字元不截）右動畫窗 1020×800；   # fullcode（D-020）：片尾整份程式雙欄（容量 50 行＝每欄 25 列、每行 ≤58 字元，由 narrate.py 檢查）；省略＝沿用舊行為（舊式場景：沿用 base 版面、無 ops）
   "focus": "anim" | "code" | "both",       # 預設 anim
   "no_code": true|false,                   # 預設：layout==concept → true（整場不出現程式碼）
   "allow_overlap": [["intro_a","intro_b"]],# 允許重疊的元素對（例如卡片與其底框）
   "cues": [{"id","text","cap","say","pauseAfter",
             "ops": [{"at":0~1, "dur":秒, "set":{"intro_xxx":{x,y,w,h,text,sub,color,fs,sfs,opacity,...}}}]}]}
舊式場景（沒有 layout/focus/no_code/allow_overlap，cue 也沒有 ops）完全不經過本模組的檢查，行為與以前相同。

驗證項（錯誤碼）：
  LAYOUT 版面只能 concept/wide/split2（及 fullcode）；FOCUS focus 值；OP_FORMAT op 格式（需 at∈[0,1]、set 為 dict、dur>0）；PROP 未知屬性／錯誤列舉值；
  PREFIX 元素 id 必須 intro_ 開頭；ID_CONFLICT 與主流程元素或其他 intro 場景 id 衝突；
  NO_FADE 場尾（最後一個 cue、at≥0.5）沒有把自己的所有元素淡出（opacity=0）；
  RESIDUE 進入其他場景／任何 cue（含程式碼段）時仍有他場 intro 元素可見；
  CODE_VISIBLE no_code 場景出現時程式碼面板已可見（story.revealAll 為真，或在第一個有 lines 的 cue 之後）；
  CODE_LINES no_code 場景的 cue 帶了高亮行；FIRST_N 前 N 場不是 no_code 的 intro 場景；
  FONT 文字有效字級（fs×scale×版面倍率）< 最小像素（預設 32）；BOUNDS 超出舞台；OVERLAP 同時可見元素方塊重疊。
"""
from itertools import combinations

PREFIX = "intro_"
LAYOUTS = ("concept", "wide", "split2")   # split2（D-020 E2）：左程式右動畫；右窗 1020×800，程式面板恆可見（no_code 預設 false，focus 預設 both）
FULLCODE = "fullcode"            # D-020 E1：整份程式雙欄一次秀出的場景（無動畫舞台、不顯示 cap；不能有 ops；no_code 恆為 false）
FOCUSES = ("anim", "code", "both")
COLORS = ("neutral", "yellow", "green", "gray", "red")
SHAPES = ("rect", "circle", "line")
PROPS = {"x", "y", "w", "h", "text", "sub", "color", "dashed", "opacity", "scale", "fs", "sfs", "plain", "shape", "arrow"}
DEFAULT_EL = dict(x=0, y=0, w=170, h=110, text="", sub="", color="neutral", dashed=False, opacity=1, scale=1, fs=40, sfs=26, plain=False, shape="rect", arrow=False)
# 版面倍率與舞台虛擬尺寸（來自 src/story/timeline.ts RECTS 與 Story.tsx；wide 高 580 見該檔註解）
STAGE = {"concept": dict(scale=1.45, w=1200, h=460), "wide": dict(scale=1.2, w=1200, h=580), "split2": dict(scale=0.85, w=1200, h=940)}   # split2：固定模式 0.85 倍；高 940×0.85＝800（右窗高）
FADE_AT_MIN = 0.5


def is_new_style(x):
    return any(k in x for k in ("layout", "focus", "no_code", "allow_overlap")) or any("ops" in c for c in x.get("cues", []))


def make_spec(x):
    layout = x.get("layout", "concept")
    full = layout == FULLCODE
    return dict(id=x["id"], layout=layout, focus=x.get("focus", "code" if full else ("both" if layout == "split2" else "anim")),
                no_code=bool(x.get("no_code", layout == "concept")),
                allow_overlap={frozenset(p) for p in x.get("allow_overlap", [])})


class Report:
    def __init__(self):
        self.ok = self.bad = 0
        self.errors = []     # (code, 位置, 訊息)
        self._seen = set()

    def check(self, cond, code, where, msg):
        key = (code, where, msg)
        if cond:
            self.ok += 1
        elif key not in self._seen:
            self._seen.add(key)
            self.bad += 1
            self.errors.append((code, where, msg))
        return cond

    def lines(self):
        return [f"intro[{c}] {w}: {m}" for c, w, m in self.errors]

    def codes(self):
        return {c for c, _, _ in self.errors}


def _key(o):
    return (o.get("at", 0), 0)


def _op_ok(R, o, where):
    good = isinstance(o, dict) and isinstance(o.get("set"), dict)
    if not R.check(good, "OP_FORMAT", where, "op 必須是含 set(dict) 的物件"):
        return False
    at = o.get("at")
    good = isinstance(at, (int, float)) and not isinstance(at, bool) and 0 <= at <= 1
    R.check(good, "OP_FORMAT", where, f"intro op 必須有 at（0~1，旁白進度比例；排序依 at），目前 at={at!r}")
    if "dur" in o:
        R.check(isinstance(o["dur"], (int, float)) and o["dur"] > 0, "OP_FORMAT", where, f"dur 必須 >0，目前 {o['dur']!r}")
    for eid, patch in o["set"].items():
        if not R.check(isinstance(patch, dict), "OP_FORMAT", where, f"{eid} 的 patch 必須是 dict"):
            continue
        bad = sorted(set(patch) - PROPS)
        R.check(not bad, "PROP", where, f"{eid} 有未知屬性 {bad}（可用 {sorted(PROPS)}）")
        if "color" in patch: R.check(patch["color"] in COLORS, "PROP", where, f"{eid}.color={patch['color']!r} 不在 {COLORS}")
        if "shape" in patch: R.check(patch["shape"] in SHAPES, "PROP", where, f"{eid}.shape={patch['shape']!r} 不在 {SHAPES}")
        if "opacity" in patch: R.check(isinstance(patch["opacity"], (int, float)) and 0 <= patch["opacity"] <= 1, "PROP", where, f"{eid}.opacity 必須 0~1")
    return good


def _boxes_overlap(a, b):
    return min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) > 1 and min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) > 1


def _visible(state):
    return {i: p for i, p in state.items() if p.get("opacity", 1) > 0}


def _geometry(R, spec, where, vis, min_font):
    st = STAGE[spec["layout"]]
    boxed = {}
    for eid, p in vis.items():
        if p["shape"] == "line":
            continue
        boxed[eid] = p
        R.check(p["x"] >= 0 and p["y"] >= 0 and p["x"] + p["w"] <= st["w"] and p["y"] + p["h"] <= st["h"], "BOUNDS", where,
                f"{eid} 超出舞台 {st['w']}×{st['h']}：x={p['x']} y={p['y']} w={p['w']} h={p['h']}")
        k = st["scale"] * p["scale"]
        if p["text"]:
            R.check(p["fs"] * k >= min_font, "FONT", where, f"{eid} 文字有效字級 {p['fs']}×{k:.2f}={p['fs'] * k:.1f}px < {min_font}px")
        if p["sub"]:
            R.check(p["sfs"] * k >= min_font, "FONT", where, f"{eid} 副標有效字級 {p['sfs']}×{k:.2f}={p['sfs'] * k:.1f}px < {min_font}px")
    for a, b in combinations(sorted(boxed), 2):
        if frozenset((a, b)) in spec["allow_overlap"]:
            continue
        R.check(not _boxes_overlap(boxed[a], boxed[b]), "OVERLAP", where, f"{a} 與 {b} 同時可見且方塊重疊")


def verify_intro(story, specs, base_ids, require_no_code_first=0, min_font_px=32):
    """story：narrate 組好的 story dict；specs：{scene_id: spec}；base_ids：主流程所有元素 id 集合。
    回傳 Report。"""
    R = Report()
    scenes = story["scenes"]
    sids = [s["id"] for s in scenes]
    # 以 (scene_idx, cue_idx) 表示「第一個有 lines 的 cue」（渲染器在此 cue 開始才淡入程式碼面板，除非 revealAll）
    first_code_pos = None
    for si, s in enumerate(scenes):
        for ci, c in enumerate(s["cues"]):
            if c.get("lines"):
                first_code_pos = (si, ci); break
        if first_code_pos: break

    # 前 N 場必須是 no_code 的 intro 場景
    for k in range(require_no_code_first):
        sp = specs.get(sids[k]) if k < len(sids) else None
        R.check(bool(sp and sp["no_code"]), "FIRST_N", f"第{k + 1}場", f"require_no_code_first={require_no_code_first}：第 {k + 1} 場必須是 no_code 的 intro 場景（目前是 {sids[k] if k < len(sids) else '(無)'}）")

    state, owner = {}, {}
    for si, sc in enumerate(scenes):
        spec = specs.get(sc["id"])
        if spec:
            _verify_scene(R, sc, spec, si, scenes, state, owner, base_ids, min_font_px, first_code_pos, story)
        else:
            for ci, c in enumerate(sc["cues"]):
                _residue(R, sc["id"], c, state, owner, None)
    # 全程結束後也不得殘留
    left = sorted(i for i, p in _visible(state).items())
    R.check(not left, "RESIDUE", "片尾", f"片尾仍有 intro 元素可見：{left}")
    return R


def _residue(R, sid, cue, state, owner, own):
    foreign = sorted(i for i in _visible(state) if owner.get(i) != own)
    code = bool(cue.get("lines"))
    seen = R.__dict__.setdefault("_res_seen", set())
    if foreign and (tuple(foreign), code) in seen:     # 同一批殘留元素只在「第一個本 cue」與「第一個程式碼段 cue」各報一次，避免洗版
        return
    seen.add((tuple(foreign), code))
    R.check(not foreign, "RESIDUE", f"{sid}/{cue['id']}",
            f"進入{'程式碼段前' if code else '本 cue 前'}仍有 intro 元素未淡出：{foreign}")


def _verify_scene(R, sc, spec, si, scenes, state, owner, base_ids, min_font, first_code_pos, story):
    sid = sc["id"]
    R.check(sc.get("layout") == spec["layout"] and spec["layout"] in LAYOUTS + (FULLCODE,), "LAYOUT", sid, f"layout={spec['layout']!r} 不合法（只支援 {LAYOUTS + (FULLCODE,)}；split／code 屬於程式碼段）")
    R.check(spec["focus"] in FOCUSES, "FOCUS", sid, f"focus={spec['focus']!r} 不在 {FOCUSES}")
    if spec["layout"] == FULLCODE:
        # D-020 E1：fullcode 沒有動畫舞台——不能帶 ops、不能設 no_code；程式面板由渲染器強制顯示（不受 revealAll 影響）
        R.check(not spec["no_code"], "FULLCODE", sid, "fullcode 場景不能 no_code（它就是整份程式）")
        for c in sc["cues"]:
            R.check(not c.get("ops"), "FULLCODE", f"{sid}/{c['id']}", "fullcode 場景的 cue 不得帶 ops（沒有動畫舞台）")
            _residue(R, sid, c, state, owner, sid)
        return
    if spec["layout"] not in LAYOUTS:
        return
    # 程式碼可見性
    if spec["no_code"]:
        R.check(not story.get("revealAll"), "CODE_VISIBLE", sid, "story.revealAll 為真，程式碼面板一開場就顯示；no_code 場景會看到程式碼")
        R.check(first_code_pos is None or (si, len(sc["cues"]) - 1) < first_code_pos, "CODE_VISIBLE", sid, f"此 no_code 場景晚於第一個有高亮行的 cue {first_code_pos}，程式碼已出現")
        for c in sc["cues"]:
            R.check(not c.get("lines"), "CODE_LINES", f"{sid}/{c['id']}", f"no_code 場景的 cue 不得有高亮行 lines={c.get('lines')}")
    ids_here, last_touch, shown = set(), {}, set()
    cues = sc["cues"]
    for ci, c in enumerate(cues):
        _residue(R, sid, c, state, owner, sid)
        ops = [o for o in c.get("ops", [])]
        okops = [(i, o) for i, o in enumerate(ops) if _op_ok(R, o, f"{sid}/{c['id']}#op{i}")]
        for i, o in sorted(okops, key=lambda t: (t[1].get("at", 0) if isinstance(t[1].get("at"), (int, float)) else 0, t[0])):
            where = f"{sid}/{c['id']}#op{i}"
            for eid, patch in o["set"].items():
                if not isinstance(patch, dict):
                    continue
                R.check(eid.startswith(PREFIX), "PREFIX", where, f"元素 id「{eid}」必須以 {PREFIX} 開頭")
                R.check(eid not in base_ids, "ID_CONFLICT", where, f"元素 id「{eid}」與主流程元素衝突")
                other = owner.get(eid)
                R.check(other in (None, sid), "ID_CONFLICT", where, f"元素 id「{eid}」已被 intro 場景 {other} 使用")
                if other in (None, sid):
                    owner[eid] = sid
                ids_here.add(eid)
                state[eid] = {**state.get(eid, DEFAULT_EL), **patch}
                last_touch[eid] = (ci, o.get("at", 0), patch.get("opacity", state[eid]["opacity"]))
            vis_here = {i2: p for i2, p in _visible(state).items() if owner.get(i2) == sid}
            shown |= set(vis_here)
            _geometry(R, spec, where, vis_here, min_font)
    # 場尾淡出
    last_ci = len(cues) - 1
    for eid in sorted(ids_here):
        p = state[eid]
        R.check(p.get("opacity", 1) == 0, "NO_FADE", sid, f"場尾元素 {eid} 未淡出（最終 opacity={p.get('opacity', 1)}）")
        ci, at, op = last_touch[eid]
        if p.get("opacity", 1) == 0 and eid in shown:
            R.check(ci == last_ci and at >= FADE_AT_MIN, "NO_FADE", sid,
                    f"元素 {eid} 的淡出必須在場內最後一個 cue 且 at≥{FADE_AT_MIN}（目前在第 {ci + 1}/{last_ci + 1} 個 cue、at={at}）")


# ── D-020 E1：fullcode 場景對程式碼與停留時間的檢查（narrate.py 呼叫）──
# 容量依幾何計算（不寫死 40）：每欄 floor((bottomMax 975 − y0 140 − 2×pad 4)/行高 33)=25 列，兩欄 50 行；與 timeline.ts／stagefit.FULLCODE 相同（tests_d020 對拍）
FULL_MAX_LINES, FULL_MAX_COLS, FULL_MIN_DWELL = 2 * ((975 - 140 - 2 * 4) // 33), 58, 15.0
CPS, LEAD, PAUSE, SCENE_GAP = 4.3, 0.25, 0.4, 0.5      # 與 scripts/story-build.mjs 的估算常數相同


def _speak_len(t):
    import re
    n = 0
    for ch in re.sub(r"[，。！？；：、「」\s]", "", t):
        n += 1 if "\u4e00" <= ch <= "\u9fff" else 0.5
    return n


def check_fullcode(code, scene, tab=4):
    """回傳 (errors, warnings)。errors：行數 > 容量（50）、任一行 >58 字元（tab 以 4 欄展開）；warnings：估計停留 <15 秒、cue 帶 cap（fullcode 不顯示 cap）。"""
    errs, warns = [], []
    lines = code.rstrip().split("\n") if code.strip() else []
    if len(lines) > FULL_MAX_LINES:
        errs.append(f"fullcode[{scene['id']}] 程式 {len(lines)} 行 > 容量 {FULL_MAX_LINES}：整份程式放不進雙欄（需 CPE BOT 精簡或分段）")
    long_ = [(i + 1, len(l.expandtabs(tab))) for i, l in enumerate(lines) if len(l.expandtabs(tab)) > FULL_MAX_COLS]
    if long_:
        errs.append(f"fullcode[{scene['id']}] {len(long_)} 行超過 {FULL_MAX_COLS} 字元（行:字元數 {long_[:8]}{'…' if len(long_) > 8 else ''}）：24px 雙欄會被截斷；請先排版成每行 ≤{FULL_MAX_COLS}（D2）")
    dwell = sum(_speak_len(c.get("say") or c["text"]) / CPS + LEAD + c.get("pauseAfter", PAUSE) for c in scene["cues"]) + SCENE_GAP
    if dwell < FULL_MIN_DWELL:
        warns.append(f"fullcode[{scene['id']}] 估計停留 {dwell:.1f}s < {FULL_MIN_DWELL:.0f}s（F2 建議 ≥15 秒；請加長總結旁白或 pauseAfter）")
    for c in scene["cues"]:
        if c.get("cap"): warns.append(f"fullcode[{scene['id']}/{c['id']}] 帶了 cap，但 fullcode 不顯示 cap（會被忽略）")
    return errs, warns


# ── D-020 E2：split2 對程式碼的檢查（narrate.py 呼叫；整份程式只檢查一次）──
SPLIT2_MAX_COLS = 58      # 面板內可用 775.6px ≥ 58×13.2（字級 22、每字 0.6em）＝765.6px；與 timeline.ts SPLIT2／stagefit.SPLIT2 相同（tests_d020 對拍）


def check_split2(code, scene_ids, tab=4):
    """回傳 errors：任一行 >58 字元（tab 以 4 欄展開）→ split2 左面板會被截斷（overflow:hidden）。"""
    lines = code.rstrip().split("\n") if code.strip() else []
    long_ = [(i + 1, len(l.expandtabs(tab))) for i, l in enumerate(lines) if len(l.expandtabs(tab)) > SPLIT2_MAX_COLS]
    if not long_: return []
    return [f"split2[{','.join(scene_ids)}] {len(long_)} 行超過 {SPLIT2_MAX_COLS} 字元（行:字元數 {long_[:8]}{'…' if len(long_) > 8 else ''}）：22px 程式面板（820 寬）會被截斷；請先排版成每行 ≤{SPLIT2_MAX_COLS}（D2）"]
