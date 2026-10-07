"""動畫元件：圖／槽位列（卡片移動）／佇列·堆疊·優先佇列／陣列樹／map·set。
每個元件在 prepare() 先對「所有事件」依序算好每個事件後的完整畫面 frames[ei]（eid→完整屬性）與獨立推導的預期 expects[ei]
（驗證用 key 格式見 verifylib）。autoanim 只負責把 frames 與「上次輸出」做差異後寫成 op。
元件只依 trace 狀態（events[ei]["state"] 累積狀態、events[ei]["values"] 當下可見變數）決定畫面，不依賴旁白。
"""
import math, re

SENT = 10 ** 8   # 視為「無限大／未到達」的門檻


def ctext(v):
    if isinstance(v, bool): return "1" if v else "0"
    if isinstance(v, str) and len(v) == 1 and ord(v) < 32: return str(ord(v))
    if isinstance(v, float): return f"{v:g}"
    return str(v)


def is_int(v): return isinstance(v, int) and not isinstance(v, bool)


def container_types(src_text):
    """變數名 → queue/stack/deque/priority_queue"""
    out = {}
    for m in re.finditer(r"\b(priority_queue|queue|deque|stack)\s*<[^;(){}]*?>\s*([A-Za-z_]\w*)", re.sub(r"//[^\n]*", "", src_text)):
        out[m.group(2)] = m.group(1)
    return out


def hand_view(state, spec):
    """手寫陣列佇列／堆疊 → 虛擬容器內容。spec: arr, a(head 或 top 變數), b(tail 變數或 None), s0/e0(起迄偏移)。
    queue: arr[head+s0 : tail+e0]；stack: arr[s0 : top+e0]"""
    arr = state.get(spec["arr"]); a = state.get(spec["a"])
    if not isinstance(arr, list) or not is_int(a): return None
    if spec["b"] is not None:
        b = state.get(spec["b"])
        if not is_int(b): return None
        lo, hi = a + spec["s0"], b + spec["e0"]
    else:
        lo, hi = spec["s0"], a + spec["e0"]
    if lo < 0 or hi < lo or hi > len(arr): return None
    return list(arr[lo:hi])


class Comp:
    zone = "row"
    kind = "comp"
    def __init__(self, name, vars_):
        self.name, self.vars = name, list(vars_)
        self.used_name = self.kind
        self.els = {}            # eid → 基礎屬性
        self.frames = {}         # ei → {eid: 完整屬性}
        self.expects = {}        # ei → {check-key: want}
        self.hide = []           # 被此元件取代、不再以陣列格顯示的變數
        self.note = ""
        self._last = {}

    # 取得此事件後的狀態
    def _frame(self, ei, desired):
        """desired: eid → 屬性覆蓋（None＝隱藏）。frames[ei] 保存「覆蓋」，finalize() 再與基礎屬性合併成完整 props。"""
        fr = {}
        for eid, ov in desired.items():
            if ov is None: continue
            fr[eid] = {**ov, "opacity": 1}
        for eid, last in self._last.items():
            if eid not in fr:
                fr[eid] = {**last, "opacity": 0}
        self._last = fr
        self.frames[ei] = fr

    def finalize(self):
        for ei, fr in self.frames.items():
            self.frames[ei] = {eid: {**self.els[eid], **ov} for eid, ov in fr.items()}


