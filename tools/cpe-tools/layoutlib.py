"""版面幾何（純函式，不依賴 tree-sitter／沙箱，可被測試直接 import）。
從 autoanim.py 抽出：layout()（陣列列／純量 chip）、元件區域 comp_region()、build_geometry()（原 generate 的版面前段）、marker_els()（指標 ▲）。
autoanim.generate 與離線重放測試共用同一份程式，確保測試的幾何 = 真正產生的幾何。"""

PAIR_MAX = 10


STAGE_W = 1200          # 虛擬舞台寬（預設，舊版面逐值不變）
NARROW_STAGE_W = 1000   # 退路：split2 的槽位窄版（右窗 1020 寬 → 倍率 ≥1.0 → 槽卡 68×1.02≈69px）


def is_narrow(zones, stage_w):
    """窄版只用於「有頂部槽位列（top）、沒有左／右欄元件」的 story 且 stage_w<1200；其餘一律維持 1200 舊幾何（逐值不變）"""
    return stage_w < STAGE_W and "top" in zones and not ({"left", "right"} & set(zones))


def layout(plan, init_state, x0=128, wavail=1060, ystart=None, name_x=0, nrows=0, compact=False, chip_xmax=None, narrow=False, content_h=None):
    """回傳 elements: id -> props(x,y,w,h,fs,...)；舞台 1200×460（narrow：寬 stage_w≈1000，成對陣列改上下排）"""
    els = {}
    info = plan["info"]
    # 頂部有槽位列（compact）時，指標 ▲ 列距 26→22、字 24→20（成片仍 ≥26px），省下高度給放大的槽位卡
    P, PH, PF = (22, 22, 20) if compact else (26, 30, 24)
    plan["ptr_geom"] = (P, PH, PF)
    y = 8 if compact else 14
    plan["row_ys"] = []
    if plan["chips"]:
        # 右側有堆疊欄（x≥1040）時，chip 列不得伸進去：放得下就維持原本 146 間距／136 寬；放不下（8 個 chip）改均分（間距 128、寬 118）
        nchip = len(plan["chips"]); pitch, cw_ = 146, 136
        if chip_xmax is not None and 10 + 146 * (nchip - 1) + 136 > chip_xmax:
            pitch = int((chip_xmax - 10) / nchip); cw_ = pitch - 10
        for n, k in enumerate(plan["chips"]):
            els[f"v_{k}"] = dict(x=10 + pitch * n, y=y, w=cw_, h=64, fs=34, sfs=20) if compact else dict(x=10 + pitch * n, y=y, w=cw_, h=84, fs=38, sfs=24)
        y += 76 if compact else 104
    if ystart is not None: y = max(y, ystart)
    for _ in range(nrows):
        plan["row_ys"].append(y); y += 66
    arrays = plan["arrays"]
    y_arr = y

    # 頂部有槽位列（compact）時，相鄰兩個 ≤PAIR_MAX 格的一維陣列左右並排（省一整列的高度）；其他情形與以前逐值相同
    # PAIR_MAX 6→10（槽位 7–10 格時 cnt／c 不再各佔一列；半寬 466px 放 10 格仍有格寬 38、字 24）
    groups, gi = [], 0
    while gi < len(arrays):
        a0 = arrays[gi]
        if compact and not narrow and info[a0]["kind"] != "arr2" and info[a0]["n"] <= PAIR_MAX and gi + 1 < len(arrays) and info[arrays[gi + 1]]["kind"] != "arr2" and info[arrays[gi + 1]]["n"] <= PAIR_MAX:
            groups.append([a0, arrays[gi + 1]]); gi += 2
        else:
            groups.append([a0]); gi += 1
    total_w = (x0 - name_x) + wavail

    def build(strict, H=460):
        out = {}
        yy = y_arr
        np_ = {a: len(plan["ptrs"].get(a, [])) for a in arrays}
        extra_of = {a: max(0, P * np_[a] - PH) for a in arrays}   # 多個指標列（▲i ▲j…）要保留的高度
        gnp = {g[0]: max(np_[a] for a in g) for g in groups}
        gextra = {g[0]: max(extra_of[a] for a in g) for g in groups}
        n1 = sum(1 for g in groups if info[g[0]]["kind"] != "arr2")
        n2 = [a for a in arrays if info[a]["kind"] == "arr2"]
        if strict:   # 空間不夠：先扣掉每列固定要的（間距＋指標列），再平分
            fixed = sum((6 + (P * gnp[g[0]] + 4 if gnp[g[0]] else 0)) if info[g[0]]["kind"] != "arr2" else (info[g[0]]["r"] * 6 + 8) for g in groups)
            unit = (H - yy - 6 - fixed) / max(1, n1 + 3 * len(n2))
        else:
            unit = (H - yy - 6 - sum(gextra.values())) / max(1, n1 + 3 * len(n2))
        low_y = yy
        for g in groups:
            ai0 = info[g[0]]
            if ai0["kind"] != "arr2":
                npg = gnp[g[0]]
                if strict:
                    ch = int(max(28, min(86, unit))); rowh = ch + 6 + (P * npg + 4 if npg else 0)
                else:
                    rowh = min(130, unit); ch = max(36, rowh - 44); rowh = max(rowh, ch + 10) + gextra[g[0]]
                    if npg: rowh = max(rowh, ch + 2 + P * npg + 4)   # 格高夾在下限 36 時，▲ 列不得伸進下一列的格子（原本只在 low_y 計入）
                W2 = int(total_w / 2)
                for k, a in enumerate(g):
                    ai = info[a]
                    nx, cx0, wav = (name_x, x0, wavail) if len(g) == 1 else (name_x + k * W2, x0 + k * W2, W2 - (x0 - name_x) - 6)
                    L = ai["n"]
                    w = max(24, min(92, int((wav - 8 * L) / L)))
                    fs = 38 if w >= 70 else (30 if w >= 50 else (24 if w >= 34 else 20))
                    gw = ai.get("maxgw")   # 內容寬受限（content_w）時才有：全片最寬格文字（em）→ 字級降到放得進格內寬（w-8）；沒有＝與以前相同
                    while gw and fs > 20 and gw * fs > w - 8: fs = {38: 30, 30: 24, 24: 20}[fs]
                    out[f"n_{a}"] = dict(x=nx, y=yy, w=118, h=ch, fs=30, plain=True)
                    for i in range(L):
                        out[f"c_{a}_{i}"] = dict(x=cx0 + i * (w + 8), y=yy, w=w, h=ch, fs=fs, sfs=20)
                    ai.update(cw=w, cx0=cx0, cy=yy, ch=ch, gap=8)
                    low_y = max(low_y, yy + ch + 2 + P * np_[a] + 4)
                yy += rowh
            else:
                a = g[0]; ai = ai0
                R, C = ai["r"], ai["c"]
                grid_h = unit * 3
                ch = max(30, min(64, int(grid_h / R) - 6))
                w = max(34, min(84, int((wavail - 8 * C) / C)))
                fs = 30 if w >= 50 else 22
                out[f"n_{a}"] = dict(x=name_x, y=yy, w=118 if not ai.get("rowlab") else 56, h=ch, fs=30, plain=True)
                if ai.get("rowlab"):
                    for i in range(R): out[f"r_{a}_{i}"] = dict(x=name_x + 58, y=yy + i * (ch + 6), w=66, h=ch, fs=24, plain=True)
                for i in range(R):
                    for j in range(C):
                        out[f"c_{a}_{i}_{j}"] = dict(x=x0 + j * (w + 8), y=yy + i * (ch + 6), w=w, h=ch, fs=fs, sfs=18)
                ai.update(cw=w, cx0=x0, cy=yy, ch=ch, gap=8)
                yy += R * (ch + 6) + 8
                low_y = max(low_y, yy)
        return out, low_y

    if arrays and content_h:   # 內容高上限（split2 右窗 1020×800 比例較高，寬受限時高度不是瓶頸）→ 直接用這個高度排；None＝與以前相同
        out, low_y = build(False, content_h)
        if low_y > content_h - 2: out, low_y = build(True, content_h)
        els.update(out)
    elif arrays:
        out, low_y = build(False)
        if low_y > 458: out, low_y = build(True)
        if low_y > 458: out, low_y = build(True, 580)   # 舞台框外仍可見（框外沒有裁切，影片下方有空間）：內容真的放不下才往下延伸
        els.update(out)
    return els


