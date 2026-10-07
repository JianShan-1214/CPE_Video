#!/usr/bin/env python3
"""autoanim：貼「答案 C++ + 一組小輸入」→ 自動追蹤 → 事件流 → Story 基礎版動畫（不需手寫座標／時間）。

用法（需 Python 3.12+，並安裝 tree-sitter、tree-sitter-cpp、anyio；沙箱 runner 由 repo 的 backend/ 提供）：
  python autoanim.py <folder> --cpp ans.cpp --stdin in.txt --expect out.txt --title "題目"
輸出 public/<folder>/{story.json,code.cpp,trace_events.json,verify.json}
"""
import argparse, asyncio, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).parent))
import detect as detect_mod
import stagefit   # CPE-003：舞台自適應（story.stageFit）與 stage_fit 警示
import comps as comps_mod
from verifylib import check_key, got_of
import tree_sitter_cpp
from tree_sitter import Language, Parser
from app.services.trace import runner
from app.services.trace.runner import check_equivalence

HERE = Path(__file__).parent
runner.HEADER_PATH = HERE / "cpe_trace_ext.hpp"
CPP = Language(tree_sitter_cpp.language())

BASE_RE = re.compile(r"^(int|long|longlong|unsigned|unsignedint|unsignedlong|unsignedlonglong|short|char|bool|double|float|string|std::string|size_t|int64_t|uint64_t|int32_t)$")
SIZE_RE = re.compile(r"^[A-Za-z0-9_+\-\* ]+$")
LOOPS = ("for_statement", "while_statement", "do_statement", "for_range_loop")
# CPE-008：簡單 struct（只有基本型別欄位，見 detect.simple_structs）名稱 → 欄位名清單；instrument() 依原始碼設定。
# 空（程式裡沒有這種 struct）＝與以前逐值相同；vector<P> 會展開成每欄一列 p.s／p.i／p.j（kind=seq，插樁用 CPE_FLD）
STRUCTS = {}
SPLIT2_STRUCT_W, SPLIT2_STRUCT_H = 940, 580   # 940×580 的內容框在 split2 右窗（1020×800）fit 倍率 = min(1020/940, 800/580) ≈ 1.085，高度不再擠壓格子；580＝overlapcheck 出界上限（585）與 layout 既有的 580 延伸高


# ───────────────────────── 1. 靜態分析與插樁 ─────────────────────────
class Var:
    def __init__(self, name, kind, expr, dims=None):
        self.name, self.kind, self.expr, self.dims = name, kind, expr, dims or []
    def __repr__(self): return f"Var({self.name},{self.kind})"


def txt(n, src): return src[n.start_byte:n.end_byte].decode()


def find_aliases(src_text):
    al = {}
    for m in re.finditer(r"typedef\s+([\w\s:]+?)\s+(\w+)\s*;", src_text):
        al[m.group(2)] = m.group(1)
    for m in re.finditer(r"using\s+(\w+)\s*=\s*([\w\s:]+?)\s*;", src_text):
        al[m.group(1)] = m.group(2)
    return al


def norm_type(t, aliases):
    t = re.sub(r"\b(const|static|register|volatile)\b", "", t)
    t = re.sub(r"\s+", "", t.replace("std::", ""))
    for a, v in aliases.items():
        if t == a: t = re.sub(r"\s+", "", v.replace("std::", ""))
    return t


def type_kind(t):
    """'base' | ('seq',inner) | None"""
    if BASE_RE.match(t): return "base"
    m = re.match(r"^(?:unordered_)?map<([^,<>]+),([^,<>]+)>$", t)
    if m and BASE_RE.match(m.group(1)) and BASE_RE.match(m.group(2)): return "map"
    m = re.match(r"^(?:unordered_)?(?:multi)?set<([^,<>]+)>$", t)
    if m and BASE_RE.match(m.group(1)): return "set"
    m = re.match(r"^priority_queue<([^,<>]+)(?:,.*)?>$", t)
    if m and BASE_RE.match(m.group(1)): return "seq"
    m = re.match(r"^(vector|deque|stack|queue)<(.+)>$", t)
    if m:
        inner = m.group(2)
        if BASE_RE.match(inner): return "seq"
        mm = re.match(r"^vector<(.+)>$", inner)
        if m.group(1) == "vector" and mm and BASE_RE.match(mm.group(1)): return "seq2"
        if m.group(1) == "vector" and inner in STRUCTS: return "sseq"   # CPE-008：vector<P>（P 為簡單 struct）
    return None


def parse_declarator(d, src, tkind, is_str, vec_elem=False):
    """回傳 Var 或 None"""
    sizes = []
    while True:
        t = d.type
        if t == "identifier":
            name = txt(d, src)
            if sizes and tkind == "seq" and len(sizes) == 1 and vec_elem and SIZE_RE.match(sizes[0]):
                return Var(name, "arrv", f"CPE_ARRV({name}, {sizes[0]})", sizes)   # vector<int> g[N]：鄰接表
            if sizes:
                if tkind != "base" or not all(SIZE_RE.match(s) for s in sizes): return None
                sizes = sizes[::-1]
                if len(sizes) == 1: return Var(name, "arr1", f"CPE_ARR({name}, {sizes[0]})", sizes)
                if len(sizes) == 2: return Var(name, "arr2", f"CPE_ARR2({name}, {sizes[0]}, {sizes[1]})", sizes)
                return None
            if tkind == "base": return Var(name, "str" if is_str else "scalar", name)
            if tkind in ("seq", "seq2", "map", "set"): return Var(name, tkind, name)
            if tkind == "sseq": return Var(name, "sseq", name)   # CPE-008：decl_vars 再展開成每欄一個 seq
            return None
        if t == "function_declarator" and tkind in ("seq", "seq2", "base", "map", "set", "sseq") and not sizes:
            inner = d.child_by_field_name("declarator")
            if inner is not None and inner.type == "identifier":  # `vector<int> res(n)` 會被誤判成函式宣告
                d = inner
                continue
            return None
        if t == "init_declarator":
            d = d.child_by_field_name("declarator")
        elif t == "array_declarator":
            sz = d.child_by_field_name("size")
            sizes.append(txt(sz, src) if sz is not None else "")
            d = d.child_by_field_name("declarator")
        elif t == "reference_declarator":
            nxt = [c for c in d.named_children]
            if not nxt: return None
            d = nxt[0]
        else:
            return None
        if d is None: return None


