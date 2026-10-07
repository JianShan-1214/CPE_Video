#!/usr/bin/env python3
"""narrate.py：autoanim 骨架 → 「口語旁白層」。
  dump  <base_folder>                       給寫旁白的人（LLM）看的精簡稿（stdout）
  apply <base_folder> <narration.json> <new_folder> [--no-build]
                                            合併旁白 → 驗證（畫面對拍／數字核對／規則）→ 寫出新 story 資料夾 → story-build
不改動、不刪除任何 op 的內容（畫面狀態＝trace 不變）；唯一允許的是 merge_into_prev（把逐事件 cue 的 ops 併入上一句，僅改 at 時間）。
用法（任何 python3 皆可，不需 tree-sitter）：python3 narrate.py dump <folder>
extra_scenes：narration.json 的 "extra_scenes" 可插入「不屬於程式 trace」的場景。
  舊式（只有 id/title/cues[text,cap,say,lines]）＝純旁白、沿用 base 版面（行為不變）。
  新式（任一場景有 layout／focus／no_code／allow_overlap，或任一 cue 有 ops）：
    layout: concept|wide|split2|fullcode（預設 concept）；focus: anim|code|both（預設 anim）；no_code（預設 layout==concept）＝整場不出現程式碼；
    cue.ops＝自帶動畫 ops（元素 id 必須 intro_ 前綴、op 必須有 at、場尾最後一個 cue 以 at≥0.5 把全部元素淡出 opacity=0）。
    新式場景的 ops 不進「畫面對拍／渲染順序重放／ops 未改動」，改由 introlib.verify_intro 另行驗證（見 introlib.py 檔頭）。
  頂層可加 "require_no_code_first": N（前 N 場必須是 no_code intro 場景）、"intro_min_font_px": 32（有效字級下限）。
  有 no_code 場景時輸出 story 的 revealAll 設為 false（否則渲染器會在 concept 場景底部顯示程式列）。
版面擴充（split2／fullcode／layout_override／layoutRev）：
  extra_scenes 的 layout="fullcode"＝片尾「完整程式碼」：整份程式雙欄一次秀出（不捲動、不截斷、字級 24、標題「完整程式碼」、不顯示 cap 與動畫舞台）。
    該場景不得帶 ops；cue 的 lines 可選（旁白講到哪段，該段輕微高亮；預設全亮）。apply 時檢查：程式超過幾何容量（50 行＝每欄 25 列，不寫死 40）、任一行 >58 字元 → 錯誤（narration 頂層
    "fullcode_allow_overflow": true 可降為警示）；估計停留 <15 秒 → 警示（寫入 narr_verify.json 與輸出）。
  頂層 "layout_override"：字串（所有 base 場景改用該版面）或 {base場景id: 版面}（含 scene_break 切出的子場景）；版面 ∈ concept|wide|split|split2|code|fullcode（split2＝左程式面板 820×852 字級 22＋右窗 1020×800，A1 判全額）。
  頂層 "layoutRev": 2＝輸出 story 標 layoutRev:2（字幕下移到 top=1003，與 wide 程式列零重疊）；省略＝沿用 base story 的值（舊 base 沒有旗標＝與以前逐值相同）。
環境變數 NARRATE_PUB 可覆寫 public 目錄（測試用，預設 <repo>/public）。
"""
import argparse, copy, json, os, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import stagefit  # 舞台自適應的不渲染推算／警示
import introlib  # 新式 extra_scenes（layout／focus／intro_ ops）的獨立驗證器

PUB = Path(os.environ.get("NARRATE_PUB", str(Path(__file__).resolve().parents[2] / "public")))   # 測試可用環境變數改指到 /tmp 副本，預設不變
REPO = Path(__file__).resolve().parents[2]
SYM = "，。！？；：、"


# ───────────────────────── 載入 ─────────────────────────
def load(folder):
    d = PUB / folder
    story = json.loads((d / "story.json").read_text())
    meta = json.loads((d / "narr_meta.json").read_text())
    events = json.loads((d / "trace_events.json").read_text())
    code = (d / "code.cpp").read_text()
    bases, garb = meta.get("bases", {}), meta.get("garbage", {})
    def mask(k, v):
        """殘值（沒初始化的格子／純量）畫面顯示「?」，旁白層也不准看到真值"""
        if k in garb and v == garb[k]: return "?"
        b = bases.get(k)
        if b is not None and isinstance(v, list):
            if v and isinstance(v[0], list):
                return [[("?" if (i < len(b) and j < len(b[i]) and x == b[i][j] and x != 0 and isinstance(x, int)) else x) for j, x in enumerate(r)] for i, r in enumerate(v)]
            return [("?" if (i < len(b) and x == b[i] and x != 0 and isinstance(x, int)) else x) for i, x in enumerate(v)]
        return v
    full = {}
    for e in events:                      # 累積狀態（同 autoanim.build_events）
        e["values"] = {k: mask(k, v) for k, v in e["values"].items()}
        e["changes"] = {k: [mask(k, o), mask(k, nw)] for k, (o, nw) in e["changes"].items()}
        full.update(e["values"]); e["state"] = json.loads(json.dumps(full))
    return d, story, meta, events, code


def norm(v):
    """狀態值 → 可比較的數字／字元。控制字元(\\x01)視為其數字。"""
    if isinstance(v, bool): return int(v)
    if isinstance(v, str) and len(v) == 1 and ord(v) < 32: return ord(v)
    return v


def shown_len(meta, name, v):
    n = meta["disp"].get(name)
    if isinstance(v, list) and isinstance(n, int): return v[:n]
    return v


def fmt_val(v):
    v = norm(v)
    return json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v