# ═════════════ 圖 ═════════════
class GraphComp(Comp):
    zone = "left"; kind = "graph"

    def __init__(self, var, form, N, directed, edges, dist_var, queue_vars, focus_vars, weighted, events, info):
        super().__init__(f"graph_{var}", [var])
        self.var, self.form, self.N, self.directed = var, form, N, directed
        self.edges, self.dist_var, self.queue_vars, self.focus_vars, self.weighted = edges, dist_var, queue_vars, focus_vars, weighted
        self.info = info

    # —— 從狀態抽邊 ——
    def adj_edges(self, state):
        g = state.get(self.var)
        out = {}
        if not isinstance(g, list): return out
        if self.form == "list":
            for u, row in enumerate(g[:self.N]):
                for v in (row or []):
                    if is_int(v) and 0 <= v < self.N and u != v or (is_int(v) and u == v and 0 <= v < self.N): out[(u, v)] = None
        else:
            for u, row in enumerate(g[:self.N]):
                for v, x in enumerate(row[:self.N]):
                    if x not in (0, False, None, "") and not (is_int(x) and abs(x) >= SENT) and u != v:
                        out[(u, v)] = x if (self.weighted and is_int(x)) else None
        return out

    def vis_edges(self, state):
        """畫面上應顯示的邊 id → 權重"""
        raw = self.adj_edges(state)
        res = {}
        for (u, v), w in raw.items():
            if self.directed: res[f"{u}_{v}"] = w
            else:
                a, b = min(u, v), max(u, v)
                res[f"{a}_{b}"] = w if w is not None else res.get(f"{a}_{b}")
        return res

    def node_status(self, state):
        """node → visited？（由 dist／vis 陣列）與其 sub 文字"""
        st = {}
        dv = self.dist_var
        arr = state.get(dv) if dv else None
        sent = self.sentinel
        for i in range(self.N):
            sub, visited = "", False
            if isinstance(arr, list) and i < len(arr):
                x = arr[i]
                sub = self.cell(dv, i, x)
                if is_int(x) and abs(x) >= 10 ** 6: sub = "∞"
                if sub != "?":
                    if getattr(self, "flag_var", None):
                        fa = state.get(self.flag_var)
                        visited = bool(fa[i]) if isinstance(fa, list) and i < len(fa) and fa[i] != "\x00" else False
                    elif self.flag_like: visited = bool(x) and x != "\x00"
                    elif sent is not None and self.sent_ready(state): visited = x != sent
                    else: visited = False
            st[i] = (sub, visited)
        return st

    def prepare(self, events, ctx, region):
        self.cell = ctx["cell"]
        N = self.N
        x0, y0, x1, y1 = region
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 + 6
        R = min((x1 - x0) / 2 - 36, (y1 - y0) / 2 - 36)
        d = 64 if N <= 8 else (50 if N <= 12 else (40 if N <= 16 else 34))
        self.d = d
        self.pos = {}
        # 版面：先由全程出現過的邊判斷（格狀／樹狀／環形）
        alle0 = set()
        for ev in events:
            alle0 |= set(self.vis_edges(ev["state"]))
        und = {tuple(map(int, e.split("_"))) for e in alle0}
        self.layout = self._pick_layout(N, und)
        if self.layout[0] == "grid":
            W = self.layout[1]; H = -(-N // W)
            gx = (x1 - x0 - d) / max(1, W - 1); gy = (y1 - y0 - d - 30) / max(1, H - 1)
            gx, gy = min(gx, 110), min(gy, 90)
            ox = x0 + (x1 - x0 - gx * (W - 1)) / 2; oy = y0 + 30 + d / 2 + (y1 - y0 - 30 - d - gy * (H - 1)) / 2
            for i in range(N): self.pos[i] = (ox + (i % W) * gx, oy + (i // W) * gy)
            self.crowded = self._box_gap(self.pos, d) < 0   # D-016（F3）：格狀也檢查（原本不檢查、不記錄）
        elif self.layout[0] == "tree":
            kids, depth = self.layout[1], self.layout[2]
            D = max(depth.values()); leaf = [0]
            xp = {}
            def place(u):
                ch = kids.get(u, [])
                if not ch: xp[u] = leaf[0]; leaf[0] += 1
                else:
                    for c in ch: place(c)
                    xp[u] = (xp[ch[0]] + xp[ch[-1]]) / 2
            place(0)
            nl = max(1, leaf[0] - 1)
            gx = min((x1 - x0 - d) / max(1, nl), 90); gy = min((y1 - y0 - d - 30) / max(1, D), 90)
            ox = x0 + (x1 - x0 - gx * nl) / 2
            for u in range(N): self.pos[u] = (ox + xp[u] * gx, y0 + 30 + d / 2 + depth[u] * gy)
            # D-016（F3）：樹狀版面外框重疊（路徑圖深度大、星形葉子多…）時，依序試環形、弧長等距橢圓，取外框間隙最大者；仍重疊 → crowded（layout_overlap 警示）
            if self._box_gap(self.pos, d) < 0:
                cands = [("tree", self.pos)]
                pc = {i: (cx + R * math.cos(-math.pi / 2 + 2 * math.pi * i / N), cy + R * math.sin(-math.pi / 2 + 2 * math.pi * i / N)) for i in range(N)}
                cands.append(("circle", pc))
                cands.append(("circle", self._ellipse_pos(N, cx, cy, max(R, (x1 - x0) / 2 - 36), R)))
                best = max(cands, key=lambda c: self._box_gap(c[1], d))
                if best[0] != "tree":
                    self.pos = best[1]; self.layout = ("circle",)
            self.crowded = self._box_gap(self.pos, d) < 0
        else:
            for i in range(N):
                ang = -math.pi / 2 + 2 * math.pi * i / N
                self.pos[i] = (cx + R * math.cos(ang), cy + R * math.sin(ang))
            # D-012（F3）：節點外框（正方形 d×d）互相重疊時（例如 20 節點：相鄰兩點的 |dx|、|dy| 都只有 29px < d=34），
            # 改排成「弧長等距」的橢圓（水平半徑用滿區域寬 (x1-x0)/2-36，垂直半徑維持 R）；仍擠不下才記錄 self.crowded（由 autoanim 寫入警示）
            self.crowded = False
            if self._box_gap(self.pos, d) < 0:
                Rx = max(R, (x1 - x0) / 2 - 36)
                pe = self._ellipse_pos(N, cx, cy, Rx, R)
                if self._box_gap(pe, d) > self._box_gap(self.pos, d): self.pos = pe
                self.crowded = self._box_gap(self.pos, d) < 0
        self.els[f"gl_{self.var}"] = dict(x=x0, y=y0 - 2, w=150, h=34, fs=26, plain=True, text=f"圖 {self.var}", color="neutral")
        for i in range(N):
            px, py = self.pos[i]
            self.els[f"gn_{i}"] = dict(x=px - d / 2, y=py - d / 2, w=d, h=d, fs=30 if d >= 60 else 24, sfs=17, shape="circle", color="neutral")
        # 所有出現過的邊
        alle = {}
        for ev in events:
            for eid in self.vis_edges(ev["state"]): alle[eid] = True
        self.edge_ids = list(alle)
        for eid in self.edge_ids:
            if self.directed: u, v = map(int, eid.split("_"))
            else: u, v = map(int, eid.split("_"))
            self.els[f"ge_{eid}"] = self._line(u, v)
            if self.weighted:
                (ax, ay), (bx, by) = self.pos[u], self.pos[v]
                self.els[f"gw_{eid}"] = dict(x=(ax + bx) / 2 - 20, y=(ay + by) / 2 - 14, w=40, h=28, fs=20, plain=True, text="", color="neutral")
        # 哨兵（dist 初始化值）：第一次「全部格相同且非 0」的值
        self.sentinel = None; self._sent_at = None
        if self.dist_var and not self.flag_like:
            for ei, ev in enumerate(events):
                a = ev["state"].get(self.dist_var)
                if isinstance(a, list) and a and len(set(map(str, a[:N]))) == 1 and a[0] not in (0, "?", None) and ev["state"] is not None:
                    self.sentinel = a[0]; self._sent_at = ei; break
        self._events = events
        for ei, ev in enumerate(events):
            self._render(ei, ev)

    @staticmethod
    def _box_gap(pos, d):
        """所有節點對的外框（d×d 正方形）最小間隙：max(|dx|,|dy|) - d；<0 即外框重疊"""
        pts = list(pos.values())
        return min([max(abs(a[0] - b[0]), abs(a[1] - b[1])) - d for i, a in enumerate(pts) for b in pts[i + 1:]] + [1e9])

    @staticmethod
    def _ellipse_pos(N, cx, cy, Rx, Ry):
        """橢圓上弧長等距的 N 個點（自頂端起順時針）"""
        M = 4000
        pts = [(Rx * math.sin(2 * math.pi * k / M), -Ry * math.cos(2 * math.pi * k / M)) for k in range(M + 1)]
        cum = [0.0]
        for a, b in zip(pts, pts[1:]): cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        out, k = {}, 0
        for i in range(N):
            t = cum[-1] * i / N
            while cum[k + 1] < t: k += 1
            out[i] = (cx + pts[k][0], cy + pts[k][1])
        return out

    @staticmethod
    def _pick_layout(N, und):
        """格狀（邊只連 i±1／i±W，N=W×H）、樹狀（無向、N-1 條邊、由 0 可達）、否則環形"""
        E = {(min(u, v), max(u, v)) for u, v in und if u != v}
        if N >= 6 and E:
            for W in range(2, N // 2 + 1):
                if N % W: continue
                ok = all((v - u == W) or (v - u == 1 and u % W != W - 1) for u, v in E)
                nv = sum(1 for u, v in E if v - u == W); nh = len(E) - nv
                if ok and nv >= W and nh >= N // W: return ("grid", W)
        if N >= 4 and len(E) == N - 1:
            adj = {i: [] for i in range(N)}
            for u, v in E: adj[u].append(v); adj[v].append(u)
            depth, kids, q = {0: 0}, {}, [0]
            for u in q:
                for v in sorted(adj[u]):
                    if v not in depth:
                        depth[v] = depth[u] + 1; kids.setdefault(u, []).append(v); q.append(v)
            if len(depth) == N: return ("tree", kids, depth)
        return ("circle",)

    def sent_ready(self, state):
        return self.sentinel is not None and state is not None and self._cur_ei >= self._sent_at

    def _line(self, u, v):
        (ax, ay), (bx, by) = self.pos[u], self.pos[v]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        r = self.d / 2 + (4 if self.directed else 1)
        off = 7 if self.directed else 0
        nx, ny = -uy * off, ux * off
        sx, sy = ax + ux * (self.d / 2 + 1) + nx, ay + uy * (self.d / 2 + 1) + ny
        ex, ey = bx - ux * r + nx, by - uy * r + ny
        return dict(x=sx, y=sy, w=ex - sx, h=ey - sy, fs=5, shape="line", arrow=self.directed, color="neutral", text="")

    def _render(self, ei, ev):
        self._cur_ei = ei
        state = ev["state"]; vals = ev["values"]
        if self.var not in state:
            self._frame(ei, {}); self.expects[ei] = {}; return
        st = self.node_status(state)
        focus = set()
        for p in self.focus_vars:
            v = vals.get(p)
            if p in getattr(self, "uninit", ()) and p in ev["born"]: continue
            if is_int(v) and 0 <= v < self.N: focus.add(v)
        inq = set()
        for qv in self.queue_vars:
            q = hand_view(state, qv) if isinstance(qv, dict) else state.get(qv)
            if isinstance(q, list):
                for x in q:
                    if is_int(x) and 0 <= x < self.N: inq.add(x)
        edges = self.vis_edges(state)
        des = {f"gl_{self.var}": {}}
        ex = {}
        for i in range(self.N):
            sub, visited = st[i]
            col = "yellow" if i in focus else ("green" if visited else "neutral")
            des[f"gn_{i}"] = dict(text=str(i), sub=sub if self.d >= 60 else "", color=col, dashed=(i in inq and i not in focus))
        for eid, w in edges.items():
            u, v = map(int, eid.split("_"))
            col = "yellow" if (u in focus and v in focus) else "neutral"
            des[f"ge_{eid}"] = dict(color=col)
            if self.weighted and w is not None: des[f"gw_{eid}"] = dict(text=str(w))
        self._frame(ei, des)
        # 獨立推導的預期（直接從 trace 的 g／dist 原始值重算）
        g = state.get(self.var)
        exp_edges = set()
        for u in range(self.N):
            if self.form == "list": nbrs = [v for v in (g[u] if u < len(g) else []) if is_int(v) and 0 <= v < self.N]
            else: nbrs = [v for v, x in enumerate(g[u][:self.N]) if x not in (0, False, None, "") and not (is_int(x) and abs(x) >= SENT) and v != u] if u < len(g) else []
            for v in nbrs:
                if u == v and self.form != "list": continue
                exp_edges.add(f"{u}_{v}" if self.directed else f"{min(u, v)}_{max(u, v)}")
        ex["set:ge_"] = sorted(exp_edges)
        if self.weighted and self.form == "matrix":      # 邊權也對拍（有向取 g[u][v]；無向只驗對稱的邊）
            for eid in exp_edges:
                a, b = map(int, eid.split("_"))
                wab = g[a][b] if a < len(g) and b < len(g[a]) else 0
                wba = g[b][a] if b < len(g) and a < len(g[b]) else 0
                if self.directed: want_w = wab
                elif wab and wba and wab == wba: want_w = wab
                elif bool(wab) != bool(wba): want_w = wab or wba
                else: continue
                if is_int(want_w): ex[f"gw_{eid}"] = str(want_w)
        for i in range(self.N):
            ex[f"gn_{i}"] = str(i)
            ex[f"gn_{i}%color"] = "yellow" if i in focus else ("green" if st[i][1] else "neutral")
            if self.d >= 60: ex[f"gn_{i}#"] = st[i][0]
        self.expects[ei] = ex


# ═════════════ 佇列／堆疊／優先佇列 ═════════════
class SeqComp(Comp):
    kind = "seq"
    STACK_CH = 44     # 堆疊每格高（virtual）；格距 = STACK_CH + 4

    def __init__(self, var, ctype, maxlen, events, hand=None):
        super().__init__(f"seq_{var}", [var])
        self.var, self.ctype, self.maxlen, self.hand = var, ctype, maxlen, hand
        self.used_name = "seq:" + ("queue" if ctype == "deque" else ctype)
        self.zone = "right" if ctype == "stack" else "row"
        self.cards = {}   # cid → value
        self.order = []   # 目前 cid 序（前→後 或 底→頂）
        self.nextid = 0

    def region_row(self, name_x, y, h, x0, wavail):
        self.row = dict(name_x=name_x, y=y, h=h, x0=x0, wavail=wavail)

    def _pos(self, idx, cw):
        if self.ctype == "stack":
            x, ytop, h = self.col["x"], self.col["y0"], self.col["ch"]
            return x, self.col["ybase"] - (idx + 1) * (h + 4) + 4
        r = self.row
        return r["x0"] + idx * (cw + 8), r["y"]

    def prepare(self, events, ctx, region):
        self.cell = ctx["cell"]
        K = max(1, min(self.maxlen, 12 if self.ctype != "stack" else 8))
        self.K = K
        if self.ctype == "stack":
            x0, y0, x1, y1 = region
            ch = self.STACK_CH      # CPE-003：堆疊格高 40→44（A1：成片 ≥64px，wide 倍率約 1.5 → 66px；concept 更大）
            self.col = dict(x=x0 + 8, y0=y0, ch=ch, ybase=y1 - 4)
            self.cw = x1 - x0 - 16
            fy = y1 - 4 - K * (ch + 4) - 4          # 外框頂端
            self.els[f"n_{self.var}"] = dict(x=x0, y=min(y0 - 6, fy - 36), w=x1 - x0, h=34, fs=26, plain=True, text=f"{self.var} 堆疊", color="neutral")   # 名稱不被塞滿的堆疊蓋住
            self.els[f"qf_{self.var}"] = dict(x=x0 + 4, y=fy, w=x1 - x0 - 8, h=K * (ch + 4) + 8, dashed=True, color="gray", fs=24, text="", sfs=20, shape="rect")
        else:
            r = self.row
            self.cw = max(34, min(70, int((r["wavail"] - 8 * K) / K)))
            lab = {"queue": "前→後", "deque": "前→後", "priority_queue": "頂→底"}.get(self.ctype, "")
            self.els[f"n_{self.var}"] = dict(x=r["name_x"], y=r["y"], w=118, h=r["h"], fs=28, plain=True, text=self.var, sub=lab, sfs=16, color="neutral")
            self.els[f"qf_{self.var}"] = dict(x=r["x0"] - 4, y=r["y"] - 4, w=K * (self.cw + 8) + 4, h=r["h"] + 8, dashed=True, color="gray", fs=24, text="", shape="rect")
        self._events = events
        self.cardid = 0
        ids = set()
        for ei, ev in enumerate(events):
            self._render(ei, ev, ids)
        for cid in ids:
            self.els[cid] = dict(x=0, y=0, w=self.cw, h=(self.col["ch"] if self.ctype == "stack" else self.row["h"]), fs=28 if self.cw >= 50 else 22, color="neutral", shape="rect")

    def _new(self, val, ids):
        cid = f"qc_{self.var}_{self.nextid}"; self.nextid += 1
        ids.add(cid); self.cards[cid] = val; return cid

    def _track(self, new, ids):
        old = [self.cards[c] for c in self.order]
        gone = []
        if new == old: return gone
        t = self.ctype
        if t in ("queue", "deque") and old and new == old[1:]: gone.append(self.order.pop(0))
        elif t == "stack" and old and new == old[:-1]: gone.append(self.order.pop())
        elif new[:len(old)] == old and t != "priority_queue":
            for x in new[len(old):]: self.order.append(self._new(x, ids))
        elif t == "deque" and old and new[1:] == old: self.order.insert(0, self._new(new[0], ids))
        elif t == "deque" and old and new == old[:-1]: gone.append(self.order.pop())
        else:   # 一般情形（含 priority_queue）：依值貪婪對應
            pool = list(self.order); newo = []
            for x in new:
                hit = next((c for c in pool if self.cards[c] == x), None)
                if hit is not None: pool.remove(hit); newo.append(hit)
                else: newo.append(self._new(x, ids))
            gone += pool; self.order = newo
        return gone

    def _render(self, ei, ev, ids):
        state = ev["state"]
        if self.hand:
            hv = hand_view(state, self.hand)
            if hv is None:
                self._frame(ei, {}); self.expects[ei] = {}; return
            cur = hv
        else:
            if self.var not in state:
                self._frame(ei, {}); self.expects[ei] = {}; return
            cur = [x for x in state[self.var]]
        gone = self._track(cur, ids)
        des = {f"n_{self.var}": {}, f"qf_{self.var}": dict(text="空" if not cur else "", sfs=20)}
        # 出場的卡片：停在原位淡出（位置＝出場前位置）
        shown = self.order[:self.K]
        for idx, cid in enumerate(self.order):
            if idx >= self.K: continue
            x, y = self._pos(idx, self.cw)
            top = (idx == 0) if self.ctype != "stack" else (idx == len(self.order) - 1)
            des[cid] = dict(x=x, y=y, w=self.cw, text=ctext(self.cards[cid]), color="yellow" if top else "neutral")
        for cid in gone:
            if cid in self._last: des[cid] = None   # 由 _frame 補成 opacity 0（保留最後位置）
        self._frame(ei, des)
        # 獨立預期：畫面卡片文字序 = trace 的容器內容
        axis = "y" if self.ctype == "stack" else "x"
        want = [ctext(v) for v in cur[:self.K]]
        self.expects[ei] = {f"seq:qc_{self.var}_:{axis}": want, f"n_{self.var}": ("%s 堆疊" % self.var) if self.ctype == "stack" else self.var}
        if len(cur) > self.K: self.expects[ei] = {}   # 超過顯示上限：不驗（已在 notes 提示）


# ═════════════ 槽位列＋卡片移動 ═════════════
class SlotsComp(Comp):
    zone = "top"; kind = "slots"

    def __init__(self, res_var, comp_var, flag_var, n, letters, writes, events):
        super().__init__(f"slots_{res_var}", [res_var] + ([flag_var] if flag_var else []))
        self.res, self.compv, self.flag, self.n, self.letters = res_var, comp_var, flag_var, n, letters
        self.writes = writes
        self.hide = [res_var] + ([flag_var] if flag_var else [])

    # CPE-003 D-007：槽位卡／槽放大到 68（成片 wide ×~1.4 時 ≥90px），說明文字移到左側欄（不再多占一列），整體高度 158→168
    HP, HS, HL, CAPW = 68, 68, 24, 150
    # D-020 E3 退路（split2 窄版，layoutlib.build_geometry 設 self.narrow）：說明欄 150→110、卡寬上限 150→120；高度 HP/HS 維持 68（完整版 90px 不做）
    CAPW_NARROW, WMAX, WMAX_NARROW = 110, 150, 120
    narrow = False
    height = HP + 6 + HS + 2 + HL   # 此元件在舞台頂部需要的高度（autoanim 依此預留，下方陣列往下排）

    def label(self, p): return chr(65 + p) if self.letters else str(p)

    def pos_label(self, i):
        """槽位標籤：人員（字母）題用 最外／次外／中間（左右對稱，依離邊緣的距離）；其餘用「槽 i」"""
        if not self.letters: return f"槽 {i}"
        d = min(i, self.n - 1 - i)
        if self.n % 2 and d == self.n // 2: return "中間"
        return {0: "最外", 1: "次外"}.get(d, f"第{d + 1}外")

    def prepare(self, events, ctx, region):
        self.cell = ctx["cell"]
        x0, y0, x1, y1 = region
        n = self.n
        capw = self.CAPW_NARROW if self.narrow else self.CAPW
        xa = x0 + capw + 6                      # 左側說明欄之後才是卡片區
        w = int(min(self.WMAX_NARROW if self.narrow else self.WMAX, (x1 - xa - 14 * (n - 1)) / n)); self.w = w
        gap = (x1 - xa - 8 - n * w) / max(1, n - 1) if n > 1 else 0
        gap = max(14, min(60, gap))
        tot = n * w + (n - 1) * gap
        xs = xa + max(4, (x1 - xa - tot) / 2)
        self.px = lambda i: int(round(xs + i * (w + gap)))
        hp, hs, hl = self.HP, self.HS, self.HL
        self.pool_y = y0
        self.slot_y = self.pool_y + hp + 6
        self.hp, self.hs = hp, hs
        self.els[f"pcap_{self.res}"] = dict(x=x0 + 4, y=self.pool_y, w=capw, h=hp, fs=26, plain=True, text="人員" if self.letters else "項目", color="neutral")
        self.els[f"sn_{self.res}"] = dict(x=x0 + 4, y=self.slot_y, w=capw, h=hs, fs=22, plain=True, text=f"槽位 0…{n - 1}", color="neutral")
        for i in range(n):
            self.els[f"sl_{i}"] = dict(x=self.px(i), y=self.slot_y, w=w, h=hs, fs=32, dashed=True, color="gray", text="", shape="rect")
            self.els[f"sb_{i}"] = dict(x=self.px(i), y=self.slot_y + hs + 2, w=w, h=hl, fs=20, plain=True, text="", color="neutral")
        for p in range(n):
            self.els[f"pc_{p}"] = dict(x=self.px(p), y=self.pool_y, w=w, h=hp, fs=30, sfs=16, color="neutral", shape="rect")
        filled = {}      # slot → person
        self._prev_filled = {}
        for ei, ev in enumerate(events):
            self._render(ei, ev, filled)

    def _eval_idx(self, expr, ev):
        if not re.fullmatch(r"[\w\s\+\-\*/\(\)%]+", expr): return None
        env = {}
        env.update({k: v for k, v in ev["state"].items() if is_int(v)})
        env.update({k: v for k, v in ev["values"].items() if is_int(v)})
        try:
            v = eval(expr.replace("/", "//"), {"__builtins__": {}}, env)
            return v if is_int(v) else None
        except Exception: return None

    def _render(self, ei, ev, filled):
        state = ev["state"]; n = self.n
        R = state.get(self.res)
        if R is None and not (self.compv and isinstance(state.get(self.compv), list)):
            self._frame(ei, {}); self.expects[ei] = {}; return
        if R is None: R = []      # 結果陣列還沒出生：先顯示人員卡（含計數）與空槽位，與手工 v2 一致
        new_slots = set()
        for (l, expr) in self.writes:
            if ev["line0"] <= l <= ev["line1"]:
                i = self._eval_idx(expr, ev)
                if i is not None and 0 <= i < n: new_slots.add(i)
        for k in ev["changes"].get(self.res, [None, None])[1:2] or []: pass
        chg = ev["changes"].get(self.res)
        if chg:
            old, new = chg
            for i in range(min(n, len(new))):
                if (old[i] if i < len(old) else None) != new[i]: new_slots.add(i)
        for i in new_slots:
            v = R[i] if i < len(R) else None
            if is_int(v) and 0 <= v < n:
                for s_, p_ in list(filled.items()):
                    if p_ == v and s_ != i: del filled[s_]   # 同一人只能在一格
                filled[i] = v
        placed = {p: s for s, p in filled.items()}
        cnt = state.get(self.compv) if self.compv else None
        flag = state.get(self.flag) if self.flag else None
        des = {f"sn_{self.res}": {}, f"pcap_{self.res}": {}}
        ex = {}
        for i in range(n):
            des[f"sl_{i}"] = dict(color="yellow") if i in new_slots else ({"color": "green"} if i in filled else {})
            des[f"sb_{i}"] = dict(text=self.pos_label(i))
        for p in range(n):
            sub = ""
            if isinstance(cnt, list) and p < len(cnt):
                sub = self.cell(self.compv, p, cnt[p])
                if self.letters and sub not in ("?", ""): sub = f"{sub}個"
            if p in placed:
                s = placed[p]
                col = "yellow" if s in new_slots else "green"
                des[f"pc_{p}"] = dict(x=self.px(s), y=self.slot_y, text=self.label(p), sub=sub, color=col)
                ex[f"pc_{p}@x"] = self.px(s); ex[f"pc_{p}@y"] = self.slot_y
            else:
                picked = isinstance(flag, list) and p < len(flag) and flag[p] not in (0, False, "\x00", "")
                des[f"pc_{p}"] = dict(x=self.px(p), y=self.pool_y, text=self.label(p), sub=sub, color="yellow" if picked else "neutral")
                ex[f"pc_{p}@x"] = self.px(p); ex[f"pc_{p}@y"] = self.pool_y
            ex[f"pc_{p}"] = self.label(p)
            ex[f"pc_{p}#"] = sub
        self._frame(ei, des)
        self.expects[ei] = ex


# ═════════════ 陣列表示的樹 ═════════════
class TreeComp(Comp):
    zone = "left"; kind = "tree"

    def __init__(self, L, Rr, key, root_var, null, focus_vars, events, info):
        super().__init__(f"tree_{L}_{Rr}", [x for x in (L, Rr, key) if x])
        self.L, self.R, self.key, self.root_var, self.null, self.focus_vars = L, Rr, key, root_var, null, focus_vars
        self.hide = [x for x in (L, Rr, key) if x]

    def children(self, state):
        L, R = state.get(self.L), state.get(self.R)
        out = []
        if not isinstance(L, list) or not isinstance(R, list): return out
        for u in range(min(len(L), len(R))):
            for side, arr in (("l", L), ("r", R)):
                c = arr[u]
                if is_int(c) and c != self.null and 0 <= c < len(L): out.append((u, c, side))
        return out

    def exists(self, state, idx):
        K = state.get(self.key) if self.key else None
        if isinstance(K, list) and idx < len(K):
            t = self.cell(self.key, idx, K[idx])
            if t != "?" and (K[idx] != 0 or idx in self._ref(state)): return True
        return idx in self._ref(state)

    def _ref(self, state):
        s = set()
        rv = state.get(self.root_var) if self.root_var else None
        if is_int(rv) and rv != self.null: s.add(rv)
        for u, c, _ in self.children(state): s.add(u); s.add(c)
        return s

    def prepare(self, events, ctx, region):
        self.cell = ctx["cell"]
        x0, y0, x1, y1 = region
        # 以全程聯集的邊求版面（插入型的樹只增不減）
        par = {}
        last = events[-1]["state"]
        edges = {}
        for ev in events:
            for u, c, side in self.children(ev["state"]): edges[(u, c)] = side
        kids = {}
        for (u, c), side in edges.items(): kids.setdefault(u, {})[side] = c
        for u, d in kids.items():
            for side, c in d.items(): par[c] = u
        nodes = set(par) | set(kids)
        rv = last.get(self.root_var) if self.root_var else None
        roots = [r for r in nodes if r not in par]
        if is_int(rv) and rv in nodes: roots = [rv] + [r for r in roots if r != rv]
        order = []     # 中序
        depth = {}
        seen = set()
        def walk(u, d):
            if u in seen: return
            seen.add(u); depth[u] = d
            if "l" in kids.get(u, {}): walk(kids[u]["l"], d + 1)
            order.append(u)
            if "r" in kids.get(u, {}): walk(kids[u]["r"], d + 1)
        for r in roots: walk(r, 0)
        # 還沒進樹（只有 key）的節點：排在最後一列
        K = last.get(self.key) if self.key else None
        extra = []
        if isinstance(K, list):
            for i in range(len(K)):
                if i not in seen and self.cell(self.key, i, K[i]) != "?" and (K[i] != 0): extra.append(i)
        allord = order + extra
        n = max(1, len(allord))
        maxd = max(list(depth.values()) + [0]) + (1 if extra else 0)
        # 依節點數與深度挑最大的節點直徑，使任兩節點外框不重疊（max(|dx|,|dy|) ≥ d+2）
        wide_region = (x1 - x0) >= 800   # CPE-003：整個動畫區寬都給樹（autoanim.comp_region）時，節點可以更大（A1 節點 ≥64px；退化樹 15 節點仍能 52）
        for d_ in (52, 42, 36, 32, 28, 26):
            if not wide_region:
                if d_ == 52 and n > 9: continue
                if d_ == 42 and n > 12: continue
            self.d = d_
            colw = (x1 - x0 - self.d) / max(1, n - 1) if n > 1 else 0
            colw = min(colw, 78)
            total = colw * (n - 1)
            xs = x0 + (x1 - x0 - self.d - total) / 2
            rowh = min(86, (y1 - y0 - self.d - 10) / max(1, maxd))
            self.pos = {}
            for k, u in enumerate(allord):
                dd = depth.get(u, maxd)
                self.pos[u] = (xs + k * colw + self.d / 2, y0 + 24 + self.d / 2 + dd * rowh)
            pts = list(self.pos.values())
            if all(max(abs(a[0] - b[0]), abs(a[1] - b[1])) >= self.d + 2 for i, a in enumerate(pts) for b in pts[i + 1:]): break
        self.els[f"tl_{self.name}"] = dict(x=x0, y=y0 - 2, w=60, h=26, fs=26, plain=True, text="樹", color="neutral")   # CPE-003：標籤縮小，不再壓到根節點（strict 重疊 0）
        for u, (px, py) in self.pos.items():
            self.els[f"tn_{u}"] = dict(x=px - self.d / 2, y=py - self.d / 2, w=self.d, h=self.d, fs=26 if self.d >= 50 else (22 if self.d >= 36 else 18), sfs=15, shape="circle", color="neutral")
        self.edge_list = []
        for (u, c), side in edges.items():
            if u in self.pos and c in self.pos:
                self.edge_list.append((u, c, side))
                self.els[f"te_{u}_{c}"] = self._line(u, c)
        self.nodes_seen = set()
        for ei, ev in enumerate(events):
            self._render(ei, ev)

    def _line(self, u, c):
        (ax, ay), (bx, by) = self.pos[u], self.pos[c]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        r = self.d / 2 + 1
        return dict(x=ax + ux * r, y=ay + uy * r, w=dx - 2 * ux * r, h=dy - 2 * uy * r, fs=5, shape="line", color="neutral", text="")

    def _render(self, ei, ev):
        state, vals = ev["state"], ev["values"]
        if self.L not in state:
            self._frame(ei, {}); self.expects[ei] = {}; return
        focus = set()
        for p in self.focus_vars:
            v = vals.get(p)
            if is_int(v) and v in self.pos: focus.add(v)
        ch = self.children(state)
        K = state.get(self.key) if self.key else None
        des = {f"tl_{self.name}": {}}
        ex = {}
        newn = set()
        for u in self.pos:
            if self.exists(state, u):
                if u not in self.nodes_seen: newn.add(u)
                self.nodes_seen.add(u)
        for u in self.pos:
            if u not in self.nodes_seen: continue
            txt = self.cell(self.key, u, K[u]) if isinstance(K, list) and u < len(K) else str(u)
            col = "yellow" if u in focus else ("green" if u in newn else "neutral")
            des[f"tn_{u}"] = dict(text=txt, sub=str(u) if self.d >= 50 and self.key else "", color=col)
            ex[f"tn_{u}"] = txt
        vis = []
        for (u, c, side) in self.edge_list:
            if any((u, c, side) == t for t in ch):
                des[f"te_{u}_{c}"] = dict(color="neutral"); vis.append(f"{u}_{c}")
        # 獨立預期：邊集合 = 目前 L／R 陣列中的父子
        want = sorted({f"{u}_{c}" for (u, c, _) in ch if u in self.pos and c in self.pos})
        ex["set:te_"] = want
        self._frame(ei, des)
        self.expects[ei] = ex


_MISSING = object()


# ═════════════ map／set（依鍵排序的鍵值卡片列） ═════════════
class KeyedComp(Comp):
    kind = "keyed"

    def __init__(self, var, ctype, maxlen):
        super().__init__(f"keyed_{var}", [var])
        self.var, self.ctype, self.maxlen = var, ctype, maxlen
        self.used_name = "keyed:" + ctype

    def region_row(self, name_x, y, h, x0, wavail):
        self.row = dict(name_x=name_x, y=y, h=h, x0=x0, wavail=wavail)

    def prepare(self, events, ctx, region):
        r = self.row
        K = max(1, min(self.maxlen, 12)); self.K = K
        self.cw = max(40, min(80, int((r["wavail"] - 8 * K) / K)))
        self.els[f"n_{self.var}"] = dict(x=r["name_x"], y=r["y"], w=118, h=r["h"], fs=28, plain=True, text=self.var, sub="依鍵排序" if self.ctype == "map" else "集合", sfs=16, color="neutral")
        self.els[f"qf_{self.var}"] = dict(x=r["x0"] - 4, y=r["y"] - 4, w=K * (self.cw + 8) + 4, h=r["h"] + 8, dashed=True, color="gray", fs=24, text="", shape="rect")
        keys = []
        for ev in events:
            for it in ev["state"].get(self.var, []) or []:
                k = it[0] if self.ctype == "map" else it
                if k not in keys: keys.append(k)
        for k in keys:
            self.els[f"kc_{self.var}_{self._kid(k)}"] = dict(x=0, y=r["y"], w=self.cw, h=r["h"], fs=26 if self.cw >= 50 else 20, sfs=18, color="neutral", shape="rect")
        self._last_items = {}
        for ei, ev in enumerate(events): self._render(ei, ev)

    @staticmethod
    def _kid(k): return re.sub(r"\W", "_", str(k))

    def _render(self, ei, ev):
        st = ev["state"]; v = st.get(self.var)
        if v is None:
            self._frame(ei, {}); self.expects[ei] = {}; return
        items = v
        r = self.row
        des = {f"n_{self.var}": {}, f"qf_{self.var}": dict(text="空" if not items else "")}
        seqk = []
        changed = {}
        for idx, it in enumerate(items[:self.K]):
            k, val = (it[0], it[1]) if self.ctype == "map" else (it, None)
            cid = f"kc_{self.var}_{self._kid(k)}"
            txt = ctext(k); sub = ctext(val) if val is not None else ""
            prev = self._last_items.get(k, _MISSING)
            col = "neutral"
            if prev is _MISSING: col = "green" if ei > 0 else "neutral"
            elif prev != val: col = "yellow"
            des[cid] = dict(x=r["x0"] + idx * (self.cw + 8), text=txt, sub=sub, color=col)
            seqk.append(txt)
            changed[k] = val
        self._last_items = {(it[0] if self.ctype == "map" else it): (it[1] if self.ctype == "map" else None) for it in items}
        self._frame(ei, des)
        ex = {f"seq:kc_{self.var}_:x": seqk}
        if self.ctype == "map":
            ex["pairs"] = None; ex.pop("pairs")
            for idx, it in enumerate(items[:self.K]):
                ex[f"kc_{self.var}_{self._kid(it[0])}#"] = ctext(it[1])
        if len(items) > self.K: ex = {}
        self.expects[ei] = ex


# ═════════════ 自動選用 ═════════════
GRAPH_NAME = r"^(g|adj|graph|G|edge|edges|e|mat|w|a|nb|to|tree|mp)$"
DIST_NAME = r"^(dist|d|dis|depth|level|lv|vis|visited|used|seen|mark|color|col|step|dep|par|parent)$"
FLAG_NAME = r"^(vis|visited|used|seen|mark|color|col|taken|chosen|picked)$"
MAXN_GRAPH = 20


def _series(events, name):
    return [e["values"][name] for e in events if name in e["values"]]


Q_ARR = r"^(q|Q|que|queue|qu|que\d*|q\d+|buf|queue_?arr|dq)$"
S_ARR = r"^(st|stk|stack|s|S|stack_?arr|stc)$"
Q_HEAD = r"^(head|front|hd|qh|fr|f|l|lo|qf|h|first)$"
Q_TAIL = r"^(tail|rear|back|tl|qt|bk|r|rr|hi|qr|t|e|last|cnt|sz|size|end)$"
S_TOP = r"^(top|sp|tp|ptr|stop|t|cnt|sz|size|n|len)$"


def find_hand_seqs(code, events, info, kinds, uninit=()):
    """手寫陣列佇列（q[]+head/tail）與堆疊（st[]+top）。靠『名稱＋有寫入該陣列＋trace 的虛擬容器轉移合法』三條件才認領。
    回傳 [(ctype, spec, maxlen)]；轉移合法＝每次變化只有 push（尾端加一）或 pop（佇列取前／堆疊取頂）或清空。"""
    out = []
    scal = [k for k, kd in kinds.items() if kd == "scalar" and k in info or kd == "scalar"]
    scal = [k for k in scal if k not in uninit]
    def valid(spec, ctype):
        views, nprobe = [], 0
        for ev in events:
            need = [spec["arr"], spec["a"]] + ([spec["b"]] if spec["b"] else [])
            if not all(k in ev["values"] for k in need): continue
            v = hand_view(ev["state"], spec)
            if v is None: return None
            views.append(v)
        if len(views) < 3 or views[0]: return None
        pushes = 0
        for o, n in zip(views, views[1:]):
            if o == n: continue
            if n == []: continue
            if n[:len(o)] == o and len(n) == len(o) + 1: pushes += 1; continue
            if ctype == "queue" and n == o[1:]: continue
            if ctype == "stack" and n == o[:-1]: continue
            return None
        if pushes < 2: return None
        return max(len(v) for v in views)
    for arr in info:
        if kinds.get(arr) not in ("arr1", "seq") or info[arr]["kind"] not in ("arr1", "seq"): continue
        if not re.search(r"\b%s\s*\[[^\]]+\]\s*=(?!=)" % re.escape(arr), code): continue
        if re.match(Q_ARR, arr):
            for a in scal:
                if not re.match(Q_HEAD, a): continue
                for b in scal:
                    if b == a or not re.match(Q_TAIL, b): continue
                    for e0 in (0, 1):
                        spec = dict(arr=arr, a=a, b=b, s0=0, e0=e0)
                        mx = valid(spec, "queue")
                        if mx: out.append(("queue", spec, mx)); break
                    else: continue
                    break
                else: continue
                break
        elif re.match(S_ARR, arr):
            for a in scal:
                if not re.match(S_TOP, a): continue
                for s0, e0 in ((0, 0), (0, 1), (1, 1)):
                    spec = dict(arr=arr, a=a, b=None, s0=s0, e0=e0)
                    mx = valid(spec, "stack")
                    if mx: out.append(("stack", spec, mx)); break
                else: continue
                break
    return out


SEQ_CAP = dict(stack=8, queue=12, deque=12, priority_queue=12)   # SeqComp 最多畫幾張卡（stack＝8，其他＝12）；KeyedComp＝12


def trunc_note(kind_zh, var, mx, cap):
    """D-012（F4）：容器同時最大項數超過元件顯示上限 → 一則 notes（detect 會轉成 warnings.json 的 type=truncated，summary 隨之變成「缺元件警示 N 項」）"""
    return f"{kind_zh} {var} 同時最多 {mx} 項，只顯示 {cap} 項（超過的卡片不畫、不驗）"


def select(src_text, events, plan, kinds, uninit=(), disabled=()):
    """回傳 (comps, claimed_vars, notes)。每個元件只在 trace 形狀與程式用法都符合時才認領變數。"""
    code = re.sub(r"//[^\n]*", "", src_text)
    info = plan["info"]
    comps, claimed, notes = [], set(), []
    ctypes = container_types(src_text)
    zones = set()

    def ints_in(v):
        out = []
        if isinstance(v, list):
            for x in v: out += ints_in(x)
        elif is_int(v): out.append(v)
        return out

    hands = [] if "seq" in disabled else find_hand_seqs(code, events, info, kinds, uninit)
    # —— 圖 ——
    if "graph" not in disabled:
        for a in list(info):
            if "left" in zones: break
            kd = kinds.get(a)
            if a in claimed or kd not in ("arrv", "seq2", "arr2"): continue
            form = "list" if kd in ("arrv", "seq2") else "matrix"
            if kd == "seq2" and not (re.search(r"\b%s\s*\[[^\]]+\]\s*\.\s*(?:push_back|emplace_back)\s*\(" % a, code) or re.search(r":\s*%s\s*\[[^\]]+\]\s*\)" % a, code)): continue
            if kd == "arr2" and not (re.match(GRAPH_NAME, a) and re.search(r"\b%s\s*\[\s*\w+\s*\]\s*\[\s*\w+\s*\]" % a, code)): continue
            ser = _series(events, a)
            if not ser: continue
            # 節點數：被用到的最大編號＋1
            N = 0
            for v in ser:
                if form == "list":
                    for u, row in enumerate(v):
                        if row: N = max(N, u + 1, max(x for x in row if is_int(x)) + 1 if any(is_int(x) for x in row) else 0)
                else:
                    for u, row in enumerate(v):
                        for w, x in enumerate(row):
                            if x not in (0, False, None, "") and not (is_int(x) and abs(x) >= SENT): N = max(N, u + 1, w + 1)
            # dist／vis 伴隨陣列
            dv = None
            for b in info:
                if b != a and info[b]["kind"] == "arr1" and re.match(DIST_NAME, b) and kinds.get(b) in ("arr1", "seq"):
                    dv = b; N = max(N, info[b]["n"]) if info[b]["n"] <= MAXN_GRAPH else N; break
            if N < 2 or N > MAXN_GRAPH:
                notes.append(f"圖 {a}：節點數 {N} 超出 2–{MAXN_GRAPH}，不套用圖元件"); continue
            if form == "matrix":
                last = ser[-1]
                sym = all((last[u][w] != 0) == (last[w][u] != 0) for u in range(min(N, len(last))) for w in range(min(N, len(last[u]))) if w < len(last) and u < len(last[w]))
                directed = not sym
            else:
                # 無向：最後狀態 u→v 必有 v→u
                last = ser[-1]
                E = {(u, v) for u, row in enumerate(last) for v in row if is_int(v)}
                directed = any((v, u) not in E for (u, v) in E) if E else False
            weighted = False
            if form == "matrix":
                vals = {x for v in ser[-1:] for row in v[:N] for x in row[:N] if is_int(x) and x not in (0, 1) and abs(x) < SENT}
                weighted = bool(vals)
            # 焦點指標：用來當 g／dist 索引或走訪迴圈變數的純量
            foc = set()
            for pat in (r"\b%s\s*\[\s*(\w+)\s*\]" % a, r"\b%s\s*\[\s*(\w+)\s*\]" % (dv or "__none__"), r"for\s*\(\s*(?:const\s+)?(?:auto|int)\s*&?\s*(\w+)\s*:\s*%s\s*\[" % a):
                for m in re.finditer(pat, code):
                    if kinds.get(m.group(1)) == "scalar": foc.add(m.group(1))
            qv = [q for q, t in ctypes.items() if q in info and kinds.get(q) == "seq"] + [sp for t, sp, _ in hands if t == "queue"]
            flag_like = False
            if dv:
                vs = {x if not isinstance(x, str) else ord(x) for ser_ in _series(events, dv) for x in ser_}
                flag_like = bool(re.match(FLAG_NAME, dv)) or vs <= {0, 1, True, False}
            gc = GraphComp(a, form, N, directed, None, dv, qv, sorted(foc), weighted, events, info)
            gc.flag_like = flag_like
            # 距離陣列＋另一個 0/1 旗標陣列（Dijkstra：dist＋vis）→ 旗標決定已確定（綠），距離當副標
            gc.flag_var = None
            if dv and not flag_like:
                for b in info:
                    if b != dv and b != a and re.match(FLAG_NAME, b) and kinds.get(b) in ("arr1", "seq") and info[b]["n"] == info[dv]["n"]:
                        vs2 = {x if not isinstance(x, str) else ord(x) for ser_ in _series(events, b) for x in ser_}
                        if vs2 <= {0, 1, True, False}: gc.flag_var = b; break
            gc.uninit = set(uninit)
            comps.append(gc); claimed.add(a); zones.add("left")
            break

    # —— 佇列／堆疊／優先佇列 ——
    nrow = 0
    for q, t in ctypes.items():
        if "seq" in disabled: break
        if q not in info or kinds.get(q) != "seq" or q in claimed: continue
        ser = _series(events, q)
        mx = max([len(v) for v in ser] + [0])
        if mx == 0: continue
        if t == "stack":
            if "right" in zones: continue
            zones.add("right")
        else:
            if nrow >= 2: continue
            nrow += 1
        comps.append(SeqComp(q, t, mx, events)); claimed.add(q)
        if mx > SEQ_CAP.get(t, 12): notes.append(trunc_note({"stack": "堆疊", "priority_queue": "優先佇列"}.get(t, "佇列"), q, mx, SEQ_CAP.get(t, 12)))
    for t, sp, mx in hands:
        if sp["arr"] in claimed: continue
        if t == "stack":
            if "right" in zones: continue
            zones.add("right")
        else:
            if nrow >= 2: continue
            nrow += 1
        comps.append(SeqComp(sp["arr"], t, mx, events, hand=sp)); claimed.add(sp["arr"])
        if mx > SEQ_CAP.get(t, 12): notes.append(trunc_note({"stack": "堆疊", "priority_queue": "優先佇列"}.get(t, "佇列"), sp["arr"], mx, SEQ_CAP.get(t, 12)))

    # —— 槽位列 ——
    if "slots" not in disabled and "top" not in zones and "left" not in zones:
        for r in list(info):
            if r in claimed or kinds.get(r) not in ("arr1", "seq") or info[r]["kind"] not in ("arr1", "seq"): continue
            ser = _series(events, r)
            if not ser: continue
            lens = {len(v) for v in ser}
            if len(lens) != 1: continue
            n = lens.pop()
            if not 3 <= n <= 10: continue
            fin = ser[-1]
            if sorted(x for x in fin if is_int(x)) != list(range(n)): continue
            wr = [(m.start(), m.group(1)) for m in re.finditer(r"\b%s\s*\[([^\]\[]+)\]\s*=(?!=)" % re.escape(r), code)]
            if len(wr) < 2: continue
            if any(re.fullmatch(r"\s*" + re.escape(ix) + r"\s*", code[code.find("=", pos) + 1: code.find(";", pos)]) for pos, ix in wr): continue
            lines = [(code.count("\n", 0, pos) + 1, ix) for pos, ix in wr]
            comp = None
            m = re.search(r"\b(\w+)\s*\[\s*%s\s*\[" % re.escape(r), code)
            if m and m.group(1) in info and kinds.get(m.group(1)) in ("arr1", "seq"): comp = m.group(1)
            flag = next((b for b in info if re.match(FLAG_NAME, b) and kinds.get(b) in ("arr1", "seq") and b != r and b not in claimed), None)
            letters = "'A'" in code
            sc = SlotsComp(r, comp, flag, n, letters, lines, events)
            comps.append(sc); claimed.add(r); zones.add("top")
            if flag: claimed.add(flag)
            break

    # —— 陣列樹 ——
    if "tree" not in disabled and "left" not in zones and "top" not in zones:
        tc = select_tree(code, events, plan, kinds, uninit)
        if tc:
            comps.append(tc); claimed |= set(tc.hide); zones.add("left")

    # —— map／set ——
    if "keyed" not in disabled:
        for a in list(info):
            if kinds.get(a) in ("map", "set") and a not in claimed and nrow < 2:
                ser = _series(events, a)
                mx = max([len(v) for v in ser] + [0])
                if mx == 0: continue
                comps.append(KeyedComp(a, kinds[a], mx)); claimed.add(a); nrow += 1
                if mx > 12: notes.append(trunc_note("map" if kinds[a] == "map" else "set", a, mx, 12))
    return comps, claimed, notes


def select_tree(code, events, plan, kinds, uninit):
    info = plan["info"]
    arr1 = [a for a in info if kinds.get(a) in ("arr1", "seq") and info[a]["kind"] in ("arr1", "seq")]
    lr = [(a, b) for a in arr1 for b in arr1 if a < b and ({a.lower(), b.lower()} in ({"l", "r"}, {"lc", "rc"}, {"left", "right"}, {"lch", "rch"}, {"ls", "rs"}, {"lson", "rson"}))]
    if not lr: return None
    a, b = lr[0]
    L, R = (a, b) if a.lower() in ("l", "lc", "left", "lch", "ls", "lson") else (b, a)
    key = next((k for k in arr1 if k in ("key", "val", "value", "v", "data", "a", "num", "w") and k not in (L, R)), None)
    root = next((k for k, kd in kinds.items() if kd == "scalar" and k in ("root", "rt", "r0")), None)
    n = info[L]["n"]
    series0 = (_series(events, L) or [[0]])[0]
    # 節點數＝全程出現過的父子端點＋有 key 的格子，上限 15
    used = set()
    for ev in events:
        Ls, Rs = ev["state"].get(L), ev["state"].get(R)
        if isinstance(Ls, list) and isinstance(Rs, list):
            for u in range(min(len(Ls), len(Rs))):
                for c in (Ls[u], Rs[u]):
                    if is_int(c) and c != (-1 if all(x == -1 for x in series0) else 0) and 0 <= c < len(Ls): used.add(u); used.add(c)
    if len(used) > 15: return None
    # 必須真的有「寫入子節點指標」的行為
    if not re.search(r"\b%s\s*\[[^\]]+\]\s*=(?!=)" % L, code): return None
    foc = set()
    for pat in (r"\b(?:%s|%s)\s*\[\s*(\w+)\s*\]" % (L, R),) + ((r"\b%s\s*\[\s*(\w+)\s*\]" % key,) if key else ()):
        for m in re.finditer(pat, code):
            if kinds.get(m.group(1)) == "scalar": foc.add(m.group(1))
    for pm in re.finditer(r"\b(\w+)\s*\(\s*(?:int\s+)?(\w+)\s*[,)]", code):
        pass
    null = 0
    # null 值：0 或 -1，看初值
    firsts = _series(events, L)
    if firsts and all(x == -1 for x in firsts[0]): null = -1
    tc = TreeComp(L, R, key, root, null, sorted(foc), events, info)
    tc.nmax = n
    return tc