def cell_text(v):
    if isinstance(v, bool): return "1" if v else "0"
    if isinstance(v, str) and len(v) == 1 and ord(v) < 32: return str(ord(v))  # vector<char> 當旗標用：\x01 顯示成 1
    if isinstance(v, float): return f"{v:g}"
    return str(v)


def make_cell_fn(info):
    def cell_fn(a, i, v):
        ai = info.get(a, {})
        if ai.get("touched") is not None and isinstance(v, int) and not isinstance(v, bool) and ai.get("base") and i < len(ai["base"]) and v == ai["base"][i] and v != 0: return "?"
        return cell_text(v)
    return cell_fn


def comp_region(c, plan, ytop, stage_w=STAGE_W):
    """各元件區域 (x0,y0,x1,y1)；row 型回傳 None（由 region_row 指定）"""
    if c.zone == "left":
        # 樹：沒有其他陣列列要排時，整個動畫區寬都給樹（節點可以放大）；有陣列時維持左 470 寬
        if c.kind == "tree" and not plan["arrays"]:
            return (4, ytop + 2, 1196, 456)
        return (4, ytop + 2, 470, 456)
    if c.zone == "right": return (1040, ytop + 30, 1196, 452)
    if c.zone == "top": return (6, ytop - 4, stage_w - 6, ytop - 4 + getattr(c, "height", 122))
    return None