def decl_vars(node, src, aliases):
    tn = node.child_by_field_name("type")
    if tn is None: return []
    t = norm_type(txt(tn, src), aliases)
    tk = type_kind(t)
    if tk is None: return []
    is_str = t == "string"
    vec_elem = bool(re.match(r"^vector<[a-z0-9_]+>$", t)) and BASE_RE.match(t[7:-1]) is not None
    out = []
    for c in node.children_by_field_name("declarator"):
        v = parse_declarator(c, src, tk, is_str, vec_elem)
        if v and v.kind == "sseq":   # CPE-008：vector<P> p → p.s／p.i／p.j（每欄一列，CPE_FLD 取欄位）
            out += [Var(f"{v.name}.{f}", "seq", f"CPE_FLD({v.name}, {f})") for f in STRUCTS[t[7:-1]]]
        elif v: out.append(v)
    return out


def param_vars(fn, src, aliases):
    out = []
    decl = fn.child_by_field_name("declarator")
    while decl is not None and decl.type != "function_declarator":
        decl = decl.child_by_field_name("declarator")
    if decl is None: return out
    params = decl.child_by_field_name("parameters")
    if params is None: return out
    for p in params.named_children:
        if p.type in ("parameter_declaration", "optional_parameter_declaration"):
            out += decl_vars_param(p, src, aliases)
    return out


def decl_vars_param(p, src, aliases):
    tn = p.child_by_field_name("type")
    d = p.child_by_field_name("declarator")
    if tn is None or d is None: return []
    t = norm_type(txt(tn, src), aliases)
    tk = type_kind(t)
    if tk is None: return []
    v = parse_declarator(d, src, tk, t == "string")
    return [v] if v and v.kind in ("scalar", "str", "seq", "seq2") else []


def visible_vars(node, src, aliases, include_self_decl=False):
    chain = []
    n = node
    while n is not None:
        chain.append(n); n = n.parent
    chain.reverse()
    vars_ = {}
    def add(vs):
        for v in vs: vars_[v.name] = v
    for i in range(len(chain) - 1):
        A, C = chain[i], chain[i + 1]
        if A.type in ("translation_unit", "compound_statement"):
            for s in A.children:
                if s.start_byte >= C.start_byte: break
                if s.type == "declaration" and (A.type == "compound_statement" or True):
                    add(decl_vars(s, src, aliases))
        elif A.type == "function_definition":
            add(param_vars(A, src, aliases))
        elif A.type == "for_statement":
            ini = A.child_by_field_name("initializer")
            if ini is not None and ini.type == "declaration" and C.start_byte >= ini.end_byte:
                add(decl_vars(ini, src, aliases))
        elif A.type == "for_range_loop":
            tn = A.child_by_field_name("type"); d = A.child_by_field_name("declarator")
            if tn is not None and d is not None and C.start_byte >= d.end_byte:
                t = norm_type(txt(tn, src), aliases)
                if type_kind(t) == "base":
                    v = parse_declarator(d, src, "base", t == "string")
                    if v and v.kind in ("scalar", "str"): add([v])
    if include_self_decl and node.type == "declaration":
        add(decl_vars(node, src, aliases))
    return vars_


def instrument(source_text, drop_nonliteral=False):
    src = source_text.encode()
    parser = Parser(CPP)
    tree = parser.parse(src)
    aliases = find_aliases(source_text)
    STRUCTS.clear(); STRUCTS.update(detect_mod.simple_structs(source_text))   # CPE-008（與 detect 的 struct 警告共用同一個判定）
    edits = []   # (pos, seq, text)
    seq = [0]
    points = {}  # id -> dict(line0, line1, names, start_byte, kind)
    def edit(pos, text):
        edits.append((pos, seq[0], text)); seq[0] += 1
    def snap_text(node, include_self=False):
        vs = visible_vars(node, src, aliases, include_self)
        if drop_nonliteral:
            vs = {k: v for k, v in vs.items() if not (v.kind in ("arr1", "arr2") and not all(re.fullmatch(r"\d+", s) for s in v.dims))}
        if not vs: return ""
        pid = len(points)
        points[pid] = dict(line0=node.start_point[0] + 1, line1=node.end_point[0] + 1, names=list(vs.keys()),
                           kinds={k: v.kind for k, v in vs.items()}, dims={k: v.dims for k, v in vs.items()},
                           start=node.start_byte)
        return f" CPE_SNAP({pid}, {', '.join(v.expr for v in vs.values())});"
    def wrap(body):
        if body is None: return
        if body.type == "compound_statement":
            visit(body); return
        edit(body.start_byte, "{")
        if body.type in ("expression_statement", "declaration"):
            s = snap_text(body, True)
            edit(body.end_byte, s + " }")
        else:
            visit(body)
            edit(body.end_byte, " }")
    def visit(node):
        t = node.type
        if t == "compound_statement":
            for c in node.children:
                if c.type in ("expression_statement", "declaration"):
                    s = snap_text(c, True)
                    if s: edit(c.end_byte, s)
                elif c.type != "comment": visit(c)
        elif t == "if_statement":
            wrap(node.child_by_field_name("consequence"))
            alt = node.child_by_field_name("alternative")
            if alt is not None:
                inner = [c for c in alt.named_children]
                if alt.type == "else_clause" and inner:
                    b = inner[0]
                    if b.type == "if_statement": visit(b)
                    else: wrap(b)
                else: wrap(alt)
        elif t in LOOPS:
            wrap(node.child_by_field_name("body"))
        elif t == "function_definition":
            visit(node.child_by_field_name("body"))
        elif t == "translation_unit":
            for c in node.children: visit(c)
        elif t in ("namespace_definition",):
            for c in node.children: visit(c)
    visit(tree.root_node)
    out = bytearray(src)
    for pos, _, text in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        pass
    # 套用：同位置依 seq 由小到大插入 → 由後往前處理時，同位置要由大 seq 先插
    buf = src
    for pos in sorted({e[0] for e in edits}, reverse=True):
        ins = "".join(t for p, s, t in sorted([e for e in edits if e[0] == pos], key=lambda e: e[1]))
        buf = buf[:pos] + ins.encode() + buf[pos:]
    new_src = '#include "cpe_trace.hpp"\n' + buf.decode()
    return new_src, points, tree, src, aliases


