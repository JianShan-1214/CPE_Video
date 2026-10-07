"""缺元件偵測：依原始碼（tree-sitter 語意＋文字模式）＋ trace 形狀，辨識資料結構／演算法型態，
對照 coverage.py 的元件覆蓋表，產生警示（warnings.json）。autoanim 呼叫 detect(...)；獨立執行：
  python3 detect.py X.cpp   （只做原始碼層偵測，無 trace）
"""
import json, re, sys
from pathlib import Path
from coverage import COVERAGE, STATUS_ZH

try:
    from coverage import WITH_COMPONENT   # {type: (component, status, note)}：該元件被實際選用時的狀態
except ImportError:
    WITH_COMPONENT = {}


def strip_comments(t):
    def blank(m): return re.sub(r"[^\n]", " ", m.group(0))
    t = re.sub(r"/\*.*?\*/", blank, t, flags=re.S)
    t = re.sub(r"//[^\n]*", blank, t)
    t = re.sub(r'"(?:\\.|[^"\\])*"', lambda m: '"' + " " * (len(m.group(0)) - 2) + '"', t)
    return t


def line_of(t, pos): return t.count("\n", 0, pos) + 1


# 簡單 struct＝只有基本型別欄位（無指標／參考／陣列／預設值／成員函式／建構子／巢狀型別）。
# autoanim 用同一個判定決定 vector<P> 是否展開成每欄一列（p.s／p.i／p.j），detect 用它決定是否取消 struct 警告。
BASE_FIELD_RE = re.compile(r"^(int|long|longlong|unsigned|unsignedint|unsignedlong|unsignedlonglong|short|char|bool|double|float|string|size_t|int64_t|uint64_t|int32_t)$")   # 與 autoanim.BASE_RE 同一組型別
TREEISH_RE = re.compile(r"^(left|right|lc|rc|l|r|ls|rs|lson|rson|parent|par|fa|next|nxt|prev|ch|child|son)$")


def simple_structs(text):
    """{struct 名: [欄位名,...]}（依宣告順序）；只收『struct X { 基本型別 a, b; ... };』這種形狀"""
    t = strip_comments(text)
    out = {}
    for m in re.finditer(r"\bstruct\s+([A-Za-z_]\w*)\s*\{([^{}()]*)\}\s*;", t):
        fields, ok = [], True
        for piece in m.group(2).split(";"):
            piece = piece.strip()
            if not piece: continue
            mm = re.fullmatch(r"((?:const\s+)?(?:std::)?[A-Za-z_]\w*(?:\s+[A-Za-z_]\w*)*?)\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)", piece)
            if not mm: ok = False; break
            typ = re.sub(r"\s+", "", re.sub(r"\bconst\b", "", mm.group(1)).replace("std::", ""))
            if not BASE_FIELD_RE.match(typ): ok = False; break
            fields += [f.strip() for f in mm.group(2).split(",")]
        if ok and fields and len(set(fields)) == len(fields): out[m.group(1)] = fields
    return out