def build_geometry(comps, plan, init_state, cell_fn, events, stage_w=STAGE_W, content_w=None, content_h=None):
    """依元件決定 ytop／lay，排好陣列列並讓每個元件 prepare+finalize。回傳 (els, dict(ytop, lay, compact, narrow, stage_w))
    stage_w：虛擬舞台寬；預設 1200＝與以前逐值相同。<1200 且有頂部槽位列、無左／右欄元件時才啟用窄版（槽卡縮、說明欄縮、陣列不再左右成對）。"""
    zones = {c.zone for c in comps}
    narrow = is_narrow(zones, stage_w)
    if not narrow: stage_w = STAGE_W
    compact = any(c.zone == "top" for c in comps)   # 頂部有槽位列：純量 chip 縮小一點，把高度讓給下面的陣列
    ytop = (8 + 76 if compact else 14 + 104) if plan["chips"] else (8 if compact else 14)
    lay = dict(x0=128, wavail=1060, ystart=None, name_x=0, nrows=sum(1 for c in comps if c.zone == "row"))
    if "left" in zones: lay.update(name_x=480, x0=608, wavail=1200 - 608 - 10)
    if "right" in zones: lay["wavail"] -= 170; lay["chip_xmax"] = 1030    # 堆疊欄 x≥1040；chip 列不得伸進去
    if narrow:
        lay["wavail"] = 1060 - (STAGE_W - stage_w); lay["chip_xmax"] = stage_w - 6; lay["narrow"] = True
    if content_w:   # 右窗內容寬上限（虛擬座標；陣列列與 chip 列都不超過），None＝與以前逐值相同
        lay["wavail"] = min(lay["wavail"], content_w - lay["x0"]); lay["chip_xmax"] = min(lay.get("chip_xmax", content_w), content_w)
    if content_h: lay["content_h"] = content_h
    if "top" in zones: lay["ystart"] = ytop - 4 + max((getattr(c, "height", 122) for c in comps if c.zone == "top"), default=122) + 6
    els = layout(plan, init_state, compact=compact, **lay)
    rowi = 0
    for c in comps:
        reg = comp_region(c, plan, ytop, stage_w)
        c.narrow = narrow
        if c.zone == "row":
            c.region_row(lay["name_x"], plan["row_ys"][rowi], 54, lay["x0"], lay["wavail"]); rowi += 1; reg = None
        c.prepare(events, dict(cell=cell_fn), reg)
        c.finalize()
        if getattr(c, "crowded", False):   # 橢圓也排不開 → 記錄，autoanim 寫入 warnings.json（type=layout_overlap）
            plan.setdefault("geo_warnings", []).append(dict(variables=list(c.vars), now=f"圖 {getattr(c, 'var', '')} 的 {getattr(c, 'N', '?')} 個節點（直徑 {getattr(c, 'd', '?')}）在可用區域內外框仍會重疊"))
    return els, dict(ytop=ytop, lay=lay, compact=compact, narrow=narrow, stage_w=stage_w)


def marker_els(plan):
    """指標 ▲ 元件的基礎幾何：eid → (陣列, 指標變數, 第幾個, props)；需先跑過 layout()（info 內有 cx0/cy/ch/cw）"""
    out = {}
    info = plan["info"]
    P, PH, PF = plan.get("ptr_geom", (26, 30, 24))
    for a, plist in plan["ptrs"].items():
        ai = info[a]
        for n_, p in enumerate(plist):
            out[f"m_{a}_{p}"] = (a, p, n_, dict(x=ai["cx0"], y=ai["cy"] + ai["ch"] + 2 + P * n_, w=ai["cw"], h=PH, fs=PF, plain=True))
    return out
