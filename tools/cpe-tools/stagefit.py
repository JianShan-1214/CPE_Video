"""stagefit.py（CPE-003）：舞台自適應放大的「不渲染」推算與警示。

- fit_rects(story)：與 src/story/timeline.ts 的 fitRects 逐式相同（tests_cpe003 用 esbuild 打包 TS 對拍）。
- metrics(story, model)：重放 story.json 的 ops，依各 cue 版面的舞台倍率，推算 1920×1080 成片中各元素的最小像素（A1 各項）。
- fit_warnings(story, rows)：超過上限／未達標時的警示，格式同 coverage.py／detect.py 的 warnings.json 條目（type,name,status,evidence,variables,why,now,missing,eta,message）。
- merge_warnings(folder, ws)：把 stage_fit 警示併入資料夾的 warnings.json（先移除舊的 stage_fit，可重複執行）。
D-012 裁定（EL／CPE BOT；只寫文件、不改程式）：
- F6：副標（sub，成片約 23–25px）不計入 A1「一般文字 ≥26」判定（metrics 另列 text_sub，不進 judge）。
- F8：--layout concept 下 --no-comps（舊模式）的 nocomps 縮放 1.45→1.18 屬舊模式排除項，接受。
- F10：預設 --layout split 未達 A1 時有 type=stage_fit 警示；split 不要求達 A1（CPE BOT 裁定，判定走 relaxed 規則）。
- D-012 新增：type=text_overflow（F5，估算）、元件退化 → A1 項目 n/a（F7）、summary_of／geo_warnings（F3／F4 的 warnings.json 接線）。
model：legacy＝固定 RECTS（舊行為）；fit＝story.stageFit=="auto" 的自適應。
"""
import json, re
from pathlib import Path

# ── 與 timeline.ts 同步的常數 ──
DEFAULT_EL = dict(x=0, y=0, w=170, h=110, text="", sub="", color="neutral", dashed=False, opacity=1, scale=1, fs=40, sfs=26, plain=False, shape="rect", arrow=False)
LEGACY = {  # layout: (stageX, stageY, stageScale)
    "concept": (90, 150, 1.45), "wide": (240, 150, 1.2), "split": (1070, 150, 0.7), "code": (1215, 215, 0.55),
    "fullcode": (1215, 215, 0.55),
    "split2": (866, 150, 0.85)}      # split2（D-020 E2）：固定模式 0.85 倍（1200×0.85＝1020 寬）；stageFit=auto 時用 FIT_REGIONS["split2"]
# fullcode（D-020 E1）：舞台被淡出，數值只供 rect 補間；metrics 對 fullcode cue 一律略過
# D-020 E1：fullcode 雙欄幾何（與 timeline.ts 的 FULLCODE 逐值相同；tests_d020 以 esbuild 對拍）
FULLCODE = dict(fs=24, lh=33, x0=50, colW=900, gap=20, y0=140, titleTop=94, titleH=40, titleFs=32, gutter=46, pad=4, bottomMax=975, maxLines=50, maxCols=58, title="完整程式碼")
# D-020 E2：split2 幾何（與 timeline.ts 的 SPLIT2／RECTS.split2 逐值相同；tests_d020 以 esbuild 對拍）
SPLIT2 = dict(panel=dict(x=24, y=100, w=820, h=852), win=dict(x=856, y=150, w=1040, h=800), fs=22, lh=38, gutterW=1.2, gutterPad=0.5, maxCols=58, visibleLines=22,
              cap=dict(left=856, width=1040, top=104, fontSize=30))
SUBTITLE_TOP_BOX = 983      # 舊 story 字幕框實測 y=983–1056（layoutRev<2）；layoutRev≥2 → 1001–1075
SUBTITLE_TOP_REV2 = 1001
FIT_REGIONS = {  # layout: (rx, ry, rw, rh, min, max)
    "concept": (60, 150, 1800, 680, 0.5, 1.8), "wide": (60, 150, 1800, 710, 0.5, 1.8), "split": (1060, 150, 830, 790, 0.5, 1.4),
    "split2": (866, 150, 1020, 800, 0.5, 1.5)}      # D-020 E2：右窗 1020×800（A2 ≥950×700）