def fmt_state(meta, state):
    out = []
    for k in meta["shown"]:
        if k not in state: continue
        v = shown_len(meta, k, state[k])
        if isinstance(v, list):
            if v and isinstance(v[0], list): v = [[norm(x) for x in r[:meta["disp"][k][1]]] for r in v[:meta["disp"][k][0]]]
            else: v = [norm(x) for x in v]
        else: v = norm(v)
        out.append(f"{k}={json.dumps(v, ensure_ascii=False, separators=(',', ':'))}")
    return " ".join(out)


def diff_changes(meta, e):
    parts = []
    shown = set(meta["shown"]) | set(meta["markers"])
    for k in e.get("born", []):
        if k in shown: parts.append(f"{k} 出生={fmt_val(e['values'][k]) if not isinstance(e['values'][k], list) else json.dumps([norm(x) for x in shown_len(meta, k, e['values'][k])], ensure_ascii=False, separators=(',', ':'))}")
    for k, (old, new) in e["changes"].items():
        if k not in shown: continue
        if isinstance(new, list) and new and isinstance(new[0], list):
            ch = [(i, j) for i, r in enumerate(new) for j, x in enumerate(r) if not (i < len(old) and j < len(old[i]) and old[i][j] == x)]
            s = ", ".join(f"{k}[{i}][{j}]:{norm(old[i][j]) if i < len(old) and j < len(old[i]) else '∅'}→{norm(new[i][j])}" for i, j in ch[:6])
            parts.append(s + (f" …共{len(ch)}格" if len(ch) > 6 else ""))
        elif isinstance(new, list):
            n = max(len(old), len(new))
            ch = [i for i in range(n) if (old[i] if i < len(old) else None) != (new[i] if i < len(new) else None)]
            s = ", ".join(f"{k}[{i}]:{norm(old[i]) if i < len(old) else '∅'}→{norm(new[i]) if i < len(new) else '∅'}" for i in ch[:6])
            parts.append(s + (f" …共{len(ch)}格" if len(ch) > 6 else ""))
        elif isinstance(new, str) and len(new) > 1:
            parts.append(f"{k}:'{old}'→'{new}'")
        else:
            parts.append(f"{k}:{norm(old)}→{norm(new)}")
    return "; ".join(parts) or "(無顯示變化)"


# ───────────────────────── dump ─────────────────────────
def cmd_dump(a):
    d, story, meta, events, code = load(a.folder)
    lines = code.split("\n")
    print(f"# 題目：{story['title']}    資料夾：{a.folder}")
    print(f"# 輸入：{meta['stdin'].strip()!r}    輸出：{meta['stdout'].strip()!r}")
    print(f"# 畫面顯示：陣列={meta['arrays']} 純量chip={meta['chips']} 指標marker(▲)={meta['markers']}")
    DESC = {"graph": "節點圓＋邊線圖（節點內=編號與 dist 值；黃=目前處理的節點；綠=已訪問；虛線框=在佇列／堆疊內）",
            "seq": "佇列／堆疊卡片（隊首／堆頂黃色；push 新卡入列、pop 卡片離開）",
            "slots": "人物卡片＋槽位列（卡片被選中變黃，放進槽位後移到該槽並變綠）",
            "tree": "節點圓＋父子連線的樹（黃=目前走到的節點，綠=剛新增的節點）",
            "keyed": "依鍵排序的 key／value 卡片列（新鍵綠、值變動黃）"}
    for c in meta.get("comps", []):
        print(f"# 元件[{c['kind']}] 變數 {c['vars']}：{DESC.get(c['kind'], '')}——這些變數用圖形呈現，旁白可以說「圖上」「佇列裡」「槽位」，不必說「陣列格」")
    if meta["notes"]: print("# 限制：", "; ".join(meta["notes"]))
    wf = d / "warnings.json"
    if wf.exists():
        W = json.loads(wf.read_text())
        if W["warnings"]:
            print(f"# ██ 缺元件警示 {len(W['warnings'])} 項（畫面退化，旁白不要假設有這些視覺；出片回報須附）：")
            for w in W["warnings"]:
                print(f"#   - [{w['status']}] {w['name']} {('('+'、'.join(w['variables'][:3])+')') if w['variables'] else ''}：目前＝{w['now']}；缺＝{w['missing']}；補元件＝{w['eta']}")
        if W.get("components_used"): print("# 已自動選用元件：", "、".join(W["components_used"]))
    print("# 每格「?」＝該格尚未被程式寫入的殘值；旗標 \\x01 顯示為 1。索引由 0 起算。")
    cues_meta = meta["cues"]
    cur_state = {}
    for sc in story["scenes"]:
        sid = sc["id"]
        allines = sorted({l for c in sc["cues"] for l in c.get("lines", [])})
        if sid.startswith("s") and sc["label"] == "輸出": allines = sorted({l for c in sc["cues"] for l in c.get("lines", [])})
        print(f"\n=== 場景 {sid}（原標題「{sc['label']}」）程式行 {allines[0] if allines else '-'}–{allines[-1] if allines else '-'} ===")
        if allines and len(allines) <= 16:
            for l in range(allines[0], allines[-1] + 1): print(f"  {l:>2}| {lines[l - 1]}")
        elif allines:
            print(f"  （{len(allines)} 行；主要 {allines[0]}–{allines[-1]}）")
        for c in sc["cues"]:
            m = cues_meta.get(c["id"], {"kind": "?", "events": []})
            ls = c.get("lines", [])
            lr = f"{ls[0]}–{ls[-1]}" if ls else "-"
            if m["kind"] == "event":
                e = events[m["events"][0]]; cur_state = e["state"]
                print(f"  - {c['id']} [逐事件] 行{e['line0']}: {diff_changes(meta, e)}")
                print(f"        狀態: {fmt_state(meta, cur_state)}")
            elif m["kind"] == "ff":
                es = [events[i] for i in m["events"]]
                print(f"  - {c['id']} [快轉 {len(es)} 個事件] 行{lr}:")
                for e in es[:3]: print(f"        · 行{e['line0']}: {diff_changes(meta, e)}")
                if len(es) > 3: print(f"        · …（其餘 {len(es) - 3} 個）")
                cur_state = es[-1]["state"]
                print(f"        快轉後狀態: {fmt_state(meta, cur_state)}")
            elif m["kind"] == "setup":
                cur_state = events[0]["state"]
                print(f"  - {c['id']} [初始畫面] 行{lr}: 畫面先出現 {fmt_state(meta, cur_state)}")
            elif m["kind"] == "intro":
                print(f"  - {c['id']} [場景開場] 行{lr}（此句只重設顏色，無資料變化）  目前: {fmt_state(meta, cur_state)}")
            else:
                print(f"  - {c['id']} [{m['kind']}] 行{lr}")
    print("\n# narration.json 格式見 SKILL.md「旁白層」。每個 cue 必須有 text；可加 cap、about（陣列變數名，供數字核對）、claims、allow_numbers。")


