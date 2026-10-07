#!/usr/bin/env python3
"""pixel_table.py：不渲染，從 story.json 的幾何與版面倍率推算 1920×1080 成片的「最小元素像素表」。

用法：
  python3 pixel_table.py [資料夾 ...]          # 預設：audit/* 與 public/aud_*（資料夾可為絕對路徑或 public/ 下的名稱）
    --model legacy|fit|matrix   legacy＝固定 RECTS（現行渲染）；fit＝story.stageFit=="auto" 的自適應；matrix（預設）＝依序列出 legacy、fit，
                                以及假設全部改用 wide／concept 版面的 fit（供選版面）
    --as-layout wide|concept|split2    把 split 場景假設成該版面再算（只影響推算，不改檔）
    --json                      輸出 JSON（每樣本每 model 的 min/count/判定）
    --write-warnings OUTDIR     把 stage_fit 警示合併進 OUTDIR/<樣本名>/warnings.json（以原資料夾的 warnings.json 為底；不會改動原資料夾）
    --strict-exit               有任何樣本未達標 → exit 1（預設 exit 0，僅列表）
另附兩段（不改既有表格）——字幕框與各版面程式面板底的重疊像素（layoutRev<2 時 wide 15px；layoutRev≥2 為 0）；
       含 fullcode 場景的樣本：行數／最長行字元／字級／欄內所需寬 vs 可用寬／面板底／判定（fullcode 無動畫舞台，A1 項目對它 n/a，其舞台元素不計入 A1）。
A1 門檻（1920×1080 成片像素）：一般文字≥26；槽位卡高≥90（槽位≤8）；節點直徑≥64、節點字≥28（節點≤10）；佇列/堆疊格高≥64（假設≤8 格）。
內容超過上限時容許縮到 75% 但要出警示；低於 75% 或沒超限卻低於門檻＝未達標。
元件退化（資料夾 warnings.json 內 status=degraded 的 slots／graph_*／tree_array／queue／stack／priority_queue）時，對應 A1 項目顯示 n/a(退化)，
整體判定 n/a（元件退化），不計達標；新增「文字溢出」欄（文字估寬 > 框內寬）；規則：副標字級（23–25px）不計入 A1 文字判定；
split 程式段不要求達 A1；concept 下舊模式 --no-comps 縮小屬排除項。
元素群組以 id 前綴辨識：pc_/sl_＝槽位卡/槽、gn_/tn_＝圖/樹節點、qc_＝佇列/堆疊格。副標字級另列（不計入判定）。
"""
import argparse, glob, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import stagefit as sf

HERE = Path(__file__).parent
PUB = Path(os.environ.get("NARRATE_PUB", str(Path(__file__).resolve().parents[2] / "public")))
SYM = dict(pass_="✓", pass_over="✓*", pass_floor="△", fail="✗", na="-", na_degraded="n/a(退化)")


def resolve(name):
    p = Path(name)
    if p.is_absolute() or p.exists(): return p
    return PUB / name


def default_folders():
    return sorted(glob.glob(str(HERE / "audit" / "*"))) + sorted(glob.glob(str(PUB / "aud_*")))


def cell(r, unit=""):
    if r["status"] == "na": return "-"
    if r["status"] == "na_degraded": return SYM["na_degraded"]     # 元件退化＝畫面沒有該元素，不是達標
    s = "pass_" if r["status"] == "pass" else r["status"]
    return f"{r['value']:.0f}{SYM[s]}"


def analyse(folder, model, as_layout=None):
    story = json.loads((Path(folder) / "story.json").read_text(encoding="utf-8"))
    lm = {"split": as_layout, "split2": as_layout} if as_layout else None
    m = sf.metrics(story, model, lm)
    deg = sf.load_degraded(folder)        # warnings.json 內 status=degraded 的元件型態 → 對應 A1 項目判 n/a（退化）
    res = sf.judge(m, degraded=deg)
    ov, bad = sf.overall(res)
    rl = sf.ruling(story, model, lm, degraded=deg)[0]   # 規則：wide／concept 判 A1；split 只受 75% 下限
    ovf = sf.text_overflow(story)         # 文字估寬 > 框內寬
    return dict(ruling=rl, overflow=len(ovf), overflow_items=sorted(ovf)[:6], degraded=sorted(deg), name=Path(folder).name, model=model + (f"@{as_layout}" if as_layout else ""), scales=m["scales"], count=m["count"],
                min={k: (None if v is None else round(v, 2)) for k, v in m["min"].items()}, verdict=ov, failed=bad,
                items={k: dict(status=r["status"], value=None if r["value"] is None else round(r["value"], 2), need=r["need"]) for k, r in res.items()},
                _res=res)