OUT_ROW = re.compile(r"^o\d+$")
OUT_PAD = 40


def _wide(ch): o = ord(ch); return 0x2e80 <= o <= 0x9fff or 0xff00 <= o <= 0xffef


def text_width(t, fs): return sum(1 if _wide(c) else 0.62 for c in t) * fs


def auto_width(eid, w, text, fs): return min(w, text_width(text, fs) + OUT_PAD) if OUT_ROW.match(eid) else w


def extent(eid, p):
    if p["shape"] == "line":
        return (min(p["x"], p["x"] + p["w"]), min(p["y"], p["y"] + p["h"]), max(p["x"], p["x"] + p["w"]), max(p["y"], p["y"] + p["h"]))
    return (p["x"], p["y"], p["x"] + auto_width(eid, p["w"], p["text"], p["fs"]), p["y"] + p["h"])


def op_key(o): return (o["at"] if "at" in o else 0) + o.get("dt", 0) / 100   # 與 verifylib.key_of 相同


def replay(story, layout_map=None):
    """逐 cue 重放。yield (cue, layout, state dict, 每個 op 後的 (eid, props) 清單)。layout_map：把某版面換成另一版面（假設性評估）。"""
    state = {}
    for sc in story["scenes"]:
        for c in sc["cues"]:
            L = c.get("layout") or sc["layout"]
            if layout_map: L = layout_map.get(L, L)
            steps = []
            for _, o in sorted(enumerate(c.get("ops", [])), key=lambda t: (op_key(t[1]), t[0])):
                for eid, patch in o["set"].items():
                    state[eid] = {**state.get(eid, DEFAULT_EL), **patch}
                    steps.append((eid, state[eid]))
            yield c, L, state, steps


def fit_boxes(story, layout_map=None):
    """與 TS fitBoxes 同序：每個 cue 先收「進 cue 時就可見」的全部元素，再收每個 op 後的元素。"""
    boxes, state = {}, {}

    def add(L, b):
        o = boxes.get(L)
        boxes[L] = b if o is None else (min(o[0], b[0]), min(o[1], b[1]), max(o[2], b[2]), max(o[3], b[3]))
    for sc in story["scenes"]:
        for c in sc["cues"]:
            L = c.get("layout") or sc["layout"]
            if layout_map: L = layout_map.get(L, L)
            for eid, p in state.items():
                if p["opacity"] > 0: add(L, extent(eid, p))
            for _, o in sorted(enumerate(c.get("ops", [])), key=lambda t: (op_key(t[1]), t[0])):
                for eid, patch in o["set"].items():
                    state[eid] = {**state.get(eid, DEFAULT_EL), **patch}
                    if state[eid]["opacity"] > 0: add(L, extent(eid, state[eid]))
    return boxes


def fit_rect(L, b):
    g = FIT_REGIONS.get(L)
    if not g: return None
    rx, ry, rw, rh, mn, mx = g
    bw, bh = max(b[2] - b[0], 1), max(b[3] - b[1], 1)
    s = min(mx, max(mn, min(rw / bw, rh / bh)))
    return dict(stageScale=s, stageX=rx + (rw - bw * s) / 2 - b[0] * s, stageY=ry - b[1] * s)


def fit_rects(story, layout_map=None):
    out = {}
    for L, b in fit_boxes(story, layout_map).items():
        r = fit_rect(L, b)
        if r: out[L] = r
    return out


def scale_of(L, rects, model):
    if model == "fit" and L in rects: return rects[L]["stageScale"]
    return LEGACY[L][2]


# ── A1 指標 ──
# 項目：(key, 中文, 門檻 px, 數量上限, 數量說明)
A1 = [
    ("text", "一般文字", 26, None, ""),
    ("slot_h", "槽位卡高", 90, 8, "槽位數"),
    ("node_d", "節點直徑", 64, 10, "節點數"),
    ("node_fs", "節點字", 28, 10, "節點數"),
    ("cell_h", "佇列/堆疊格高", 64, 8, "格數（上限 8 為假設，spec 未寫）"),
]
FLOOR = 0.75   # 內容超過上限時允許縮到門檻的 75%