def find_uninit_locals(tree, src, aliases):
    """函式內、沒有初始值的純量區域變數名（值是殘值，不可外露）"""
    names = set()
    def walk(n, in_fn):
        if n.type == "function_definition": in_fn = True
        if in_fn and n.type == "declaration":
            tn = n.child_by_field_name("type")
            if tn is not None and type_kind(norm_type(txt(tn, src), aliases)) == "base":
                for c in n.children_by_field_name("declarator"):
                    if c.type == "identifier": names.add(txt(c, src))
        for c in n.children: walk(c, in_fn)
    walk(tree.root_node, False)
    return names


def loop_scalars(tree, src, aliases):
    """CPE-008 --show-born：main 裡、宣告在迴圈內（迴圈本體或 for 初始化）的基本型別純量名"""
    names = set()
    def walk(n, in_main, in_loop):
        if n.type == "function_definition":
            d = n.child_by_field_name("declarator")
            in_main = d is not None and txt(d, src).startswith("main")
        if in_main and in_loop and n.type == "declaration":
            tn = n.child_by_field_name("type")
            if tn is not None and type_kind(norm_type(txt(tn, src), aliases)) == "base":
                for c in n.children_by_field_name("declarator"):
                    v = parse_declarator(c, src, "base", False)
                    if v: names.add(v.name)
        for c in n.children: walk(c, in_main, in_loop or (in_main and n.type in LOOPS))
    walk(tree.root_node, False, False)
    return names


def index_pointers(tree, src):
    """array name -> set of scalar names used directly as its index (a[i], a[i+1], a[i-1])"""
    res = {}
    def walk(n):
        if n.type == "subscript_expression":
            arr = n.child_by_field_name("argument")
            idxs = n.children_by_field_name("indices")
            if arr is not None and arr.type == "identifier":
                name = txt(arr, src)
                for ix in idxs:
                    for m in re.finditer(r"[A-Za-z_]\w*", txt(ix, src)):
                        res.setdefault(name, set()).add(m.group(0))
        for c in n.children: walk(c)
    walk(tree.root_node)
    return res


# ───────────────────────── 2. 執行與事件流 ─────────────────────────
async def run_program(source_text, stdin, expect):
    last_err = None
    for drop in (False, True):
        inst, points, tree, src, aliases = instrument(source_text, drop)
        eq = await check_equivalence(source_text, inst, stdin, expect)
        if eq.traced.compile.ok:
            return eq, inst, points, tree, src, aliases
        last_err = eq.traced.compile.errors
    raise RuntimeError("插樁後編譯失敗：\n" + (last_err or ""))


def build_events(eq, points):
    state, events = {}, []
    for s in eq.traced.snapshots:
        meta = points.get(s["id"])
        if not meta: continue
        changes, born = {}, []
        for k, v in s["values"].items():
            if k in state:
                if state[k] != v: changes[k] = (state[k], v)
            else: born.append(k)
            state[k] = v
        events.append(dict(pid=s["id"], line0=meta["line0"], line1=meta["line1"], changes=changes, born=born,
                           values={k: json.loads(json.dumps(v)) for k, v in s["values"].items()},
                           first=[k for k in s["values"] if k not in (events[-1]["seen"] if events else set())] if False else None))
    # 累積 seen / 每個事件後完整狀態
    full = {}
    for e in events:
        full.update(e["values"])
        e["state"] = json.loads(json.dumps(full))
    return events


# ───────────────────────── 3. 顯示規劃 ─────────────────────────
def is_empty(v): return v in (0, "", False, None)