# ───────────────────────── 數字核對 ─────────────────────────
CN = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
# 這些詞裡的「一／二／十」不是數量，核對前先遮掉
IDIOMS = ["一對一對", "一格一格", "一個一個", "一組一組", "一步一步", "一次一次", "一下子", "一下", "一定", "一起", "一樣", "一直", "一邊", "一句話", "一句", "一開始",
          "一些", "一點", "一般", "一種", "一切", "一旦", "一半", "十分", "第一", "一眼", "一口氣", "一路", "一輪", "一遍", "萬一", "唯一", "統一",
          "同一", "每一", "一層層", "一層一層", "一列", "一整", "另一", "一律", "一致", "一併", "一如", "一再"]
NUMRE = re.compile(r"-?\d+|負?[零〇一二兩三四五六七八九十百]+")
A = re.A


def cn2int(s):
    if s.startswith("負"): return -cn2int(s[1:])
    if s.lstrip("-").isdigit(): return int(s)
    if "百" in s:
        h, r = s.split("百", 1)
        return (CN.get(h, 1) if h else 1) * 100 + (cn2int(r) if r else 0)
    if "十" in s:
        l, r = s.split("十", 1)
        return (CN[l] if l else 1) * 10 + (CN[r] if r else 0)
    v = 0
    for ch in s: v = v * 10 + CN[ch]
    return v


def numbers_in(text):
    """回傳 [(值, 原字串, 是否『N 行』行號)]；數字緊接「行」＝程式行號（說輸出的「第二行」請改寫，避免歧義）"""
    t = text
    for w in IDIOMS: t = t.replace(w, "␣" * len(w))
    out = []
    for m in NUMRE.finditer(t):
        try: v = cn2int(m.group(0))
        except Exception: continue
        rest = t[m.end():].lstrip(" ")
        out.append((v, m.group(0), rest[:1] == "行"))
    return out


def walk_ints(v, acc):
    v = norm(v)
    if isinstance(v, list):
        for x in v: walk_ints(x, acc)
    elif isinstance(v, int): acc.add(v)


def get_path(state, path):
    m = re.match(r"^([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)((?:\[\d+\])*)$", path, A)   # struct 欄位列 p.s[4]
    if not m or m.group(1) not in state: raise KeyError(path)
    v = state[m.group(1)]
    for ix in re.findall(r"\[(\d+)\]", m.group(2)): v = v[int(ix)]
    return norm(v)


def parse_val(s):
    s = s.strip()
    if re.fullmatch(r"-?\d+", s): return int(s)
    if re.fullmatch(r"[零〇一二兩三四五六七八九十百]+", s): return cn2int(s)
    return s


def base_ctx(base, meta, events):
    ctx, prev = {}, {}
    for sc in base["scenes"]:
        for c in sc["cues"]:
            m = meta["cues"][c["id"]]
            evs = [events[i] for i in m["events"]]
            after = events[0]["state"] if m["kind"] == "setup" else (evs[-1]["state"] if evs else prev)
            ctx[c["id"]] = dict(kind=m["kind"], before=prev, after=after, evs=evs, lines=c.get("lines", []))
            prev = after
    return ctx