def _group(eid):
    if eid.startswith("pc_") or eid.startswith("sl_"): return "slot"
    if eid.startswith("gn_") or eid.startswith("tn_"): return "node"
    if eid.startswith("qc_"): return "cell"
    return None


def metrics(story, model="fit", layout_map=None, only=None):
    """回傳 dict：scales{layout:倍率}, min{key:最小像素或None}, count{slot,node,cell}, text_sub 最小副標字級"""
    rects = fit_rects(story, layout_map) if model == "fit" else {}
    mn = dict(text=None, text_sub=None, slot_h=None, node_d=None, node_fs=None, cell_h=None)
    ids = dict(slot=set(), node=set(), cell=set())
    maxsim = dict(slot=0, node=0, cell=0)
    layouts = {}

    def upd(k, v):
        if mn[k] is None or v < mn[k]: mn[k] = v
    for c, L, state, _ in replay(story, layout_map):
        if only and L != only: continue
        if L == "fullcode": continue          # D-020 E1：fullcode 時舞台整個淡出，殘留的舞台元素不算畫面上的元素
        s = scale_of(L, rects, model)
        layouts[L] = s
        sim = dict(slot=0, node=0, cell=0)
        for eid, p in state.items():
            if p["opacity"] <= 0 or p["shape"] == "line": continue
            k = s * p["scale"]
            if p["text"]: upd("text", p["fs"] * k)
            if p["sub"]: upd("text_sub", p["sfs"] * k)
            g = _group(eid)
            if g == "slot": upd("slot_h", p["h"] * k)
            elif g == "node":
                upd("node_d", p["w"] * k)
                if p["text"]: upd("node_fs", p["fs"] * k)
            elif g == "cell": upd("cell_h", p["h"] * k)
            if g:
                ids[g].add(eid)
                if g != "slot" or eid.startswith("sl_"): sim[g] += 1
        for g in sim: maxsim[g] = max(maxsim[g], sim[g])
    count = dict(slot=len({e for e in ids["slot"] if e.startswith("sl_")}), node=len(ids["node"]), cell=maxsim["cell"])
    return dict(scales=layouts, min=mn, count=count, rects=rects)


# D-012（F7）：元件退化（warnings.json 內該元件型態 status=degraded，例如 >20 節點的圖、>15 節點的樹、>10 的槽位配置退回一般陣列格）
# 時，畫面上根本沒有該元素，A1 對應項目不是「達標」而是「n/a（退化）」。型態 → 受影響的 A1 項目
DEGRADE_KEYS = dict(slots=("slot_h",), graph_adj=("node_d", "node_fs"), graph_matrix=("node_d", "node_fs"), tree_array=("node_d", "node_fs"),
                    queue=("cell_h",), stack=("cell_h",), priority_queue=("cell_h",),
                    # D-016（F7）：unsupported 的節點／物件型態（指標式二元樹、鏈結、struct）→ 節點項目 n/a（畫面沒有這些元素）
                    tree_struct=("node_d", "node_fs"), pointer=("node_d", "node_fs"), struct=("node_d", "node_fs"))
# D-016（F7）：其餘 status=degraded／unsupported 的型態（map／set／pair／hash／recursion／union_find／graph_weighted…，含日後新增、不在上表者）
# 視為「未認領」：用旗標 WEAK 表示。judge 時，若該版面四個元件項目（槽位卡高／節點直徑／節點字／格高）一個元素都沒量到
# （畫面完全沒有任何元件），四項一律 n/a（退化），整體不可顯示「達標」；只要有任一元件被量到（例如 bst 的 tree_array 節點，只多一個 recursion 退化警示），
# 照常判定、不被旗標改變（避免把真正達標的樣本誤標 n/a）
DEGRADE_DEFAULT = ("slot_h", "node_d", "node_fs", "cell_h")
WEAK = "*"
DEGRADE_STATUS = ("degraded", "unsupported")
NOT_COMPONENT = ("stage_fit", "text_overflow", "layout_overlap", "truncated")   # stage-fit 自己產的警示與「超過顯示上限」不是元件型態，不影響 n/a