def plan_display(events, points, ptr_map, max1=16, max2r=8, max2c=10, exclude=(), born=()):
    """born（CPE-008 --show-born）：在 main 迴圈內宣告、出生過但值從未改變的純量也顯示；預設空＝與以前相同"""
    kinds, dims = {}, {}
    for m in points.values():
        kinds.update(m["kinds"]); dims.update(m["dims"])
    changed = {}
    first_seen = {}
    last = {}
    for ei, e in enumerate(events):
        for k, v in e["values"].items():
            if k not in first_seen: first_seen[k] = v
        for k in e["changes"]: changed[k] = changed.get(k, 0) + 1
    shown = [k for k in kinds if (changed.get(k) or (k in born and kinds[k] == "scalar")) and k in last.keys() | set(first_seen)]
    # 活動長度
    info = {}
    notes = []
    for k in shown:
        kd = kinds[k]
        if kd in ("arr1", "seq", "str"):
            mx = 0
            base = first_seen[k]
            touched = set()
            for e in events:
                v = e["values"].get(k)
                if v is None or kd != "arr1": continue
                for i, x in enumerate(v):
                    if i < len(base) and x != base[i]: touched.add(i)
            for e in events:
                v = e["values"].get(k)
                if v is None: continue
                vs = list(v) if not isinstance(v, str) else list(v)
                n_ = len(vs)
                if kd == "seq" or kd == "str": mx = max(mx, n_)
                for i, x in enumerate(vs):
                    if kd == "arr1":
                        if i in touched: mx = max(mx, i + 1)
                    elif i >= len(base) or x != base[i] or not is_empty(x): mx = max(mx, i + 1)
            mx = max(mx, 1)
            if mx > max1 and k not in exclude: notes.append(f"{k} 共 {mx} 格，只顯示前 {max1} 格")
            if mx > max1: mx = max1
            info[k] = dict(kind=kd, n=mx, touched=touched if kd == 'arr1' else None, base=list(base) if kd == 'arr1' else None)
        elif kd in ("arr2", "seq2", "arrv"):
            mr = mc = 0
            touched2 = set()
            fs_ = first_seen[k]
            for e in events:
                v = e["values"].get(k)
                if v is None: continue
                for i, row in enumerate(v):
                    for j, x in enumerate(row):
                        if kd == "arr2":
                            if i < len(fs_) and j < len(fs_[i]) and x != fs_[i][j]:
                                touched2.add((i, j)); mr, mc = max(mr, i + 1), max(mc, j + 1)
                        elif kd == "arrv" or not is_empty(x) or (i < len(fs_) and j < len(fs_[i]) and x != fs_[i][j]):
                            mr, mc = max(mr, i + 1), max(mc, j + 1)
            mr, mc = max(mr, 1), max(mc, 1)
            if (mr > max2r or mc > max2c) and k not in exclude: notes.append(f"{k} 為 {mr}×{mc}，只顯示左上 {min(mr, max2r)}×{min(mc, max2c)}")
            info[k] = dict(kind="arr2", r=min(mr, max2r), c=min(mc, max2c), touched=touched2 if kd == "arr2" else None, base=fs_ if kd == "arr2" else None, real2=kd != "arr2", rowlab=kd == "arrv")
        elif kd == "scalar":
            info[k] = dict(kind="scalar")
        elif kd in ("map", "set"):
            info[k] = dict(kind=kd)
    # 指標（markers）：用在已顯示 1D 陣列當索引、且會變的純量
    arr1 = [k for k in info if info[k]["kind"] in ("arr1", "seq", "str") and k not in exclude]
    ptrs = {}
    marker_vars = set()
    for a in arr1:
        # CPE-008：struct 欄位列 p.s 用 p[k] 的索引（ptr_map 以陣列名 p 記錄）
        for p in sorted(ptr_map.get(a, ()) if "." not in a else ptr_map.get(a.split(".")[0], ())):
            if p in info and info[p]["kind"] == "scalar" and p not in arr1:
                ptrs.setdefault(a, []).append(p); marker_vars.add(p)
    chips = [k for k in info if info[k]["kind"] == "scalar" and k not in marker_vars]
    chips.sort(key=lambda k: -changed.get(k, 0))
    if len(chips) > 8: notes.append(f"純量變數只顯示變動最多的 8 個（略過 {len(chips) - 8} 個）"); chips = chips[:8]
    chips = [k for k in info if k in chips]
    arrays = [k for k in info if info[k]["kind"] in ("arr1", "seq", "str", "arr2") and k not in exclude]
    return dict(info=info, chips=chips, arrays=arrays, ptrs=ptrs, marker_vars=marker_vars, notes=notes, changed=changed)


from layoutlib import layout, build_geometry, marker_els, make_cell_fn, cell_text   # CPE-003：版面幾何抽成純函式模組（可離線測試）


def board_state(plan, state):
    """state(變數→值) → 元素 id → text/visible"""
    info = plan["info"]; out = {}
    for k in plan["chips"]:
        if k in state: out[f"v_{k}"] = ("?" if plan.get("garbage", {}).get(k) == state[k] else cell_text(state[k]), True)
    for a in plan["arrays"]:
        ai = info[a]; v = state.get(a)
        if v is None: continue
        if ai["kind"] != "arr2":
            seq = list(v) if not isinstance(v, str) else list(v)
            for i in range(ai["n"]):
                if i >= len(seq): out[f"c_{a}_{i}"] = ("", False)
                elif ai.get("touched") is not None and isinstance(seq[i], int) and i < len(ai["base"]) and seq[i] == ai["base"][i] and seq[i] != 0: out[f"c_{a}_{i}"] = ("?", True)
                else: out[f"c_{a}_{i}"] = (cell_text(seq[i]), True)
        else:
            if ai.get("rowlab"):
                for i in range(ai["r"]): out[f"r_{a}_{i}"] = (str(i), True)
            for i in range(ai["r"]):
                for j in range(ai["c"]):
                    ok = i < len(v) and j < len(v[i])
                    if ok and ai.get("touched") is not None and isinstance(v[i][j], int) and i < len(ai["base"]) and j < len(ai["base"][i]) and v[i][j] == ai["base"][i][j] and v[i][j] != 0: out[f"c_{a}_{i}_{j}"] = ("?", True)
                    else: out[f"c_{a}_{i}_{j}"] = (cell_text(v[i][j]), True) if ok else ("", False)
    return out


# ───────────────────────── 4. Story 產生 ─────────────────────────
def top_units(tree, src, points, events):
    main = None
    for c in tree.root_node.children:
        if c.type == "function_definition":
            d = c.child_by_field_name("declarator")
            if d is not None and txt(d, src).startswith("main"): main = c
    if main is None: return []
    hits = {}
    for e in events: hits[e["pid"]] = hits.get(e["pid"], 0) + 1
    by_start = {m["start"]: pid for pid, m in points.items()}
    def direct_ids(body):
        return [by_start[c.start_byte] for c in body.children if c.start_byte in by_start]
    def is_once(s):
        body = s.child_by_field_name("body")
        if body is None or body.type != "compound_statement": return False
        ids = direct_ids(body)
        return bool(ids) and max(hits.get(i, 0) for i in ids) == 1
    def units(body):
        out = []
        for s in body.children:
            if s.type in ("{", "}", "comment"): continue
            if s.type in LOOPS and is_once(s):
                out += units(s.child_by_field_name("body"))
            else:
                out.append(s)
        return out
    return [dict(type=s.type, l0=s.start_point[0] + 1, l1=s.end_point[0] + 1) for s in units(main.child_by_field_name("body"))], main.start_point[0] + 1


KIND = {"for_statement": "迴圈", "while_statement": "迴圈", "do_statement": "迴圈", "for_range_loop": "迴圈", "if_statement": "判斷"}