class Checker:
    def __init__(self, meta, code):
        self.meta = meta
        self.varnames = set(meta["shown"]) | set(meta["markers"])
        self.stdin_nums = {int(x) for x in re.findall(r"\d+", meta["stdin"])}
        self.stdin_letters = set(re.findall(r"[A-Z]", meta["stdin"]))
        self.stdout_nums = {int(x) for x in re.findall(r"\d+", meta["stdout"])}
        self.stdout_letters = set(re.findall(r"[A-Z]", meta["stdout"]))
        self.ok = self.bad = self.claims_ok = self.claims_bad = 0
        self.kinds = dict(num=[0, 0], line=[0, 0], letter=[0, 0], stmt=[0, 0])
        self.errors = []

    def err(self, cid, msg): self.errors.append(f"{cid}: {msg}")

    def hit(self, kind, good):
        self.kinds[kind][0 if good else 1] += 1
        if good: self.ok += 1
        else: self.bad += 1

    def facts(self, cx, about):
        strict, loose = set(), set()
        for e in cx["evs"]:
            for k in e.get("born", []):
                if k in self.varnames: walk_ints(e["values"][k], strict)
            for k, (old, new) in e["changes"].items():
                if k not in self.varnames: continue
                if isinstance(new, list):
                    for i in range(max(len(old), len(new))):
                        o = old[i] if i < len(old) else None; nn = new[i] if i < len(new) else None
                        if isinstance(o, list) or isinstance(nn, list):
                            for j in range(max(len(o or []), len(nn or []))):
                                oo = o[j] if o and j < len(o) else None; n2 = nn[j] if nn and j < len(nn) else None
                                if oo != n2: strict.add(i); strict.add(j); walk_ints(oo if oo is not None else [], strict); walk_ints(n2 if n2 is not None else [], strict)
                        elif o != nn:
                            strict.add(i); walk_ints(o if o is not None else [], strict); walk_ints(nn if nn is not None else [], strict)
                else:
                    walk_ints(old, strict); walk_ints(new, strict)
            for k in self.meta["markers"] + self.meta["chips"]:
                if k in e["values"]: walk_ints(e["values"][k], strict)
        st = cx["after"]
        for k in self.meta["markers"] + self.meta["chips"]:
            if k in st: walk_ints(st[k], strict)
        for k in about:
            if k in st:
                walk_ints(shown_len(self.meta, k, st[k]), loose)
                dd = self.meta["disp"].get(k)
                if isinstance(dd, int): loose.update(range(dd + 1))
                elif dd: loose.update(range(dd[0] + 1)); loose.update(range(dd[1] + 1))
        if cx["kind"] == "setup":   # 開場可引用範例輸入輸出的數字（畫面就是那組範例）
            loose |= self.stdin_nums | self.stdout_nums
            for k in self.meta["shown"]:
                if k in st: walk_ints(shown_len(self.meta, k, st[k]), loose)
        if cx["kind"] == "out": loose |= self.stdout_nums
        if cx["kind"] == "extra": loose |= self.stdin_nums | self.stdout_nums
        loose |= strict
        return strict, loose

    def check_cue(self, cid, n, text, cap, cx, lines):
        about = list(n.get("about", []))
        for a_ in about:
            if a_ not in self.varnames: self.err(cid, f"about 指到不存在的顯示變數 {a_}（可用 {sorted(self.varnames)}）")
        for m in re.finditer(r"(?<![\w\[])([A-Za-z_]\w*)(?![\w])", text + " " + cap, A):
            if m.group(1) in self.varnames and m.group(1) not in about: about.append(m.group(1))
        for m in re.finditer(r"(?<![\w\[.])([A-Za-z_]\w*\.[A-Za-z_]\w*)(?![\w])", text + " " + cap, A):   # struct 欄位列 p.s
            if m.group(1) in self.varnames and m.group(1) not in about: about.append(m.group(1))
        strict, loose = self.facts(cx, about)
        allow = set(n.get("allow_numbers", []))
        # 1) 明確 claims（對本 cue 結束後的 trace 狀態；before. 前綴＝本 cue 開始前）
        for cl in n.get("claims", []):
            m = re.match(r"^(before\.)?([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?(?:\[\d+\])*)\s*(==|=|!=)\s*(.+)$", cl.strip(), A)   # 允許 p.s[4]=10
            if not m: self.err(cid, f"claims 格式錯誤：{cl}（範例 cnt[1]=4、before.i=0、ch=B）"); self.claims_bad += 1; continue
            st = cx["before"] if m.group(1) else cx["after"]
            try: got = get_path(st, m.group(2))
            except Exception: self.err(cid, f"claims {cl}：狀態中找不到 {m.group(2)}"); self.claims_bad += 1; continue
            want = parse_val(m.group(4)); eq = got == want
            if m.group(3) == "!=": eq = not eq
            if eq: self.claims_ok += 1
            else: self.claims_bad += 1; self.err(cid, f"claims 不符：{cl}，trace 實際 {m.group(2)}={got}")
        # 2) 旁白裡「變數 是／變成／等於 值」與「變數 從 X 變成 Y」逐句抽出比對
        VAL = r"(-?\d+|[零〇一二兩三四五六七八九十百]+|[A-Z])(?![\w])"
        for m in re.finditer(r"(?<![\w\[.])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?(?:\[\d+\])*)\s*(?:=|＝|是|變成|等於|變為)\s*" + VAL, text, A):   # p.i 是 1 → 查 p.i（不是 i）
            name = m.group(1)
            if name.split("[")[0] not in self.varnames: continue
            gots = []
            for st in cx.get("afters", [cx["after"]]):
                try: gots.append(get_path(st, name))
                except Exception: pass
            if not gots: self.err(cid, f"旁白「{m.group(0)}」：狀態中找不到 {name}"); self.hit("stmt", False); continue
            want = parse_val(m.group(2))
            good = any(g == want or (isinstance(g, int) and isinstance(want, str) and len(want) == 1 and chr(65 + g) == want) for g in gots)
            self.hit("stmt", good)
            if not good: self.err(cid, f"旁白「{m.group(0)}」與 trace 不符（{name} 在此 cue 各步實際值={gots}）")
        for m in re.finditer(r"(?<![\w\[.])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?(?:\[\d+\])*)\s*從\s*" + VAL + r"\s*變成\s*" + VAL, text, A):
            name = m.group(1)
            if name.split("[")[0] not in self.varnames: continue
            pairs = []
            for b_, a_ in cx.get("pairs", [(cx["before"], cx["after"])]) + [(cx["before"], cx["after"])]:
                try: pairs.append((get_path(b_, name), get_path(a_, name)))
                except Exception: pass
            if not pairs: self.err(cid, f"旁白「{m.group(0)}」：找不到 {name}"); self.hit("stmt", False); continue
            good = any(ob == parse_val(m.group(2)) and oa == parse_val(m.group(3)) for ob, oa in pairs)
            self.hit("stmt", good)
            if not good: self.err(cid, f"旁白「{m.group(0)}」與 trace 不符（{name}：{pairs}）")
        # 3) 所有數字（阿拉伯／中文）必須在本 cue 的事實內；「N 行」必須是本 cue／本場高亮行
        for txt_, where in ((text, "旁白"), (cap, "cap")):
            for v, raw, is_line in numbers_in(txt_):
                if is_line:
                    good = v in lines or v in allow
                    self.hit("line", good)
                    if not good: self.err(cid, f"{where}提到「{raw}行」，但本場高亮行是 {sorted(lines)[:10]}")
                else:
                    good = v in loose or v in allow
                    self.hit("num", good)
                    if not good: self.err(cid, f"{where}提到數字「{raw}」＝{v}，不在該 cue 的 trace 事實內（已知：{sorted(loose)[:24]}；確為題目常數才用 allow_numbers）")
        # 4) 大寫字母：只接受 (i) 本 cue 各步字元變數的值／陣列裡的字元 (ii) 本 cue 變化到的整數 k 對應的 A+k
        #    (iii) 初始畫面／輸出 cue 的輸入輸出字母 (iv) letters_from 指定陣列的值 (v) allow_letters 明確放行
        ok_l = set(n.get("allow_letters", []))
        if cx["kind"] in ("setup", "out"): ok_l |= self.stdin_letters | self.stdout_letters
        def add_chars(v):
            if isinstance(v, str) and len(v) == 1 and v.isalpha(): ok_l.add(v)
            elif isinstance(v, list):
                for x in v: add_chars(x)
        for st in cx.get("afters", [cx["after"]]) + [cx["before"]]:
            for k in self.meta["shown"] + self.meta["markers"]:
                if k in st: add_chars(st[k])
        for e in cx["evs"]:
            for k, v in e["values"].items():
                if k in self.varnames: add_chars(v)
        for v in strict:
            if 0 <= v < 26: ok_l.add(chr(65 + v))
        for k in n.get("letters_from", []):
            tmp = set(); walk_ints(cx["after"].get(k, []), tmp)
            ok_l |= {chr(65 + v) for v in tmp if 0 <= v < 26}
        for m in re.finditer(r"(?<![A-Za-z])([A-Z])(?![A-Za-z])", text + " " + cap):
            self.hit("letter", m.group(1) in ok_l)
            if m.group(1) not in ok_l: self.err(cid, f"提到字母 {m.group(1)}，但本 cue 的 trace 事實推不出它（可用 letters_from／allow_letters 明確放行；目前可接受 {sorted(ok_l)}）")