def degraded_keys(warnings):
    """warnings.json 的 warnings 清單 → 因元件退化／未支援而不適用的 A1 項目集合"""
    out = set()
    for w in warnings or []:
        if w.get("status") in DEGRADE_STATUS and w.get("type") not in NOT_COMPONENT:
            if w.get("type") in DEGRADE_KEYS: out |= set(DEGRADE_KEYS[w["type"]])
            else: out.add(WEAK)
    return out


def load_degraded(folder):
    """資料夾的 warnings.json → degraded_keys（沒有檔案＝空集合）"""
    p = Path(folder) / "warnings.json"
    if not p.exists(): return set()
    try: return degraded_keys(json.loads(p.read_text(encoding="utf-8")).get("warnings", []))
    except (ValueError, OSError): return set()


# D-020 E3 退路版（CPE BOT／EL 裁定；完整版 90px 不做）：split2 有槽位（slot）時，槽卡高與一般文字改分級——
#   槽卡高：≥90 全額；68–89 警示通過（pass_floor，需警示）；<68 不達標。 一般文字：≥26 全額；20–25 警示通過；<20 不達標。
# 只限 split2 且該版面有槽位卡；其他版面、其他元件（節點／佇列格）與 split2 無槽位的 story 照舊全額判定。
RETREAT = {"split2": dict(slot_h=68, text=20)}


def retreat_floors(L, m):
    """該版面（metrics 以 only=L 算出）適用的退路下限；無則 None"""
    f = RETREAT.get(L)
    return dict(f) if f and m["count"]["slot"] > 0 else None


def judge(m, relaxed=False, degraded=(), floors=None):
    """A1 逐項判定：status ∈ na／na_degraded（元件退化，無此元素，不算達標）／pass／pass_floor（超過上限但≥75%，需警示）／fail
    relaxed=True（CPE BOT 裁定：split 程式段不要求達 A1）：≥門檻＝pass；≥75% 門檻＝pass_floor（警示）；其餘 fail，與數量上限無關"""
    res = {}
    degraded = set(degraded)
    if WEAK in degraded and all(m["min"][k] is None for k in DEGRADE_DEFAULT): degraded |= set(DEGRADE_DEFAULT)   # D-016（F7）：畫面沒有任何元件＋有未認領型態警示
    cmap = dict(text=None, slot_h="slot", node_d="node", node_fs="node", cell_h="cell")
    for key, zh, thr, lim, _ in A1:
        v = m["min"][key]
        if v is None:
            res[key] = dict(status="na_degraded" if key in degraded else "na", value=None, need=thr, count=None, limit=lim); continue
        n = m["count"][cmap[key]] if cmap[key] else None
        over = lim is not None and n is not None and n > lim
        if relaxed: over = True
        if floors and key in floors:       # D-020 E3 退路：分級（≥門檻 pass；≥退路下限 pass_floor＝警示通過；其餘 fail），與數量上限無關
            st = "pass" if v >= thr - 1e-9 else ("pass_floor" if v >= floors[key] - 1e-9 else "fail")
            res[key] = dict(status=st, value=v, need=thr, count=n, limit=lim, over=False, retreat=floors[key]); continue
        if v >= thr - 1e-9: st = "pass"
        elif over and v >= thr * FLOOR - 1e-9: st = "pass_floor"
        else: st = "fail"
        if over and st == "pass" and not relaxed: st = "pass_over"      # 超過上限但仍達全額門檻
        res[key] = dict(status=st, value=v, need=thr, count=n, limit=lim, over=over)
    return res


NA_DEG = "n/a（元件退化）"


def overall(res):
    bad = [k for k, r in res.items() if r["status"] == "fail"]
    if bad: return "未達標", bad
    return (NA_DEG if any(r["status"] == "na_degraded" for r in res.values()) else "達標"), bad