def phrase(name, old, new, kind):
    if kind in ("arr1", "seq", "str"):
        ch = [i for i in range(max(len(old), len(new))) if (old[i] if i < len(old) else None) != (new[i] if i < len(new) else None)]
        if len(ch) == 1 and ch[0] < len(new): return f"{name}[{ch[0]}] 變成 {cell_text(new[ch[0]])}"
        return f"{name} 有 {len(ch)} 格更新"
    if kind in ("arr2", "seq2", "arrv"):
        ch = [(i, j) for i, row in enumerate(new) for j, x in enumerate(row)
              if not (i < len(old) and j < len(old[i]) and old[i][j] == x)]
        if len(ch) == 1: return f"{name}[{ch[0][0]}][{ch[0][1]}] 變成 {cell_text(new[ch[0][0]][ch[0][1]])}"
        return f"{name} 有 {len(ch)} 格更新"
    return f"{name} 變成 {cell_text(new)}"


def narrow_w(args):
    """D-020 E3：虛擬舞台寬。--stage-w 明確指定優先；否則 --layout split2 → 1000（只對有頂部槽位列的 story 生效，layoutlib.is_narrow），其餘 1200（舊行為）"""
    w = getattr(args, "stage_w", None)
    if w: return w
    return 1000 if getattr(args, "layout", "split") == "split2" else 1200