# ───────────────────────── 對拍（重放 ops） ─────────────────────────
from verifylib import key_of, apply_patch, check_key, got_of


def replay_verify(story, meta):
    """(a1) 依 autoanim 原順序逐組重放，畫面文字須＝ trace 預期（同 autoanim verify）"""
    cur, ok, bad, fails = {}, 0, 0, []
    groups = {}
    for sc in story["scenes"]:
        for c in sc["cues"]:
            for i, o in enumerate(c.get("ops", [])): groups.setdefault(o["_g"], []).append((i, o))
    for cid, exp in meta["checks"]:
        for _, o in sorted(groups.get(cid, []), key=lambda t: (key_of(t[1]), t[0])): apply_patch(cur, o)
        if exp is None: continue
        for eid, t in exp.items():
            if check_key(cur, eid, t): ok += 1
            else: bad += 1; fails.append((cid, eid, t, got_of(cur, eid)))
    want = [l.rstrip() for l in meta["stdout"].rstrip("\n").split("\n")][:6]
    for k, w in enumerate(want):
        w2 = w if len(w) <= 40 else w[:40] + "…"
        got = cur.get(f"o{k}", {}).get("text")
        if got == w2: ok += 1
        else: bad += 1; fails.append(("out", f"o{k}", w2, got))
    return ok, bad, fails


def renderer_order_verify(story, meta):
    """(a2) 以渲染器實際順序（依 cue、cue 內依時間鍵）重放：每個 cue 結束時，畫面須＝其最後一組的預期；
    並檢查合併後 cue 內各 op 組的先後仍是原本順序。"""
    exp = dict(meta["checks"]); order = {cid: i for i, (cid, _) in enumerate(meta["checks"])}
    cur, ok, bad, fails = {}, 0, 0, []
    last_g = -1
    for sc in story["scenes"]:
        for c in sc["cues"]:
            ops = sorted(enumerate(c.get("ops", [])), key=lambda t: (key_of(t[1]), t[0]))
            for _, o in ops:
                if o["_g"].startswith("__intro__"): continue   # intro 場景的 ops 另行驗證
                if order[o["_g"]] < last_g: bad += 1; fails.append((c["id"], "順序", o["_g"], "op 組順序被打亂"))
                last_g = max(last_g, order[o["_g"]])
                apply_patch(cur, o)
            if not ops: continue
            e = exp.get(ops[-1][1]["_g"])
            if not e: continue
            for eid, t in e.items():
                if check_key(cur, eid, t): ok += 1
                else: bad += 1; fails.append((c["id"], eid, t, got_of(cur, eid)))
    return ok, bad, fails


# ───────────────────────── 規則檢查（同 story-build.mjs ＋旁白層自訂） ─────────────────────────
def clen(t): return len(re.sub(r"[，。！？；：、「」\s]", "", t))


def chunks(text):
    parts = re.findall(r"[^，。！？；：、]+[，。！？；：、]?", text) or [text]
    out = []
    for p in parts:
        if out and len(out[-1] + p) <= 18 and not re.search(r"[。！？]$", out[-1]): out[-1] += p
        else: out.append(p)
    return out