class Det:
    def __init__(self, text, events=None, plan=None, points=None, used=()):
        self.raw = text
        self.t = strip_comments(text)
        self.lines = self.raw.split("\n")
        self.events, self.plan, self.points, self.used = events or [], plan or {}, points or {}, set(used)
        self.hits = {}   # type -> dict(evidence=[(line,text)], names=set(), why=[...])

    def add(self, typ, line, name=None, why=None):
        h = self.hits.setdefault(typ, dict(evidence=[], names=[], why=[]))
        txt = self.lines[line - 1].strip() if line and 0 < line <= len(self.lines) else ""
        if line and not any(e["line"] == line for e in h["evidence"]) and len(h["evidence"]) < 6:
            h["evidence"].append(dict(line=line, code=txt[:80]))
        if name and name not in h["names"]: h["names"].append(name)
        if why and why not in h["why"]: h["why"].append(why)

    def find(self, pat, flags=0):
        return [(line_of(self.t, m.start()), m) for m in re.finditer(pat, self.t, flags)]

    # ── 資料結構 ──
    def scan(self):
        t = self.t
        self.adj_names = set(); self.mat_names = set(); self.tree_names = set()
        # 鄰接表：vector<int> g[N]；vector<vector<int>> g
        for ln, m in self.find(r"\bvector\s*<\s*(?:int|long\s+long|ll)\s*>\s*([A-Za-z_]\w*)\s*\[\s*[^\]]+\]"):
            self.adj_names.add(m.group(1)); self.add("graph_adj", ln, m.group(1), "vector<int> 陣列（每點一串鄰居）")
        for ln, m in self.find(r"\bvector\s*<\s*vector\s*<\s*(?:int|long\s+long|ll)\s*>\s*>\s*([A-Za-z_]\w*)\s*(\(|;|\{)?"):
            nm = m.group(1)
            # 鄰接表用法：g[u].push_back(v) 或 for (x : g[u])；dp(n+1, vector<int>(m+1)) 這種建構不算
            if re.search(r"\b" + nm + r"\s*\[[^\]]+\]\s*\.\s*(?:push_back|emplace_back)\s*\(", self.t) or re.search(r":\s*" + nm + r"\s*\[[^\]]+\]\s*\)", self.t):
                self.adj_names.add(nm); self.add("graph_adj", ln, nm, "vector<vector<int>>（push_back／逐鄰居走訪＝鄰接表）")
        # 帶權：vector<pair<..>> g[N] 或 vector<vector<pair
        for ln, m in self.find(r"\bvector\s*<\s*(?:vector\s*<\s*)?(?:pair|tuple)\s*<[^;{]*?>\s*>?\s*>?\s*([A-Za-z_]\w*)\s*(\[|;|\()"):
            self.add("graph_weighted", ln, m.group(1), "以 pair 存（鄰居, 權重）")
            self.add("pair", ln, m.group(1))
        for ln, m in self.find(r"\b(?:pair|tuple)\s*<[^;{()]*>\s*([A-Za-z_]\w*)"):
            self.add("pair", ln, m.group(1))
        # 鄰接矩陣／格子
        for ln, m in self.find(r"\b(?:int|long\s+long|ll|char|bool|double)\s+([A-Za-z_]\w*)\s*\[\s*([^\]]+)\]\s*\[\s*([^\]]+)\]"):
            self.mat_names.add(m.group(1))
        for ln, m in self.find(r"\bvector\s*<\s*vector\s*<\s*(?:int|long\s+long|ll|char|bool)\s*>\s*>\s*([A-Za-z_]\w*)"):
            self.mat_names.add(m.group(1))
        # 容器
        for typ, pat in (("queue", r"\bqueue\s*<"), ("queue", r"\bdeque\s*<"), ("stack", r"\bstack\s*<"),
                         ("priority_queue", r"\bpriority_queue\s*<"), ("map", r"\b(?:unordered_)?(?:multi)?map\s*<"),
                         ("set", r"\b(?:unordered_)?(?:multi)?set\s*<")):
            for ln, m in self.find(pat): self.add(typ, ln, None, m.group(0).strip("< "))
        # struct／class／指標
        simple = self.simple_ok()
        for ln, m in self.find(r"\b(struct|class)\s+([A-Za-z_]\w*)\s*\{"):
            if m.group(1) == "struct" and m.group(2) in simple:   # 簡單 struct 的 vector 已逐欄追蹤顯示 → 不警告（supported）
                self.add("struct_simple", ln, m.group(2), f"vector<{m.group(2)}> 逐欄顯示（{'／'.join(simple[m.group(2)])}）"); continue
            self.add("struct", ln, m.group(2), f"{m.group(1)} {m.group(2)}")
        for ln, m in self.find(r"\b[A-Za-z_]\w*\s*\*\s*([A-Za-z_]\w*)\s*(=|;|,|\))"):
            pre = t[max(0, m.start() - 12):m.start()]
            if re.search(r"[=+\-*/%<>!&|?:^~]\s*$", pre): continue   # a * b 的乘法，不是指標宣告
            if re.search(r"[(,]\s*$", pre) and not re.match(r"\s*(?:const\s+)?(?:int|long|char|double|bool|float|unsigned|auto|void|size_t|string|Node|TreeNode)\b", m.group(0)): continue
            if re.search(r"(return|\bcout|\bcin|[\w\)\]]\s*)$", pre) and not re.search(r"\b(int|long|char|double|bool|float|unsigned|auto|void|size_t|Node|TreeNode|struct)\s*$", pre): continue
            self.add("pointer", ln, m.group(1), "指標變數")
        for ln, m in self.find(r"\bnew\s+[A-Za-z_]"): self.add("pointer", ln, None, "new 配置")
        # 樹：left/right/parent 命名或 struct 有 left/right
        has_l = re.search(r"\b(?:int|long|vector<int>)\s+[^;]*?\b(left|lc|lch|lson|L)\s*\[|\bvector\s*<\s*int\s*>\s*(left|lc|lch|lson)\b", t)
        has_r = re.search(r"\b(?:int|long|vector<int>)\s+[^;]*?\b(right|rc|rch|rson|R)\s*\[|\bvector\s*<\s*int\s*>\s*(right|rc|rch|rson)\b", t)
        pats = [r"\b(?:left|lson|lch)\s*\[|\b(?:right|rson|rch)\s*\["] + ([r"\b(?:lc|rc)\s*\["] if has_l and has_r else []) + [r"\bch\s*\[\s*[^\]]+\]\s*\[\s*2\s*\]", r"\b(?:tree|tr)\s*\[[^\]]+\]\s*\.\s*(?:l|r|left|right)\b"]
        for pt in pats:
            for ln, m in self.find(pt):
                self.tree_names.add(m.group(0)); self.add("tree_array", ln, re.sub(r"\s*\[.*", "", m.group(0)), "left／right／ch[][2] 陣列表示的樹")
        if re.search(r"\b(left|right|lc|rc)\b\s*;", t) and "struct" in self.hits:
            for ln, m in self.find(r"\b(left|right|lc|rc)\b\s*;"): self.add("tree_struct", ln, None, "struct 內有 left／right 指標欄位")
        for ln, m in self.find(r"\bstruct\s+(?:Tree)?Node\b|\bTreeNode\b"): self.add("tree_struct", ln, None, "Node／TreeNode 結構")
        # 字串
        for ln, m in self.find(r"\b(?:std::)?string\s+([A-Za-z_]\w*)"): self.add("string", ln, m.group(1), "string 變數")
        for ln, m in self.find(r"\bgetline\s*\("): self.add("string", ln, None, "getline")
        for ln, m in self.find(r"\.substr\s*\(|\.find\s*\(|\.compare\s*\("): self.add("string", ln, None, "substr／find（視窗與匹配不顯示）")
        # 格子搜尋
        if re.search(r"\b(dx|dy|dir|dirs|di|dj)\s*\[[^\]]*\]\s*=\s*\{", t) or re.search(r"\{\s*-?1\s*,\s*0\s*,\s*1\s*,\s*0\s*\}", t):
            for ln, m in self.find(r"\b(dx|dy|dir|dirs|di|dj)\s*\[[^\]]*\]\s*=\s*\{"): self.add("grid", ln, m.group(1), "方向陣列 dx／dy")
        # 遞迴
        self.rec = []
        for m in re.finditer(r"(?m)^[ \t]*(?:[A-Za-z_][\w:<>,\s\*&]*?)\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:const\s*)?\{", t):
            name = m.group(1)
            if name in ("if", "for", "while", "switch", "main"): continue
            depth, i, s = 1, m.end(), m.end()
            while i < len(t) and depth:
                depth += (t[i] == "{") - (t[i] == "}"); i += 1
            body = t[s:i]
            if re.search(r"\b" + re.escape(name) + r"\s*\(", body):
                self.rec.append(name); self.add("recursion", line_of(t, m.start()), name, f"{name}() 呼叫自己")
        # 並查集
        for ln, m in self.find(r"\b(?:find|getf|root|Find)\s*\([^)]*\)\s*\{[^}]*=\s*(?:find|getf|root|Find)\s*\(|\b([A-Za-z_]\w*)\s*\[\s*([A-Za-z_]\w*)\s*\]\s*=\s*(?:find|getf|root)\s*\(\s*\1\s*\[\s*\2\s*\]") + \
                self.find(r"\b(?:parent|par|fa|pa|p)\s*\[\s*(\w+)\s*\]\s*==\s*\1\b"):
            self.add("union_find", ln, None, "find 路徑壓縮／parent[x]==x")
        # 雜湊／桶
        for ln, m in self.find(r"\b([A-Za-z_]\w*)\s*\[\s*[^\]\[]*%\s*([A-Za-z_]\w*|\d+)\s*\]"):
            self.add("hash", ln, m.group(1), "以 % 取餘落入桶")
        # DP 表（僅資訊）
        for ln, m in self.find(r"\b(dp|f|g|memo)\s*\[[^\]]+\](?:\s*\[[^\]]+\])?\s*=\s*(?:max|min)"): self.add("dp_table", ln, m.group(1), "dp 轉移")

    def simple_ok(self):
        """可取消 struct 警告的簡單 struct——欄位全是基本型別、名稱／欄位不像樹或鏈結節點、
        原始碼裡這個型別只出現在 vector<P> 與 const P& 參數（沒有單一物件、陣列、pair／map／priority_queue 元素等其他用法），
        且（有 trace 時）畫面確實有它的欄位列（plan.info 有 名.欄位）。其他 struct 照舊警告。"""
        t, res = self.t, {}
        info = (self.plan or {}).get("info")
        for nm, fs in simple_structs(self.raw).items():
            if re.fullmatch(r"(?:Tree)?Node|TreeNode|Edge", nm) or any(TREEISH_RE.match(f) for f in fs): continue
            uses = [m for m in re.finditer(r"\b" + re.escape(nm) + r"\b", t)]
            ok_use = vec = 0
            for m in uses:
                pre, post = t[max(0, m.start() - 40):m.start()], t[m.end():m.end() + 20]
                if re.search(r"\bstruct\s+$", pre): ok_use += 1                                   # 定義本身
                elif re.search(r"\bvector\s*<\s*$", pre) and re.match(r"\s*>", post): ok_use += 1; vec += 1
                elif re.search(r"\bconst\s+$", pre) and re.match(r"\s*&", post): ok_use += 1      # lambda／比較函式參數 const P &x
            if not vec or ok_use != len(uses): continue
            if info and not any("." in k and k.split(".", 1)[1] in fs for k in info): continue
            res[nm] = fs
        return res

    # ── 演算法 ──
    def algos(self):
        t = self.t
        algos = []
        has_q = "queue" in self.hits and re.search(r"\bqueue\s*<", t)
        nb = r"for\s*\(\s*(?:auto|int)\s*&?\s*\w+\s*:\s*(\w+)\s*\[|for\s*\(\s*int\s+\w+\s*=\s*0\s*;[^;]*;\s*\w+\+\+\s*\)\s*if\s*\(\s*(\w+)\s*\[\s*\w+\s*\]\s*\[\s*\w+\s*\]"
        neigh = self.find(nb)
        if has_q and neigh and re.search(r"\.push\s*\(", t) and re.search(r"\.pop\s*\(", t) and "priority_queue" not in self.hits:
            algos.append(("bfs", neigh[0][0]))
        if self.rec and neigh and any(re.search(r"\b" + n + r"\s*\(", t) for n in self.rec) and re.search(r"\b(vis|visited|used|seen|mark)\b", t) and not has_q:
            algos.append(("dfs", neigh[0][0]))
        if "stack" in self.hits and re.search(r"\bstack\s*<", t) and neigh and not self.rec: algos.append(("dfs_stack", neigh[0][0]))
        if "priority_queue" in self.hits and neigh and re.search(r"\b(dist|d)\s*\[", t): algos.append(("dijkstra", neigh[0][0]))
        fl = self.find(r"\b(\w+)\s*\[\s*i\s*\]\s*\[\s*j\s*\]\s*=\s*(?:min|max)?\s*\(?\s*\1\s*\[\s*i\s*\]\s*\[\s*j\s*\]\s*,\s*\1\s*\[\s*i\s*\]\s*\[\s*k\s*\]\s*\+\s*\1\s*\[\s*k\s*\]\s*\[\s*j\s*\]")
        if fl: algos.append(("floyd", fl[0][0]))
        for a, ln in algos:
            for typ in ("graph_adj",) if self.adj_names else (("graph_matrix",) if self.mat_names else ()):
                self.add(typ, ln, None, f"演算法：{a}")
        if fl and not self.adj_names: self.add("graph_matrix", fl[0][0], None, "Floyd：矩陣為圖")
        self.algo_list = algos
        # 矩陣當圖：g[u][v] 與 n×n 迴圈、名稱像圖
        for nme in self.mat_names:
            if re.search(r"\b(?:g|adj|graph|w|e|d|dis|dist|mp)\b", nme) and (fl or algos or re.search(r"\b" + nme + r"\s*\[\s*\w+\s*\]\s*\[\s*\w+\s*\]\s*(?:==|!=|>|<)\s*(?:1|0|INF)", t)):
                self.add("graph_matrix", 0, nme, "2D 陣列名稱／用法像鄰接矩陣")
        # 格子：2D 陣列 + 方向或 '#'/'.' 比較
        if self.mat_names and ("grid" in self.hits or re.search(r"==\s*'[#.*SE]'", t)):
            self.add("grid", 0, next(iter(self.mat_names)), "2D 字元／旗標格 + 迷宮式走訪")
        # 槽位列（排列／配置）：used 旗標 + 結果陣列賦值；或 next_permutation
        slots_ln = self.find(r"\bnext_permutation\s*\(")
        for ln, m in slots_ln: self.add("slots", ln, None, "next_permutation（排列）")
        used = self.find(r"\b(used|vis|visited|taken|chosen|picked)\s*\[[^\]]+\]\s*=\s*(?:1|true)")
        res = self.find(r"\b(res|ans|perm|out|pos|place|arr|sol|order)\s*\[[^\]]+\]\s*=\s*(?!\s*\d+\s*[;,])")
        if used and res and not any(a in ("bfs", "dfs", "dijkstra") for a, _ in algos):
            self.add("slots", used[0][0], None, "以 used 旗標挑人並寫入位置陣列（配置／排列）")
            self.add("slots", res[0][0], res[0][1].group(1), "結果位置陣列")

    def trace_shape(self):
        """trace 形狀補強：事件顯示的變數種類"""
        notes = (self.plan or {}).get("notes") or []
        if notes:
            for n in notes: self.add("truncated", 0, None, n)
        # 已被插樁略過的宣告（型別不支援）：與 tracer 支援型別比對
        shown = set((self.plan or {}).get("arrays", [])) | set((self.plan or {}).get("chips", []))
        for typ in ("map", "set", "pair", "priority_queue", "struct", "pointer"):
            if typ in self.hits: self.hits[typ]["why"].append("該變數未被追蹤，畫面不顯示")
        # 追蹤到、但形狀是 2D 不等長 → 鄰接表
        for k, v in ((self.plan or {}).get("info") or {}).items():
            if v.get("rowlab"): self.add("graph_adj", 0, k, "trace：不等長二維列表")

    def run(self):
        self.scan(); self.algos(); self.trace_shape()
        # 元件被實際選用 → 該型態一定要出現在清單（即使原始碼層沒偵測到），狀態依 WITH_COMPONENT 判定
        TYPE_OF = {"slots": "slots", "tree": "tree_array", "keyed:map": "map", "keyed:set": "set",
                   "seq:queue": "queue", "seq:stack": "stack", "seq:priority_queue": "priority_queue"}
        for ci in (self.plan or {}).get("comp_info", []):
            typ = TYPE_OF.get(ci.get("used_name"))
            if ci.get("kind") == "graph": typ = "graph_matrix" if ci.get("form") == "matrix" else "graph_adj"
            if typ and typ not in self.hits: self.add(typ, 0, ci["vars"][0], "autoanim 依 trace 選用了對應元件")
        out = []
        for typ, h in self.hits.items():
            c = COVERAGE[typ]
            st, now, missing, eta = c["status"], c["now"], c["missing"], c["eta"]
            comp = WITH_COMPONENT.get(typ)
            if comp and comp[0] in self.used:
                st, now = comp[1], comp[2]
                missing = comp[3] if len(comp) > 3 else (c["missing"] if comp[1] != "supported" else "—")
                eta = comp[4] if len(comp) > 4 else (eta if comp[1] != "supported" else "—")
            if st == "supported": continue
            if typ == "truncated" or (typ in ("dp_table",)): pass
            ev = h["evidence"]
            names = "、".join(h["names"][:4])
            fmt = (f"【{STATUS_ZH[st]}】{c['name']}" + (f"（{names}）" if names else "") +
                   f"｜缺：{missing}｜目前：{now}｜補元件：{eta}")
            out.append(dict(type=typ, name=c["name"], status=st, evidence=ev, variables=h["names"], why=h["why"],
                            now=now, missing=missing, eta=eta, message=fmt))
        order = dict(unsupported=0, degraded=1, partial=2)
        out.sort(key=lambda w: (order.get(w["status"], 3), w["type"]))
        return out, getattr(self, "algo_list", [])


def detect(src_text, events=None, plan=None, points=None, used=()):
    d = Det(src_text, events, plan, points, used)
    ws, algos = d.run()
    return ws, algos


def print_warnings(ws, algos, out=sys.stdout):
    if algos: print(f"  偵測到演算法：{', '.join(a for a, _ in algos)}", file=out)
    for w in ws:
        ev = "、".join(f"L{e['line']}" for e in w["evidence"] if e["line"])
        print(f"  ⚠ {w['message']}" + (f"｜證據：{ev}" if ev else ""), file=out)
    if ws:
        nu = sum(1 for w in ws if w["status"] == "unsupported"); nd = sum(1 for w in ws if w["status"] == "degraded"); npr = sum(1 for w in ws if w["status"] == "partial")
        print(f"\n██ 缺元件警示 {len(ws)} 項（不支援 {nu}／退化 {nd}／部分 {npr}）— 出片前必須告知使用者（見 warnings.json）██", file=out)


if __name__ == "__main__":
    ws, algos = detect(Path(sys.argv[1]).read_text())
    print_warnings(ws, algos)