def generate(folder, args, eq, points, tree, src, aliases, events, src_text):
    ptr_map = index_pointers(tree, src)
    born = loop_scalars(tree, src, aliases) if getattr(args, "show_born", False) else set()   # CPE-008 --show-born
    plan = plan_display(events, points, ptr_map, born=born)
    uninit = find_uninit_locals(tree, src, aliases)
    kinds = {}
    for m in points.values(): kinds.update(m["kinds"])
    comps, claimed, cnotes = [], set(), []
    if not getattr(args, "no_comps", False):
        comps, claimed, cnotes = comps_mod.select(src_text, events, plan, kinds, uninit, disabled=set(getattr(args, "disable", "").split(",")))
        if claimed: plan = plan_display(events, points, ptr_map, exclude=claimed, born=born)
    plan["notes"] = plan["notes"] + cnotes
    plan["components"] = [c.used_name for c in comps]
    plan["comp_info"] = [dict(kind=c.kind, name=c.name, vars=c.vars, hide=c.hide, used_name=c.used_name, form=getattr(c, "form", None)) for c in comps]
    plan["uninit"] = sorted(uninit)
    plan["garbage"] = {}
    for e in events:   # 沒初始值的區域純量：出生時若是非零殘值 → 畫面顯示「?」直到第一次被改
        for k in e["born"]:
            v = e["values"][k]
            if k in uninit and plan["info"].get(k, {}).get("kind") == "scalar" and isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0:
                plan["garbage"][k] = v
    info = plan["info"]
    # CPE-008：split2 且有 struct 欄位列（p.s／p.i／p.j，常 10 格）時，內容寬限 940 → fit 倍率 ≥1.08，▲指標／chip 副標 24px 上畫面仍 ≥26px；其他情形不變
    cw_ = SPLIT2_STRUCT_W if getattr(args, "layout", "split") == "split2" and any("." in a for a in plan["arrays"]) else None
    if cw_:   # 格子變窄：記下各一維陣列全片最寬的格文字（em），layoutlib 據此降字級，避免 4 位數溢出格子
        for a in plan["arrays"]:
            if info[a]["kind"] == "arr2": continue
            info[a]["maxgw"] = max([stagefit.glyph_width(cell_text(x), 1) for e in events if a in e["values"] for x in list(e["values"][a])[:info[a]["n"]]] or [0])
    els, geo = build_geometry(comps, plan, events[0]["state"] if events else {}, make_cell_fn(info), events, stage_w=narrow_w(args), content_w=cw_, content_h=SPLIT2_STRUCT_H if cw_ else None)   # layoutlib（CPE-003：與離線重放測試共用）
    ytop, lay = geo["ytop"], geo["lay"]
    comp_vars = set(v for c in comps for v in c.vars)
    shown = set(plan["chips"]) | set(plan["arrays"]) | plan["marker_vars"] | comp_vars
    emitted = {}
    def comp_patch(ei):
        d = {}
        for c in comps:
            fr = c.frames.get(ei)
            if fr is None: continue
            for eid, p in fr.items():
                if emitted.get(eid) != p and not (eid not in emitted and p.get("opacity", 1) == 0):
                    d[eid] = p; emitted[eid] = p
        return d
    def comp_expect(ei):
        ex = {}
        for c in comps: ex.update(c.expects.get(ei, {}))
        return ex
    units, main_line = top_units(tree, src, points, events)
    # 事件 → unit
    def unit_of(line):
        for ui, u in enumerate(units):
            if u["l0"] <= line <= u["l1"]: return ui
        return None
    groups = []  # (unit index, [event idx])
    cur_u = None
    for ei, e in enumerate(events):
        if ei == 0: continue   # 第 0 個事件的「出生」已在初始畫面（s0）呈現
        if not ((set(e["changes"]) | set(e["born"])) & shown): continue
        u = unit_of(e["line0"])
        if u is None: u = cur_u if cur_u is not None else 0
        if groups and groups[-1][0] == u: groups[-1][1].append(ei)
        else: groups.append((u, [ei]))
        cur_u = u
    scenes, checks = [], []
    cue_meta, scene_events = {}, {}   # 給旁白層：cue → 對應的事件序號
    def op(at=None, dt=None, dur=None, **set_):
        o = {"set": set_}
        if at is not None: o["at"] = at
        if dt is not None: o["dt"] = dt
        if dur is not None: o["dur"] = dur
        return o
    cellstate = {}  # elid -> (text, color, opacity)
    def el_patch(eid, text=None, color="neutral", visible=True, **extra):
        p = dict(els[eid]); p["color"] = color; p["opacity"] = 1 if visible else 0
        if text is not None:
            if eid.startswith("v_"): p["text"] = text; p["sub"] = eid[2:]
            else: p["text"] = text
        p.update(extra)
        return p
    # 預設狀態：第一個事件的狀態（變數首次出現）
    init_state = events[0]["state"] if events else {}
    # 用各變數「首次出現」的值當初始
    first_vals = {}
    for e in events:
        for k, v in e["values"].items(): first_vals.setdefault(k, v)
    base_state = dict(events[0]["state"]) if events else {}   # 只顯示第 0 個事件時已存在的變數；其餘等「出生」才出現（不外露殘值）
    base_board = board_state(plan, base_state)
    # 由「首次出現」算不出初值的變數（事件 0 就被改）：用 changes 還原
    e0 = events[0]
    for k, (old, new) in e0["changes"].items(): pass

    def setup_ops():
        d = dict(comp_patch(0))
        for a in plan["arrays"]:
            if a in base_state: d[f"n_{a}"] = dict(els[f"n_{a}"], text=a, color="neutral", opacity=1, plain=True)
        for eid, (t, vis) in base_board.items():
            d[eid] = el_patch(eid, t, "neutral", vis)
            cellstate[eid] = (t, "neutral", 1 if vis else 0)
        return d
    # 場景 0：準備
    first_line = units[0]["l0"] if units else main_line
    scenes.append(dict(id="s0", label="準備", layout=getattr(args, "layout", "split"), focus="both", cues=[
        dict(id="s0c1", text="先看標頭、全域變數和 main 開頭。", cap="初始狀態", lines=list(range(1, max(2, first_line))),
             ops=[dict(at=0.3, dur=0.5, set=setup_ops())], pauseAfter=0.6)]))
    checks.append(("s0c1", {**{eid: t for eid, (t, vis) in base_board.items() if vis}, **comp_expect(0)}))
    cue_meta["s0c1"] = dict(kind="setup", events=[0]); scene_events["s0"] = [0]

    def unit_label(u):
        return KIND.get(u["type"], "這段")
    ptr_els = {}
    for eid, (a, p, n_, props) in marker_els(plan).items():
        ptr_els[eid] = (a, p, n_)
        els[eid] = props
    first_change = {}
    for ei_, e_ in enumerate(events):
        for k_ in e_["changes"]: first_change.setdefault(k_, ei_)
    def ptr_ops(state, vals=None, ei_=None):
        d = {}
        for eid, (a, p, n_) in ptr_els.items():
            ai = info[a]; v = state.get(p)
            vis = isinstance(v, int) and not isinstance(v, bool) and 0 <= v < ai["n"]
            if vals is not None and p not in vals: vis = False          # 變數已離開作用域：指標收起
            if p in plan["garbage"] and ei_ is not None and ei_ < first_change.get(p, 1 << 30): vis = False   # 未初始化殘值（第一次被改之前）：不指
            x = ai["cx0"] + (v if vis else 0) * (ai["cw"] + ai["gap"])
            d[eid] = dict(els[eid], x=x, text=f"▲{p}", color="yellow", opacity=1 if vis else 0)
        return d
    ptr_patch_cache = {}

    def apply_event(prev_state, new_state, settled, cnt_prefix, cue_id, cum, ei=None):
        """回傳 set 與 checkpoint 預期文字；prev→new 的差異格變黃，先前 settled 變綠"""
        d = {}
        pb, nb = board_state(plan, prev_state), board_state(plan, new_state)
        now = set()
        for eid, (t, vis) in nb.items():
            if pb.get(eid) != (t, vis): now.add(eid)
        for eid in list(settled):
            if eid not in now:
                t, vis = nb.get(eid, ("", False))
                if cellstate.get(eid, (None, None, None))[1] != "green":
                    d[eid] = el_patch(eid, t, "green", vis); cellstate[eid] = (t, "green", 1 if vis else 0)
        for eid in now:
            t, vis = nb[eid]
            d[eid] = el_patch(eid, t, "yellow", vis); cellstate[eid] = (t, "yellow", 1 if vis else 0)
            settled.add(eid)
        for a in plan["arrays"]:   # 新出生的陣列：補上名稱標籤
            if a in new_state and a not in prev_state:
                d[f"n_{a}"] = dict(els[f"n_{a}"], text=a, color="neutral", opacity=1, plain=True)
        d.update(ptr_ops(new_state, events[ei]["values"] if ei is not None else None, ei))
        exp = {eid: t for eid, (t, vis) in nb.items() if vis}
        if ei is not None:
            d.update(comp_patch(ei)); exp.update(comp_expect(ei))
        return d, exp
    # 場景
    nsc = 0
    last_state = dict(base_state)
    prev_state_global = dict(base_state)
    for gi, (u, eidx) in enumerate(groups):
        nsc += 1
        sid = f"s{nsc}"
        un = units[u] if u < len(units) else dict(type="", l0=events[eidx[0]]["line0"], l1=events[eidx[-1]]["line1"])
        rng = list(range(un["l0"], un["l1"] + 1))
        label = f"第 {un['l0']}–{un['l1']} 行" if un["l1"] > un["l0"] else f"第 {un['l0']} 行"
        cues = []
        intro = f"第 {un['l0']} 到 {un['l1']} 行，{unit_label(un)}。" if un["l1"] > un["l0"] else f"看第 {un['l0']} 行。"
        # 重設顏色
        reset = {}
        for eid, (t, c, o) in list(cellstate.items()):
            if c != "neutral" and eid in els:
                reset[eid] = el_patch(eid, t, "neutral", bool(o)); cellstate[eid] = (t, "neutral", o)
        cues.append(dict(id=f"{sid}c1", text=intro, cap=label, lines=rng, ops=[dict(at=0.4, dur=0.3, set=reset)] if reset else [], pauseAfter=0.3))
        checks.append((f"{sid}c1", None))
        cue_meta[f"{sid}c1"] = dict(kind="intro", events=[]); scene_events[sid] = list(eidx)
        settled = set()
        n_indiv = (30 if any(c.kind == "tree" for c in comps) else 12) if any(c.kind != "slots" for c in comps) else 4   # 圖／樹／佇列／map 元件的過程重要，多逐步呈現幾個事件
        indiv = eidx[:n_indiv]
        rest = eidx[n_indiv:]
        prev_state = dict(prev_state_global)
        ci = 1
        for ei in indiv:
            e = events[ei]
            ci += 1
            parts = []
            for k in e["born"]:
                if k in shown and kinds[k] in ("scalar",): parts.append(f"{k} 是 {cell_text(e['values'][k])}")
                elif k in shown: parts.append(f"{k} 出現")
            for k in e["changes"]:
                if k in shown:
                    old, new = e["changes"][k]
                    parts.append(phrase(k, old, new, kinds[k]))
            text = "，".join(parts[:2]) + "。" if parts else "狀態更新。"
            d, exp = apply_event(prev_state, e["state"], settled, "", f"{sid}c{ci}", None, ei)
            cues.append(dict(id=f"{sid}c{ci}", text=text, cap=f"第 {e['line0']} 行", lines=list(range(e["line0"], e["line1"] + 1)),
                             ops=[dict(at=0.35, dur=0.4, set=d)], pauseAfter=0.5))
            checks.append((f"{sid}c{ci}", exp))
            cue_meta[f"{sid}c{ci}"] = dict(kind="event", events=[ei])
            prev_state = e["state"]
        if rest:
            ci += 1
            pick_n = 36
            sel = rest if len(rest) <= pick_n else [rest[int(i * (len(rest) - 1) / (pick_n - 1))] for i in range(pick_n)]
            ops = []
            exp = None
            for k, ei in enumerate(sel):
                e = events[ei]
                d, exp = apply_event(prev_state, e["state"], settled, "", None, None, ei)
                ops.append(dict(dt=0.25 + 0.2 * k, dur=0.15, set=d))
                prev_state = e["state"]
            lines_all = [events[i]["line0"] for i in rest]
            cues.append(dict(id=f"{sid}c{ci}", text="剩下的照做，快轉帶過。", cap=label, lines=list(range(min(lines_all), max(events[i]["line1"] for i in rest) + 1)),
                             ops=ops, pauseAfter=0.6))
            checks.append((f"{sid}c{ci}", exp))
            cue_meta[f"{sid}c{ci}"] = dict(kind="ff", events=list(rest))
        prev_state_global = prev_state
        scenes.append(dict(id=sid, label=label, layout=getattr(args, "layout", "split"), focus="both", cues=cues))
    # 輸出
    out_lines = [l.rstrip() for l in eq.original.stdout.rstrip("\n").split("\n")[:6]]
    cout_lines = [i + 1 for i, l in enumerate(src_text.split("\n")) if re.search(r"\bcout\b|printf|puts", l)]
    oops = {}
    for k, l in enumerate(out_lines):
        oops[f"o{k}"] = dict(x=140, y=330 + 0 + k * 0, w=920, h=50, text=l if len(l) <= 40 else l[:40] + "…", color="green", plain=False, fs=30, opacity=1)
    # 輸出放在舞台右下不被 cells 遮：改放到 y=  (依 cells 底部)
    ybase = max([v["y"] + v["h"] for v in els.values()] + [200]) + 20
    ybase = min(ybase, 400 - 46 * max(0, len(out_lines) - 1))
    for k in range(len(out_lines)):
        oops[f"o{k}"]["y"] = ybase + 46 * k; oops[f"o{k}"]["h"] = 40
        oops[f"o{k}"]["x"] = 10 + 0; oops[f"o{k}"]["w"] = 1100
        els[f"o{k}"] = {}
    scenes.append(dict(id=f"s{nsc + 1}", label="輸出", layout=getattr(args, "layout", "split"), focus="both", cues=[
        dict(id=f"s{nsc + 1}c1", text="最後是輸出結果。", cap="實際輸出", lines=cout_lines[:3], ops=[
            dict(at=0.15, dur=0.4, set={**{eid: dict(p, opacity=0) for eid, p in els.items() if p and not eid.startswith("o")}, **{eid: dict(p, opacity=0) for eid, p in emitted.items()}}),  # 先淡出資料區，避免輸出列與陣列重疊
            dict(at=0.5, dur=0.4, set=oops)], pauseAfter=1.0)]))
    checks.append((f"s{nsc + 1}c1", None))
    cue_meta[f"s{nsc + 1}c1"] = dict(kind="out", events=[]); scene_events[f"s{nsc + 1}"] = []
    plan["cue_meta"], plan["scene_events"] = cue_meta, scene_events
    story = dict(title=args.title, revealAll=True, code="code.cpp", scenes=scenes)
    return story, checks, plan, events