def rule_check(story, names, lo=45, hi=70):
    warns, last_start, notice, counts = [], "", 0, []
    for sc in story["scenes"]:
        all_ = "".join(c["text"] for c in sc["cues"])
        n = clen(all_); counts.append((sc["id"], sc["label"], n, len(sc["cues"])))
        if n < lo or n > hi: warns.append(f"[narr] 場景 {sc['id']} 旁白 {n} 字，超出 {lo}–{hi}")
        st = all_[:2]
        if st == last_start: warns.append(f"[build] 場景 {sc['id']} 開頭「{st}」與上一場景相同")
        last_start = st
        mentioned = {m.group(1) for m in re.finditer(r"(?<![\w\[])([A-Za-z_]\w*)(?![\w])", all_, A) if m.group(1) in names}
        if len(mentioned) > 3: warns.append(f"[narr] 場景 {sc['id']} 提到 {len(mentioned)} 個程式名稱 {sorted(mentioned)}（建議 ≤3，其餘用中文角色名）")
        for c in sc["cues"]:
            if not c["text"].strip(): warns.append(f"{c['id']} 旁白為空")
            for p in chunks(c["text"]):
                if len(re.sub(r"[，。！？；：、]", "", p)) > 18: warns.append(f"[build] {c['id']} 單行字幕片段超過 18 字：{p}")
            cap = c.get("cap")
            if cap and len(cap) > 14: warns.append(f"[build] {c['id']} cap 超過 14 字：{cap}")
            if cap and cap in c["text"]: warns.append(f"[build] {c['id']} cap 與旁白重複")
            notice += c["text"].count("這裡要注意")
            if re.search(r"[\[\]=<>{}]", c["text"]): warns.append(f"[narr] {c['id']} 旁白含程式符號（TTS 會念怪，改口語或加 say）")
    if notice > 1: warns.append(f"[build] 「這裡要注意」出現 {notice} 次（最多 1 次）")
    return warns, counts