# 各版面程式面板底（RECTS：concept 842+126、wide 872+126、split／code 125+835）與字幕框頂（舊 story 983；layoutRev≥2 為 1001）
CODE_PANEL_END = {"concept": 842 + 126, "wide": 872 + 126, "split": 125 + 835, "code": 125 + 835, "split2": 100 + 852}


def subtitle_overlap(folder):
    story = json.loads((Path(folder) / "story.json").read_text(encoding="utf-8"))
    rev = story.get("layoutRev") or 0
    top = sf.SUBTITLE_TOP_REV2 if rev >= 2 else sf.SUBTITLE_TOP_BOX
    used = sorted({(c.get("layout") or sc["layout"]) for sc in story["scenes"] for c in sc["cues"]})
    lay = {L: max(0, CODE_PANEL_END[L] - top) for L in used if L in CODE_PANEL_END}
    if "split2" in used: lay["split2"] = max(0, sf.SPLIT2["panel"]["y"] + sf.SPLIT2["panel"]["h"] - top)
    if "fullcode" in used:
        code = (Path(folder) / "code.cpp").read_text(encoding="utf-8") if (Path(folder) / "code.cpp").exists() else ""
        lay["fullcode"] = max(0, sf.fullcode_metrics(code)["panel_bottom"] - top)
    return dict(name=Path(folder).name, layoutRev=rev, subtitle_top=top, overlap=lay)


def analyse_fullcode(folder):
    story = json.loads((Path(folder) / "story.json").read_text(encoding="utf-8"))
    scs = sf.fullcode_scenes(story)
    if not scs: return None
    cp = Path(folder) / "code.cpp"
    m = sf.fullcode_metrics(cp.read_text(encoding="utf-8") if cp.exists() else "")
    caps = sum(1 for sc in scs for c in sc["cues"] if c.get("cap"))
    return dict(name=Path(folder).name, scenes=[sc["id"] for sc in scs], caps_ignored=caps, **m)


RSYM = dict(pass_="全額", pass_floor="退路達標＋警示", fail="不達標", na="-", na_degraded="n/a")


def analyse_split2(folder):
    story = json.loads((Path(folder) / "story.json").read_text(encoding="utf-8"))
    scs = sf.split2_scenes(story)
    if not scs: return None
    cp = Path(folder) / "code.cpp"
    m = sf.split2_metrics(cp.read_text(encoding="utf-8") if cp.exists() else "")
    # split2 有槽位時的退路分級（槽卡 ≥90 全額／68–89 警示通過／<68 不達標；文字 ≥26／20–25／<20）；無槽位則為 None（照舊全額判定）
    deg = sf.load_degraded(folder)
    per = sf.ruling(story, "fit", degraded=deg)[1].get("split2")
    ret = None
    if per and per[0]["slot_h"].get("retreat"):
        r_ = per[0]
        ret = {k: dict(value=None if r_[k]["value"] is None else round(r_[k]["value"], 1), status=r_[k]["status"]) for k in ("slot_h", "text")}
    return dict(name=Path(folder).name, scenes=[sc["id"] for sc in scs], retreat=ret, **m)