# ───────────────────────── 5. 對拍驗證 ─────────────────────────
def verify(story, checks, eq, events, plan):
    """重放 story ops → 每個 cue 結束後的畫面文字必須 = 對應 trace 狀態；並核對 stdout"""
    cur = {}
    ok = bad = 0
    fails = []
    cue_map = {c["id"]: c for s in story["scenes"] for c in s["cues"]}
    for cid, exp in checks:
        cue = cue_map[cid]
        ops = sorted(enumerate(cue.get("ops", [])), key=lambda t: ((t[1].get("at", 0) if "at" in t[1] else 0) + t[1].get("dt", 0) / 100, t[0]))
        for _, o in ops:
            for eid, patch in o["set"].items():
                cur[eid] = {**cur.get(eid, {}), **patch}
        if exp is None: continue
        for eid, t in exp.items():
            if check_key(cur, eid, t): ok += 1
            else:
                bad += 1; fails.append((cid, eid, t, got_of(cur, eid)))
    # 最終輸出
    want = [l.rstrip() for l in eq.original.stdout.rstrip("\n").split("\n")][:6]
    shown = [cur[f"o{k}"]["text"] for k in range(len(want)) if f"o{k}" in cur]
    for k, w_ in enumerate(want):
        w2 = w_ if len(w_) <= 40 else w_[:40] + "…"
        if k < len(shown) and shown[k] == w2: ok += 1
        else: bad += 1; fails.append(("out", f"o{k}", w2, shown[k] if k < len(shown) else None))
    return dict(checked=ok + bad, ok=ok, bad=bad, fails=fails[:20], equivalent=eq.equivalent, matches_expected=eq.matches_expected)