# ── 警示（warnings.json 條目）──
STRICT_LAYOUTS = ("wide", "concept", "split2")   # D-020（EL 裁定）：split2 判全額 A1（不是 split 的 75% 寬鬆規則）； CPE BOT 裁定：動畫密集段（wide／concept）判 A1；split（程式段）只受 75% 下限與警示


def ruling(story, model="fit", layout_map=None, degraded=()):
    """依裁定逐版面判定。回傳 (整體 '達標'|'警示'|'未達標'|'n/a（元件退化）', {版面: (res, relaxed, m)})；優先序：未達標 > 警示 > n/a（元件退化）> 達標"""
    m0 = metrics(story, model, layout_map)
    per, worst = {}, "達標"
    for L in sorted(m0["scales"]):
        m = metrics(story, model, layout_map, only=L)
        relaxed = L not in STRICT_LAYOUTS
        res = judge(m, relaxed=relaxed, degraded=degraded, floors=retreat_floors(L, m))
        per[L] = (res, relaxed, m)
        st = {r["status"] for r in res.values()}
        if "fail" in st: worst = "未達標"
        elif ("pass_floor" in st) and worst in ("達標", NA_DEG): worst = "警示"
        elif ("na_degraded" in st) and worst == "達標": worst = NA_DEG
    return worst, per


def fit_warnings(story, model="fit", degraded=()):
    """stage_fit 警示（以裁定逐版面判斷；split 為寬鬆規則）＋ D-012 type=text_overflow 警示（F5）。degraded＝因元件退化而不適用的 A1 項目（見 degraded_keys）"""
    _, per = ruling(story, model, degraded=degraded)
    out = []
    for L, (res, relaxed, m) in per.items():
        lay = f"{L}×{m['scales'].get(L, 1):.2f}"
        for key, zh, thr, lim, cz in A1:
            r = res[key]
            if r["status"] in ("na", "na_degraded", "pass"): continue
            v = r["value"]
            tag = f"[{L}]"
            if r["status"] == "fail":
                st = "degraded"; head = f"{tag}{zh} {v:.0f}px 低於最小可讀尺寸" + ("（低於 split 容許下限 75%）" if relaxed else "")
            elif r.get("retreat") and r["status"] == "pass_floor":
                st = "partial"; head = f"{tag}{zh} {v:.0f}px，退路版達標（門檻 {thr}、退路下限 {r['retreat']}；split2 槽位窄版，完整版 90px/26px 未做）"
            elif r["status"] == "pass_over":
                st = "partial"; head = f"{tag}{zh} 內容超過上限（{cz}={r['count']}>{lim}），仍維持 {v:.0f}px"
            else:
                st = "partial"
                head = f"{tag}{zh} {v:.0f}px，僅受 75% 下限（split 程式段，門檻 {thr}、下限 {thr * FLOOR:.0f}）" if relaxed else f"{tag}{zh} 因內容超過上限（{cz}={r['count']}>{lim}）縮到 {v:.0f}px（門檻 {thr}、容許下限 {thr * FLOOR:.0f}）"
            need = f"{thr}px" + (f"（{cz}≤{lim}）" if lim else "")
            why = [f"版面倍率：{lay}（model={model}）", f"A1 門檻：{need}" + ("；split 僅受 75% 下限" if relaxed else "")]
            if r.get("retreat") and r["status"] == "pass_floor":
                missing = "完整版：槽卡 90px／文字 26px（需更窄的 stage 或更大的右窗；E3 完整版未做）"; eta = "完整版另估（約 1–2 天）"
            elif r["status"] == "fail":
                missing = "更大的動畫區：動畫密集段改用 wide／concept 版面，或調大元件幾何（comps.py）後重跑 autoanim"
                eta = "版面改用 wide/concept：0；元件幾何放大＋重驗：約 0.5–1 天"
            elif relaxed:
                missing = "動畫密集段改用 wide／concept 版面即可達全額門檻"; eta = "0（autoanim --layout wide）"
            else:
                missing = "內容超過上限時的分頁／縮放策略（目前僅縮小並警示）"; eta = "約 0.5 天"
            now = f"{zh} 目前 {v:.0f}px（舞台自適應 {model}，{lay}）"
            out.append(dict(type="stage_fit", name=f"動畫區最小可讀尺寸：{zh}", status=st,
                            evidence=[dict(line=0, code=f"layout={L} {key}={v:.1f}px need={thr}px count={r['count']} limit={lim}")],
                            variables=[key], why=why, now=now, missing=missing, eta=eta,
                            message=f"【{'退化' if st == 'degraded' else '部分支援'}】動畫區最小可讀尺寸：{head}｜缺：{missing}｜目前：{now}｜補元件：{eta}"))
    out += overflow_warnings(story)
    return out