def render_split2(rows):
    hdr = ["樣本", "split2 場景數", "程式字級", "最長行≤58", "面板內需寬/可用", "整行可見行數≥20", "右窗(fit 區)≥950×700", "面板底(<983)", "槽卡高(退路)", "文字(退路)", "判定"]
    out = ["### split2（左程式面板 820×852＋右窗 1020×800；A1 判全額，元件像素見上方表格各 split2 列）", "", "| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] * len(hdr)) + "|"]
    for r in rows:
        out.append("| " + " | ".join([r["name"], str(len(r["scenes"])), str(r["fs"]), f"{r['longest']}（{r['lines']} 行）", f"{r['need_px']:.0f}/{r['avail_px']:.0f}", str(r["visible_lines"]),
                                      f"{r['win_w']}×{r['win_h']}", str(r["panel_bottom"]),
                                      "-" if not r.get("retreat") else f"{r['retreat']['slot_h']['value']}px {RSYM[r['retreat']['slot_h']['status']]}", "-" if not r.get("retreat") else f"{r['retreat']['text']['value']}px {RSYM[r['retreat']['text']['status']]}",
                                      "達標" if r["ok"] else "未達標：" + "；".join(r["reasons"])]) + " |")
    return "\n".join(out + [""])


def render_fullcode(rows):
    hdr = ["樣本", "fullcode 場景", "行數≤容量", "最長行≤58", "字級≥22", "欄內需寬/可用", "面板底(<983)", "判定"]
    out = ["### fullcode（整份程式雙欄；倍率 1.0、無動畫舞台）", "", "| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] * len(hdr)) + "|"]
    for r in rows:
        out.append("| " + " | ".join([r["name"], ",".join(r["scenes"]), str(r["lines"]), str(r["longest"]), str(r["fs"]), f"{r['need_px']:.0f}/{r['avail_px']}", str(r["panel_bottom"]),
                                      "達標" if r["ok"] else "未達標：" + "；".join(r["reasons"])]) + " |")
    return "\n".join(out + [""])


def render_subtitle(rows):
    out = ["### 字幕框與程式面板重疊（px，0＝不重疊）", "", "| 樣本 | layoutRev | 字幕框頂 | " + " | ".join(["concept", "wide", "split", "split2", "code", "fullcode"]) + " |", "|" + "|".join(["---"] * 9) + "|"]
    for r in rows:
        out.append("| " + " | ".join([r["name"], str(r["layoutRev"]), str(r["subtitle_top"])] + [str(r["overlap"].get(L, "-")) for L in ("concept", "wide", "split", "split2", "code", "fullcode")]) + " |")
    return "\n".join(out + [""])


def render(rows, title):
    hdr = ["樣本", "版面×倍率", "文字≥26", "(副標)", "槽位卡高≥90", "節點直徑≥64", "節點字≥28", "格高≥64", "槽/點/格數", "文字溢出", "判定(全額 A1)", "裁定判定"]
    out = [f"### {title}", "", "| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] * len(hdr)) + "|"]
    for r in rows:
        res = r["_res"]
        sub = r["min"]["text_sub"]
        lay = " ".join(f"{L}×{s:.2f}" for L, s in sorted(r["scales"].items()))
        n = r["count"]
        out.append("| " + " | ".join([r["name"], lay, cell(res["text"]), "-" if sub is None else f"{sub:.0f}", cell(res["slot_h"]), cell(res["node_d"]), cell(res["node_fs"]), cell(res["cell_h"]),
                                      f"{n['slot']}/{n['node']}/{n['cell']}", str(r["overflow"]), r["verdict"] + ("" if not r["failed"] else "：" + "、".join(r["failed"])), r["ruling"]]) + " |")
    npass = sum(1 for r in rows if r["verdict"] == "達標")
    nr = sum(1 for r in rows if r["ruling"] == "達標"); nw = sum(1 for r in rows if r["ruling"] == "警示"); nn = sum(1 for r in rows if r["ruling"] == sf.NA_DEG)
    nov = sum(1 for r in rows if r["overflow"])
    out += ["", f"裁定判定（wide／concept／split2 判全額 A1；split 僅受 75% 下限＋警示；split2 有槽位時槽卡 ≥68、文字 ≥20 為「退路達標＋警示」）：達標 {nr}、警示 {nw}、n/a（元件退化）{nn}、未達標 {len(rows) - nr - nw - nn}（共 {len(rows)}）", "",
            f"全額 A1 達標 {npass}/{len(rows)}（✓ 達標；✓* 內容超過上限但仍達標；△ 超過上限且縮到 75%~100%，需警示；✗ 未達標；- 此樣本沒有該元素；n/a(退化)＝該元件退化（warnings.json 的 degraded），畫面沒有該元素，不算達標；單位 px，取全片最小值）",
            f"文字溢出（估寬 > 框內寬；只估算）：{nov} 個樣本有溢出元素" + ("：" + "；".join(f"{r['name']}={r['overflow']}" for r in rows if r["overflow"]) if nov else ""), ""]
    return "\n".join(out)


def recommend(allrows):
    """每個樣本：現行(legacy)與 fit 是否達標；若 split 達不到，列出 wide／concept(fit) 哪個能達標。"""
    names = [r["name"] for r in allrows[("legacy", None)]]
    idx = {k: {r["name"] + "#" + str(i): r for i, r in enumerate(rows)} for k, rows in allrows.items()}
    out = ["### 版面建議（以 fit 推算；split 是『左程式右動畫』，wide／concept 的程式碼只剩底部小列）", "",
           "| 樣本 | 現行 legacy | split+fit | wide+fit | concept+fit | 建議 |", "|---|---|---|---|---|---|"]
    for i, n in enumerate(names):
        v = {k: rows[i] for k, rows in allrows.items()}
        f = lambda k: v[k]["verdict"] + ("" if not v[k]["failed"] else "(" + ",".join(v[k]["failed"]) + ")")
        if v[("fit", None)]["verdict"] == "達標": rec_ = "split 即可"
        elif v[("fit", "wide")]["verdict"] == "達標": rec_ = "改用 wide"
        elif v[("fit", "concept")]["verdict"] == "達標": rec_ = "改用 concept"
        elif v[("fit", None)]["verdict"] == sf.NA_DEG: rec_ = "元件退化：A1 該項 n/a（先補元件，見 warnings.json）"
        else: rec_ = "任何版面皆未達標：需調元件幾何（comps.py）後重跑 autoanim"
        out.append(f"| {n} | {f(('legacy', None))} | {f(('fit', None))} | {f(('fit', 'wide'))} | {f(('fit', 'concept'))} | {rec_} |")
    cnt = lambda k: sum(1 for r in allrows[k] if r["verdict"] == "達標")
    out += ["", f"達標數（共 {len(names)}）：legacy {cnt(('legacy', None))}；split+fit {cnt(('fit', None))}；wide+fit {cnt(('fit', 'wide'))}；concept+fit {cnt(('fit', 'concept'))}", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folders", nargs="*")
    ap.add_argument("--model", choices=["legacy", "fit", "matrix"], default="matrix")
    ap.add_argument("--as-layout", choices=["wide", "concept", "split2"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write-warnings")
    ap.add_argument("--strict-exit", action="store_true")
    a = ap.parse_args(argv)
    folders = [resolve(f) for f in a.folders] if a.folders else [Path(f) for f in default_folders()]
    folders = [f for f in folders if (f / "story.json").exists()]
    if not folders: print("沒有可用的資料夾（需含 story.json）", file=sys.stderr); return 2
    variants = ([("legacy", None), ("fit", None), ("fit", "wide"), ("fit", "concept")] if a.model == "matrix" else [(a.model, a.as_layout)])
    allrows = {}
    for model, al in variants:
        allrows[(model, al)] = [analyse(f, model, al) for f in folders]
    fc_rows = [x for x in (analyse_fullcode(f) for f in folders) if x]
    s2_rows = [x for x in (analyse_split2(f) for f in folders) if x]
    sub_rows = [subtitle_overlap(f) for f in folders]
    if a.json:
        jd = {f"{m}{'@' + al if al else ''}": [{k: v for k, v in r.items() if k != "_res"} for r in rows] for (m, al), rows in allrows.items()}
        if fc_rows: jd["fullcode"] = fc_rows
        if s2_rows: jd["split2"] = s2_rows
        jd["subtitle_overlap"] = sub_rows
        print(json.dumps(jd, ensure_ascii=False, indent=1))
    else:
        names = {("legacy", None): "現行渲染（固定 RECTS：split×0.7、wide×1.2、concept×1.45）", ("fit", None): "舞台自適應 stageFit=auto（依實際版面）",
                 ("fit", "wide"): "假設：split 場景改用 wide 版面 + stageFit=auto", ("fit", "concept"): "假設：split 場景改用 concept 版面 + stageFit=auto"}
        for k, rows in allrows.items():
            print(render(rows, names.get(k, str(k))))
        if a.model == "matrix": print(recommend(allrows))
        if fc_rows: print(render_fullcode(fc_rows))
        if s2_rows: print(render_split2(s2_rows))
        print(render_subtitle(sub_rows))
    if a.write_warnings:
        out = Path(a.write_warnings); n = 0
        for f in folders:
            story = json.loads((f / "story.json").read_text(encoding="utf-8"))
            d = out / f.name; d.mkdir(parents=True, exist_ok=True)
            if (f / "warnings.json").exists(): (d / "warnings.json").write_text((f / "warnings.json").read_text(encoding="utf-8"), encoding="utf-8")
            W = sf.merge_warnings(d, sf.fit_warnings(story, "fit", sf.load_degraded(f))); n += len(W["warnings"])
        print(f"warnings 已寫入 {out}/<樣本>/warnings.json（{len(folders)} 個樣本；原資料夾未改動）", file=sys.stderr)
    bad = sum(1 for rows in list(allrows.values())[:1] for r in rows if r["verdict"] not in ("達標", sf.NA_DEG))
    bad += sum(1 for r in fc_rows if not r["ok"]) + sum(1 for r in s2_rows if not r["ok"])
    return 1 if (a.strict_exit and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