# ───────────────────────── apply ─────────────────────────
def cmd_apply(a):
    d, base, meta, events, code = load(a.folder)
    nar = json.loads(Path(a.narration).read_text())
    bctx = base_ctx(base, meta, events)
    src = copy.deepcopy(base)
    base_ops = [o["set"] for sc in base["scenes"] for c in sc["cues"] for o in c.get("ops", [])]
    order = {cid: i for i, (cid, _) in enumerate(meta["checks"])}
    errors = []
    nsc = nar.get("scenes", {})
    sids = {sc["id"] for sc in src["scenes"]}
    cids = {c["id"] for sc in src["scenes"] for c in sc["cues"]}
    for sid, ns in nsc.items():
        if sid not in sids: errors.append(f"narration 有不存在的場景 {sid}")
        else:
            for cid in ns.get("cues", {}):
                if cid not in {c["id"] for sc in src["scenes"] if sc["id"] == sid for c in sc["cues"]}: errors.append(f"場景 {sid} 沒有 cue {cid}")
    extras = {}
    for x in nar.get("extra_scenes", []): extras.setdefault(x.get("after", ""), []).append(x)
    out_scenes, groups_of, ncues = [], {}, {}

    intro_specs = {}

    def add_extra(after):
        for x in extras.get(after, []):
            new_style = introlib.is_new_style(x)
            if x["id"] in sids or x["id"] in {sc_["id"] for sc_ in out_scenes}: errors.append(f"額外場景 id 重複：{x['id']}")
            cues = []
            for xc in x["cues"]:
                c = dict(id=xc["id"], text=xc["text"], lines=xc.get("lines", []), ops=[], pauseAfter=xc.get("pauseAfter", 0.6))
                if xc["id"] in cids or xc["id"] in groups_of: errors.append(f"額外 cue id 重複：{xc['id']}")
                if "cap" in xc: c["cap"] = xc["cap"]
                if "say" in xc: c["say"] = xc["say"]
                if new_style:
                    c["ops"] = [dict(copy.deepcopy(o), _g="__intro__" + x["id"]) if isinstance(o, dict) else o for o in xc.get("ops", [])]
                groups_of[c["id"]] = []; ncues[c["id"]] = xc; cues.append(c)
            if new_style:
                spec = introlib.make_spec(x); intro_specs[x["id"]] = spec
                out_scenes.append(dict(id=x["id"], label=x["title"], layout=spec["layout"], focus=spec["focus"], cues=cues))
            else:
                out_scenes.append(dict(id=x["id"], label=x["title"], layout=(src["scenes"][0]["layout"] if src["scenes"] else "split"), focus="both", cues=cues))
    for k_ in extras:
        if k_ != "" and k_ not in sids: errors.append(f"extra_scenes 的 after={k_!r} 不是基礎場景 id，這些額外場景不會被插入")
    add_extra("")
    for sc in src["scenes"]:
        ns = nsc.get(sc["id"], {}); cc = ns.get("cues", {})
        if ns.get("merge_into_prev_scene") and out_scenes: cur = out_scenes[-1]
        else:
            cur = dict(id=sc["id"], label=ns.get("title", sc["label"]), layout=sc["layout"], focus=sc["focus"], cues=[], _base=sc["id"])
            out_scenes.append(cur)
        for c in sc["cues"]:
            n = cc.get(c["id"]); kind = meta["cues"][c["id"]]["kind"]
            if n is None: errors.append(f"缺少 {c['id']} 的旁白（{kind}）"); continue
            if n.get("scene_break"):
                cur = dict(id=f"{sc['id']}_{c['id']}", label=n["scene_break"], layout=sc["layout"], focus=sc["focus"], cues=[], _base=sc["id"])
                out_scenes.append(cur)
            prev = cur["cues"][-1] if cur["cues"] else None
            if n.get("merge_into_prev"):
                pk = meta["cues"][prev["id"]]["kind"] if prev and prev["id"] in meta["cues"] else None
                if prev is None or pk not in ("event", "intro", "setup") or kind not in ("event", "intro"):
                    errors.append(f"{c['id']} 不能 merge_into_prev（只支援逐事件／開場 cue 併入逐事件／開場／初始 cue；快轉 cue 與額外 cue 不併）"); continue
                if prev.get("lines") != c.get("lines") and not n.get("allow_line_mismatch"):
                    errors.append(f"{c['id']} 與被併入的 {prev['id']} 高亮行不同（{c.get('lines')} vs {prev.get('lines')}），併入後畫面高亮會與旁白不符；改為獨立 cue，或加 allow_line_mismatch"); continue
                for o in prev["ops"]: o.setdefault("_g", prev["id"])
                prev["_n"] = prev.get("_n", 0)
                base_at = max([o["at"] for o in prev["ops"] if "at" in o] or [0.3])
                for o in c.get("ops", []):
                    o2 = copy.deepcopy(o); o2["_g"] = c["id"]
                    if "at" in n: o2["at"] = n["at"]; o2.pop("dt", None)
                    else: prev["_n"] += 1; o2["at"] = base_at; o2["dt"] = round(0.9 * prev["_n"], 2)
                    prev["ops"].append(o2)
                groups_of[prev["id"]].append(c["id"]); ncues[c["id"]] = dict(merged=True)
                continue
            if "text" not in n: errors.append(f"{c['id']} 缺 text"); continue
            c["text"] = n["text"]
            if "cap" in n: c["cap"] = n["cap"]
            else: c.pop("cap", None)
            for k in ("say", "pauseAfter"):
                if k in n: c[k] = n[k]
            for o in c.get("ops", []): o["_g"] = c["id"]
            groups_of[c["id"]] = [c["id"]]; ncues[c["id"]] = n; cur["cues"].append(c)
        add_extra(sc["id"])
    for sc in out_scenes:
        if len(sc["label"]) > 16: errors.append(f"{sc['id']} 標題太長（{len(sc['label'])}>16）")
    # layout_override（base 場景改版面）
    lo = nar.get("layout_override")
    OVR = ("concept", "wide", "split", "split2", "code", "fullcode")
    if lo is not None:
        if isinstance(lo, str): lo = {sid_: lo for sid_ in sids}
        if not isinstance(lo, dict): errors.append("layout_override 必須是版面名稱字串或 {場景id: 版面}")
        else:
            for k_, v_ in lo.items():
                if k_ not in sids: errors.append(f"layout_override 的場景 {k_!r} 不是基礎場景 id")
                if v_ not in OVR: errors.append(f"layout_override[{k_}]={v_!r} 不合法（可用 {OVR}）")
            for sc_ in out_scenes:
                b_ = sc_.get("_base")
                if b_ in lo and lo[b_] in OVR: sc_["layout"] = lo[b_]
    for sc_ in out_scenes: sc_.pop("_base", None)
    story = dict(src, scenes=out_scenes)
    if "title" in nar: story["title"] = nar["title"]
    if "layoutRev" in nar:
        if nar["layoutRev"] in (1, 2): story["layoutRev"] = nar["layoutRev"]
        else: errors.append(f"layoutRev 只能是 1 或 2（收到 {nar['layoutRev']!r}）")
    for sc in out_scenes:
        for c in sc["cues"]: c.pop("_n", None)
    now_ops = [o["set"] for sc in story["scenes"] for c in sc["cues"] for o in c.get("ops", []) if not str(o.get("_g", "")).startswith("__intro__")]
    ops_unchanged = sorted(map(json.dumps, now_ops)) == sorted(map(json.dumps, base_ops))
    if not ops_unchanged: errors.append("內部錯誤：op 內容與原骨架不同（不允許）")
    # (a0) 新式 extra_scenes 獨立驗證（不進畫面對拍；程式碼面板可見性、intro_ 前綴／id 衝突／場尾淡出／殘留／字級／重疊）
    intro_rep = None
    req_n = nar.get("require_no_code_first", 0)
    if intro_specs or req_n:
        if any(sp["no_code"] for sp in intro_specs.values()): story["revealAll"] = False
        base_ids = {eid for sc_ in base["scenes"] for c_ in sc_["cues"] for o_ in c_.get("ops", []) for eid in o_["set"]}
        intro_rep = introlib.verify_intro(story, intro_specs, base_ids, req_n, nar.get("intro_min_font_px", 32))
        errors += intro_rep.lines()
    # (a0') fullcode 場景（extra_scenes 或 layout_override）對程式碼的檢查
    full_warns = []
    for sc_ in story["scenes"]:
        if sc_["layout"] == "fullcode":
            fe, fw = introlib.check_fullcode(code, sc_)
            if nar.get("fullcode_allow_overflow"):
                full_warns += [f"(允許溢出) {x}" for x in fe]
            else:
                errors += fe
            full_warns += fw
    # (a0'') split2 場景的程式碼寬度（≤58 字元，A1 不截斷）；split2_allow_overflow:true 降為警示
    sp2 = [sc_["id"] for sc_ in story["scenes"] if sc_["layout"] == "split2" or any(c_.get("layout") == "split2" for c_ in sc_["cues"])]
    if sp2:
        se = introlib.check_split2(code, sp2)
        if nar.get("split2_allow_overflow"): full_warns += [f"(允許溢出) {x}" for x in se]
        else: errors += se
    # (a1) --stage-fit auto → 輸出 story 標 stageFit="auto"（渲染器依內容自適應舞台），並推算 A1 警示
    fit_ws = []
    sf_mode = getattr(a, "stage_fit", None) or ("auto" if story.get("stageFit") == "auto" else None)   # 沒指定時沿用 base（autoanim 預設 auto）
    if sf_mode == "off": stagefit.apply_stage_fit(story, "off")
    if sf_mode == "auto":
        stagefit.apply_stage_fit(story, "auto")
        fit_ws = stagefit.fit_warnings(story, "fit", stagefit.load_degraded(d))   # base 資料夾 warnings.json 內退化的元件 → A1 該項 n/a
    # (a) 畫面對拍
    ok_a, bad_a, fails_a = replay_verify(story, meta)
    ok_r, bad_r, fails_r = renderer_order_verify(story, meta)
    for f in fails_a[:5] + fails_r[:5]: errors.append(f"畫面對拍失敗 {f}")
    # (b) 數字核對
    ck = Checker(meta, code)
    prev_after = {}
    for sc in out_scenes:
        scene_lines = {l for c in sc["cues"] for l in c.get("lines", [])}
        for c in sc["cues"]:
            g = groups_of[c["id"]]
            if g:
                cs = [bctx[x] for x in g]
                kinds = [x["kind"] for x in cs]
                kind = "setup" if "setup" in kinds else ("out" if "out" in kinds else ("ff" if "ff" in kinds else "event"))
                cx = dict(kind=kind, before=cs[0]["before"], after=cs[-1]["after"], evs=[e for x in cs for e in x["evs"]],
                          afters=[x["after"] for x in cs], pairs=[(x["before"], x["after"]) for x in cs])
                prev_after = cx["after"]
            else:
                cx = dict(kind="extra", before=prev_after, after=prev_after, evs=[])
            n = ncues[c["id"]]
            ck.check_cue(c["id"], n, c["text"], c.get("cap", ""), cx, set(c.get("lines", [])) | scene_lines)
    errors += ck.errors
    names = set(meta["shown"]) | set(meta["markers"]) | {"pick", "main", "sort", "push_back", "front"}
    warns, counts = rule_check(story, names)
    warns += full_warns
    for sc in story["scenes"]:
        for c in sc["cues"]:
            for o in c.get("ops", []): o.pop("_g", None)
    out = PUB / a.new_folder
    out.mkdir(parents=True, exist_ok=True)
    for f in ("code.cpp", "trace_events.json", "narr_meta.json", "warnings.json"):
        if (d / f).exists(): (out / f).write_text((d / f).read_text())
    (out / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=1))
    if sf_mode == "auto": stagefit.merge_warnings(out, fit_ws)
    elif sf_mode == "off": stagefit.merge_warnings(out, [])
    (out / "narration.json").write_text(Path(a.narration).read_text())
    res = dict(screen_ok=ok_a, screen_bad=bad_a, renderer_order_ok=ok_r, renderer_order_bad=bad_r,
               num_ok=ck.ok, num_bad=ck.bad, by_kind={k: v for k, v in ck.kinds.items()}, claims_ok=ck.claims_ok, claims_bad=ck.claims_bad,
               warnings=warns, errors=errors, ops_unchanged=ops_unchanged, scene_chars=counts)
    if intro_rep: res.update(intro_ok=intro_rep.ok, intro_bad=intro_rep.bad, intro_scenes=sorted(intro_specs))
    ncue = sum(len(s["cues"]) for s in story["scenes"])
    print(f"{a.new_folder}: scenes={len(story['scenes'])} cues={ncue}（併入 {sum(1 for v in ncues.values() if v.get('merged'))} 個逐事件 cue）")
    print(f"  (a) 畫面對拍 {ok_a}/{ok_a + bad_a}；渲染順序重放 {ok_r}/{ok_r + bad_r}；ops 內容未改動={ops_unchanged}")
    print(f"  (b) 旁白核對 {ck.ok}/{ck.ok + ck.bad}（數字 {ck.kinds['num'][0]}/{sum(ck.kinds['num'])}、行號 {ck.kinds['line'][0]}/{sum(ck.kinds['line'])}、字母 {ck.kinds['letter'][0]}/{sum(ck.kinds['letter'])}、變數敘述 {ck.kinds['stmt'][0]}/{sum(ck.kinds['stmt'])}）；claims {ck.claims_ok}/{ck.claims_ok + ck.claims_bad}")
    if intro_rep: print(f"  (d) intro 場景獨立驗證 {intro_rep.ok}/{intro_rep.ok + intro_rep.bad}（{len(intro_specs)} 場：{' '.join(sorted(intro_specs))}；revealAll={story.get('revealAll')}）")
    if sf_mode == "auto": print(f"  (e) 舞台自適應 stageFit=auto：A1 警示 {len(fit_ws)} 項（寫入 warnings.json type=stage_fit；明細見 pixel_table.py）")
    print(f"  (c) 規則 warning {len(warns)}；各場字數：" + " ".join(f"{i}:{n}" for i, _, n, _ in counts))
    for w in warns: print("   ⚠", w)
    for e in errors: print("   ✗", e)
    if errors:
        (out / "narr_verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        print(f"驗證失敗（{len(errors)} 項），story 已寫出但請修正 narration.json 後重跑。"); sys.exit(1)
    if not a.no_build:
        r = subprocess.run(["node", "scripts/story-build.mjs", a.new_folder, "--no-audio"], cwd=REPO, capture_output=True, text=True)
        print("  story-build:", r.stdout.strip().replace("\n", "\n   "), r.stderr.strip()[:300])
        bw = [l for l in r.stdout.splitlines() if l.startswith("⚠")]
        res["build_warnings"] = bw
        (out / "narr_verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        if bw or r.returncode: print(f"  build 有 {len(bw)} 個 warning"); sys.exit(1)
    else:
        (out / "narr_verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("  ✓ 全部通過")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("dump"); p.add_argument("folder"); p.set_defaults(fn=cmd_dump)
    p = sp.add_parser("apply"); p.add_argument("folder"); p.add_argument("narration"); p.add_argument("new_folder")
    p.add_argument("--no-build", action="store_true")
    p.add_argument("--stage-fit", choices=["auto", "off"], help="auto＝輸出 story 加 stageFit=auto（動畫區依內容自適應放大）並把最小可讀尺寸警示併入 warnings.json；off＝移除 stageFit 與 stage_fit 警示；不指定＝沿用 base（base 由 autoanim 產生時預設為 auto；舊 base 沒有 stageFit 則輸出與以前相同）")
    p.set_defaults(fn=cmd_apply)
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