# ── D-012（F5）：文字溢出格子 ──
BORDER = 8   # 框線＋內距（左右合計）


# D-016（F5 校準）：QA D-015 用 D-009 真實 1080p 影格量得數字字形寬約 0.49em（2 位數 fs24：35–37px/倍率 1.536≈23.4px）、'-1' 約 0.85em；
# 舊估計 0.62em/字使 audit 圖樣本誤報約 88%。溢出檢查改用下表（text_width 本身不動，仍供 auto_width／TS 對拍）。
def glyph_width(t, fs):
    """單行文字估寬（px，story 座標）：數字 0.5em、'-' 0.35em、標點／空白 0.28em、小寫 0.55em、大寫 0.65em、CJK 1em、其他 0.62em"""
    w = 0.0
    for c in t:
        if _wide(c): w += 1
        elif c.isdigit(): w += 0.5
        elif c == "-": w += 0.35
        elif c in ".,:;!' ": w += 0.28
        elif c.islower(): w += 0.55
        elif c.isupper(): w += 0.65
        else: w += 0.62
    return w * fs


def usable_width(shape, w, fs):
    """元素內可放單行文字的寬度。矩形＝w-8（Story.tsx：border-box、4px 框線）；圓形＝外圓半徑 w/2-2 在文字半高（0.36·fs）處的弦長
    （文字壓到框線不算溢出，只要仍在圓內；文字比圓高則 0）"""
    if shape == "circle":
        r = w / 2 - 2
        h = 0.36 * fs
        return 2 * (r * r - h * h) ** 0.5 if r > h else 0.0
    return w - BORDER


def text_overflow(story):
    """全片重放，找出『單行文字估寬（text_width）> 元素內寬』的元素（plain／line／無文字／不可見者不查）。回傳 {eid: dict(text,fs,tw,w,shape,cue)}，同一元素只留最嚴重的一筆。
    估寬模型為 glyph_width（D-016 校準，數字 0.5em）；副標（sfs）一併檢查，鍵為 eid#sub。"""
    bad = {}
    for c, L, state, _ in replay(story):
        for e, p in state.items():
            if p["opacity"] <= 0 or p["plain"] or p["shape"] == "line": continue
            w = auto_width(e, p["w"], p["text"], p["fs"])
            for key, txt, fs in ((e, p["text"], p["fs"]), (e + "#sub", p["sub"], p["sfs"])):
                if not txt: continue
                tw, uw = glyph_width(txt, fs), usable_width(p["shape"], w, fs)
                if tw > uw + 0.5 and (key not in bad or tw - uw > bad[key]["tw"] - bad[key]["w"]):
                    bad[key] = dict(text=txt, fs=fs, tw=round(tw, 1), w=round(uw, 1), shape=p["shape"], cue=c["id"])
    return bad


def overflow_warnings(story):
    ob = text_overflow(story)
    if not ob: return []
    items = sorted(ob.items(), key=lambda kv: kv[1]["w"] - kv[1]["tw"])
    ex = "、".join(f"{k}「{v['text']}」估寬 {v['tw']:.0f}>內寬 {v['w']:.0f}（fs={v['fs']}）" for k, v in items[:4])
    names = [k for k, _ in items]
    now = f"{len(ob)} 個元素的文字估寬超過框內寬（可能溢出／折行）：{ex}"
    missing = "縮小字級、加寬格子或改寫顯示文字（版面不自動處理）"; eta = "約 0.5 天（逐元件調幾何＋重驗）"
    return [dict(type="text_overflow", name="文字溢出格子", status="partial",
                 evidence=[dict(line=0, code=f"{k} text={v['text']!r} fs={v['fs']} tw={v['tw']} w={v['w']}") for k, v in items[:6]],
                 variables=names[:12], why=["估寬 = glyph_width（數字 0.5em、'-' 0.35em、CJK 1em…，D-016 依 D-009 真實影格校準），內寬 = 框寬−8（圓形取外圓在文字半高處的弦長）；只做估算，非實際渲染量測"], now=now, missing=missing, eta=eta,
                 message=f"【部分支援】文字溢出格子：{now}｜缺：{missing}｜目前：{now}｜補元件：{eta}")]