# ───────────────────────── main ─────────────────────────
async def amain():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder"); ap.add_argument("--cpp", required=True); ap.add_argument("--stdin", required=True)
    ap.add_argument("--expect"); ap.add_argument("--title", default=""); ap.add_argument("--no-comps", action="store_true", dest="no_comps"); ap.add_argument("--disable", default="")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "public")); ap.add_argument("--layout", default="split", choices=["split", "split2", "concept", "wide"], help="split＝左程式右動畫（預設）；split2＝D-020 E2：左程式面板 820×852（字級 22、單行 ≤58 字元不截、約 22 行）＋右窗 1020×800（A1 判全額）；fullcode 只用於 narrate 的片尾場景，不是整片版面；concept＝1.45 倍舞台＋小程式列（舞台限高 460）；wide＝1.2 倍舞台（可到 580 高）＋小程式列（手工版風格）")
    ap.add_argument("--stage-fit", default="auto", choices=["auto", "off"], dest="stage_fit", help="CPE-003：auto（預設）＝story 加 stageFit=auto（動畫區依內容自適應放大）並把最小可讀尺寸警示（type=stage_fit）寫入 warnings.json；off＝關閉，行為與以前相同")
    ap.add_argument("--stage-w", type=int, default=None, dest="stage_w", help="D-020 E3：虛擬舞台寬（<1200 時，有頂部槽位列的 story 啟用窄版：槽卡寬≤120、說明欄 110、陣列不左右成對）；預設：--layout split2→1000，其餘 1200（逐值不變）")
    ap.add_argument("--show-born", action="store_true", dest="show_born", help="CPE-008：main 迴圈內宣告、設過一次就不再改的純量（如找到解那條路徑上的 d／c／t／k）也顯示（chip 或 ▲指標）；預設關閉＝與以前逐值相同")
    ap.add_argument("--layout-rev", type=int, default=2, choices=[1, 2], dest="layout_rev", help="D-020 E4：2（預設，新產生的 story）＝story 標 layoutRev:2，字幕下移到 top=1003，與 wide 程式列零重疊；1＝不標（與以前逐值相同）")
    args = ap.parse_args()
    src_text = Path(args.cpp).read_text()
    stdin = Path(args.stdin).read_text()
    expect = Path(args.expect).read_text() if args.expect else None
    eq, inst, points, tree, src, aliases = await run_program(src_text, stdin, expect)
    if not eq.equivalent:
        print("⚠ 插樁版輸出與原版不同，中止", eq.original.stdout[:200], eq.traced.stdout[:200]); sys.exit(2)
    if expect is not None and not eq.matches_expected:
        print("⚠ 原版輸出與預期不符", repr(eq.original.stdout[:200])); sys.exit(2)
    events = build_events(eq, points)
    if not events: print("沒有任何追蹤事件"); sys.exit(3)
    story, checks, plan, events = generate(args.folder, args, eq, points, tree, src, aliases, events, src_text)
    res = verify(story, checks, eq, events, plan)
    stagefit.apply_stage_fit(story, args.stage_fit)
    if args.layout_rev >= 2: story["layoutRev"] = args.layout_rev
    d = Path(args.out) / args.folder
    d.mkdir(parents=True, exist_ok=True)
    (d / "story.json").write_text(json.dumps(story, ensure_ascii=False, indent=1))
    (d / "code.cpp").write_text(src_text)
    (d / "verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    (d / "narr_meta.json").write_text(json.dumps(dict(
        cues=plan["cue_meta"], scene_events=plan["scene_events"], checks=[[c, e] for c, e in checks],
        shown=plan["arrays"] + plan["chips"] + sorted(set(v for c in plan["comp_info"] for v in c["vars"])), comps=plan["comp_info"], arrays=plan["arrays"], chips=plan["chips"], markers=sorted(plan["marker_vars"]),
        ptrs=plan["ptrs"], notes=plan["notes"], garbage=plan["garbage"],
        disp={k: (v["n"] if "n" in v else [v.get("r"), v.get("c")]) for k, v in plan["info"].items() if v["kind"] != "scalar"},
        bases={k: v["base"] for k, v in plan["info"].items() if v["kind"] in ("arr1", "arr2") and v.get("touched") is not None and v.get("base") is not None}, stdin=stdin, stdout=eq.original.stdout, cpp=str(Path(args.cpp).resolve())), ensure_ascii=False))
    (d / "trace_events.json").write_text(json.dumps([{k: v for k, v in e.items() if k != "state"} for e in events], ensure_ascii=False))
    ncue = sum(len(s["cues"]) for s in story["scenes"])
    print(f"{args.folder}: events={len(events)} scenes={len(story['scenes'])} cues={ncue} shown={plan['arrays'] + plan['chips']} comps={[c['kind'] + ':' + ','.join(c['vars']) for c in plan['comp_info']]} markers={sorted(plan['marker_vars'])}")
    print(f"  對拍 {res['ok']}/{res['checked']} 通過  equivalent={res['equivalent']} matches_expected={res['matches_expected']}")
    for n in plan["notes"]: print("  限制:", n)
    for f in res["fails"][:8]: print("  FAIL", f)
    ws, algos = detect_mod.detect(src_text, events, dict(plan, kinds={k: v["kind"] for k, v in plan["info"].items()}), points, used=plan.get("components", ()))
    ws = ws + stagefit.geo_warnings(plan)    # CPE-003 D-012：排版時偵測到的外框重疊（F3 超限）
    (d / "warnings.json").write_text(json.dumps(dict(summary=stagefit.summary_of(ws), algorithms=[a for a, _ in algos], components_used=sorted(plan.get("components", ())), warnings=ws), ensure_ascii=False, indent=1))
    nfit = stagefit.write_outputs_warnings(d, story, args.stage_fit)    # type=stage_fit 併入 warnings.json（可重跑；off 時移除既有 stage_fit）
    if args.stage_fit == "auto": print(f"  舞台自適應 stageFit=auto：最小可讀尺寸警示 {nfit} 項（type=stage_fit；明細 pixel_table.py {d}）")
    print("  缺元件偵測（warnings.json）：" + ("無缺元件警示" if not ws else f"{len(ws)} 項"))
    detect_mod.print_warnings(ws, algos)
if __name__ == "__main__":
    asyncio.run(amain())