def apply_stage_fit(story, mode):
    """autoanim／narrate 共用：mode='auto' → 設 story.stageFit；'off' → 移除。回傳 story（就地修改）"""
    if mode == "auto": story["stageFit"] = "auto"
    elif mode == "off": story.pop("stageFit", None)
    return story


def write_outputs_warnings(folder, story, mode):
    """寫完 warnings.json 之後呼叫：auto → 併入 type=stage_fit 警示（可重跑）；off → 移除既有 stage_fit 警示。回傳新增數"""
    ws = fit_warnings(story, "fit", load_degraded(folder)) if mode == "auto" else []
    p = Path(folder) / "warnings.json"
    if mode == "auto" or p.exists(): merge_warnings(folder, ws)
    return len(ws)


OWN_TYPES = ("stage_fit", "text_overflow")   # merge_warnings 重跑時會先移除、再寫入的警示型態


def summary_of(warnings):
    """warnings.json 的 summary：有任何警示就不是「無缺元件警示」"""
    return "無缺元件警示" if not warnings else f"缺元件警示 {len(warnings)} 項"


def geo_warnings(plan):
    """layoutlib／comps 在排版時記錄的『物理上放不下』事件（plan["geo_warnings"]: [dict(variables, now)]）→ warnings.json 條目 type=layout_overlap（D-012：F2／F3 的超限警示）"""
    out = []
    for g in plan.get("geo_warnings", []):
        out.append(dict(type="layout_overlap", name="元件外框重疊（空間不足）", status="degraded", evidence=[dict(line=0, code=g["now"])], variables=list(g.get("variables", [])),
                        why=["排版時偵測到外框重疊且已用盡可調整的幾何"], now=g["now"], missing="更大的動畫區或更少的元件／節點", eta="約 0.5 天",
                        message=f"【退化】元件外框重疊：{g['now']}｜缺：更大的動畫區或更少的元件／節點｜目前：{g['now']}｜補元件：約 0.5 天"))
    return out


def merge_warnings(folder, ws):
    p = Path(folder) / "warnings.json"
    W = json.loads(p.read_text(encoding="utf-8")) if p.exists() else dict(summary="", algorithms=[], components_used=[], warnings=[])
    W["warnings"] = [w for w in W.get("warnings", []) if w.get("type") not in OWN_TYPES] + ws
    W["summary"] = summary_of(W["warnings"])
    p.write_text(json.dumps(W, ensure_ascii=False, indent=1), encoding="utf-8")
    return W


# ── D-020 E1：fullcode（整份程式雙欄）──
def fullcode_columns(n):
    rows = max(1, -(-n // 2))
    return dict(rows=rows, h=rows * FULLCODE["lh"] + 2 * FULLCODE["pad"], cols=[(0, min(n, rows)), (min(n, rows), n)])


def fullcode_scenes(story):
    return [sc for sc in story.get("scenes", []) if any((c.get("layout") or sc.get("layout")) == "fullcode" for c in sc.get("cues", [])) or sc.get("layout") == "fullcode"]


def fullcode_metrics(code, tab=4):
    """fullcode 場景對一份程式碼的實測推算（1080p 像素，倍率恆 1.0）：行數、最長行字元、列數、面板底 y、欄內所需寬 vs 可用寬、字級。
    判定 ok＝行數≤容量(50) 且 最長行≤58 字元 且 所需寬≤可用寬 且 字級≥22 且 面板底 < 字幕框頂。"""
    F = FULLCODE
    lines = code.rstrip().split("\n") if code.strip() else []
    n = len(lines)
    longest = max((len(l.expandtabs(tab)) for l in lines), default=0)
    col = fullcode_columns(max(n, 1))
    avail = F["colW"] - 2 - 5 - F["gutter"]                 # 欄寬 − 邊框(1×2) − 左邊線(5) − 行號欄
    need = longest * 0.6 * F["fs"]                          # JetBrains Mono 每字 0.6em（D-020 實測 16.1px@27px）
    bottom = F["y0"] + col["h"]
    reasons = []
    if n > F["maxLines"]: reasons.append(f"行數 {n} > 容量 {F['maxLines']}（每欄 {(F['bottomMax'] - F['y0'] - 2 * F['pad']) // F['lh']} 列）")
    if longest > F["maxCols"]: reasons.append(f"最長行 {longest} 字元 > {F['maxCols']}")
    if need > avail + 1e-9: reasons.append(f"最長行需寬 {need:.0f}px > 欄內可用 {avail}px")
    if F["fs"] < 22: reasons.append(f"字級 {F['fs']} < 22")
    if bottom > F["bottomMax"] or bottom >= SUBTITLE_TOP_BOX: reasons.append(f"面板底 {bottom} 超過 {F['bottomMax']}／壓到字幕框（{SUBTITLE_TOP_BOX}）")
    return dict(lines=n, longest=longest, rows=col["rows"], fs=F["fs"], panel_bottom=bottom, need_px=round(need, 1), avail_px=avail,
                ok=not reasons, reasons=reasons)


# ── D-020 E2：split2（左程式面板＋右窗）──
def split2_scenes(story):
    return [sc for sc in story.get("scenes", []) if sc.get("layout") == "split2" or any(c.get("layout") == "split2" for c in sc.get("cues", []))]


def split2_metrics(code, tab=4):
    """split2 對一份程式碼的實測推算（1080p，程式字級 22 不縮放）：行數、最長行字元、欄內所需寬 vs 可用寬、整行可見行數、右窗（stageFit 區）尺寸、面板底。
    ok＝最長行≤58 字元 且 所需寬≤可用寬 且 字級≥20 且 整行可見行數≥20 且 右窗≥950×700 且 面板底<字幕框頂。"""
    S = SPLIT2
    lines = code.rstrip().split("\n") if code.strip() else []
    longest = max((len(l.expandtabs(tab)) for l in lines), default=0)
    gut = S["fs"] * S["gutterW"] + S["fs"] * S["gutterPad"]
    avail = S["panel"]["w"] - 2 - 5 - gut                  # 邊框(1×2)＋左邊線(5)＋窄行號欄
    need = longest * 0.6 * S["fs"]                          # JetBrains Mono 每字 0.6em
    vis = S["panel"]["h"] // S["lh"]
    rx, ry, rw, rh, mn, mx = FIT_REGIONS["split2"]
    bottom = S["panel"]["y"] + S["panel"]["h"]
    reasons = []
    if longest > S["maxCols"]: reasons.append(f"最長行 {longest} 字元 > {S['maxCols']}")
    if need > avail + 1e-9: reasons.append(f"最長行需寬 {need:.1f}px > 面板內可用 {avail:.1f}px")
    if S["fs"] < 20: reasons.append(f"字級 {S['fs']} < 20")
    if vis < 20: reasons.append(f"整行可見行數 {vis} < 20")
    if rw < 950 or rh < 700: reasons.append(f"右窗 {rw}×{rh} < 950×700")
    if bottom >= SUBTITLE_TOP_BOX: reasons.append(f"面板底 {bottom} 壓到字幕框（{SUBTITLE_TOP_BOX}）")
    return dict(lines=len(lines), longest=longest, fs=S["fs"], lh=S["lh"], visible_lines=vis, panel_w=S["panel"]["w"], panel_h=S["panel"]["h"], panel_bottom=bottom,
                need_px=round(need, 1), avail_px=round(avail, 1), win_w=rw, win_h=rh, ok=not reasons, reasons=reasons)
