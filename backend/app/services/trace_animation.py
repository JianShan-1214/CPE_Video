"""Turn an LLM trace plan + real execution snapshots into renderer animation frames.

Pure functions only; running the program lives in ``app.services.trace`` and the
per-draft orchestration in ``generation_service.trace_draft``.

Snapshot values are output of the user's program: untrusted data. They become
display text only and never go back to the LLM (messages here quote the plan,
not values).

Decisions:
- ``mark`` = indices (grid: cells) whose value changed vs the previous frame,
  including newly appended ones; the first frame has none. Pointer positions
  are not marked — the pointer arrows already show them.
- The stacks renderer tracks blocks by value, so a frame with a duplicate value
  cannot animate: the whole animation switches to ``grid`` (one row per stack,
  bottom → top) with a warning.
- array / stacks cells must be number|string: bool → "true"/"false", null → "—".
"""

import difflib
import json
import re

from app.schemas import StepTrace
from app.services.trace import TraceError, TraceExpr
from app.services.trace.instrument import AFTER_MARK, _scan

# Renderer limits — keep in sync with src/animation-layout.ts.
MAX_ARRAY_VALUES = 16
MAX_STACKS = 8
MAX_STACK_HEIGHT = 12
MAX_GRID = 12
MAX_VARS = 8
MAX_CAPTION_CHARS = 40
MAX_VAR_TEXT = 24
MISSING = "—"

_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_PLACEHOLDER_BODY = re.compile(
    r"\s*([A-Za-z_]\w*)(?:\[\s*([A-Za-z_]\w*|\d+)\s*(?:([+-])\s*(\d+)\s*)?\])?\s*", re.ASCII
)
_SNAP_LINE = re.compile(r"\s*CPE_SNAP\((\d+),")


# ── plan → trace point ───────────────────────────────────────────────────────


def map_line(step_content: str, final_content: str, line: int) -> int | None:
    """Line ``line`` of a step's file → the same line in the final file (None if it was dropped).
    Lines are compared stripped, so re-indentation between steps still matches."""
    a = [text.strip() for text in step_content.splitlines()]
    b = [text.strip() for text in final_content.splitlines()]
    for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        if block.a <= line - 1 < block.a + block.size:
            return block.b + (line - 1 - block.a) + 1
    return None


def invalid_pointers(trace: StepTrace, source: str, line: int) -> list[str]:
    """Pointers that never index ``show.expr`` in the function around ``line`` of
    ``source`` (comments/strings ignored).

    An arrow under ``arr[i]`` is only honest when the code really writes
    ``arr[...i...]``; grid also accepts the 2nd index (``g[r][c]``). Queue's
    front/back are implicit, and vars has no container.
    ponytail: scope = the enclosing top-level ``{}`` block, so ``arr[i]`` in
    another function doesn't count; an index passed to a helper that does the
    indexing is rejected (move it to vars)."""
    expr = trace.show.expr
    if not expr or trace.show.as_ in ("queue", "vars"):
        return []
    codes = [info.code for info in _scan(source)]
    start = depth = 0
    for n, code in enumerate(codes):
        if depth <= 0:
            start = n
        depth += code.count("{") - code.count("}")
        if n >= line - 1 and depth <= 0:
            break
    scope = "\n".join(codes[start : n + 1])
    head = rf"\b{re.escape(expr)}\s*\[" + (r"(?:[^\]]*\]\s*\[)?" if trace.show.as_ == "grid" else "")
    return [p for p in trace.pointers if not re.search(rf"{head}[^\]]*\b{re.escape(p)}\b", scope)]


def _parse_placeholder(body: str) -> tuple[str, str | int | None, int]:
    match = _PLACEHOLDER_BODY.fullmatch(body)
    if not match:
        raise TraceError(f"說明模板的 {{{body}}} 不合法：只接受變數名稱、a[i]、a[i + 1] 這種形式")
    name, index, sign, k = match.groups()
    if index is not None and index.isdigit():
        index = int(index)
    offset = (-int(k) if sign == "-" else int(k)) if k else 0
    return name, index, offset


def plan_exprs(trace: StepTrace) -> list[TraceExpr]:
    """Expressions to snapshot for a plan, deduplicated, in display order.

    ``{a[i + 1]}`` placeholders trace ``a`` and ``i`` (never the indexed
    expression, which could read out of bounds); we index in Python."""
    show = trace.show
    exprs: dict[str, str | None] = {}

    def add(expr: str, length: str | None = None) -> None:
        exprs.setdefault(expr, length)

    if show.expr:
        add(show.expr, show.length)
    elif show.as_ != "vars":
        raise TraceError(f"show.as 為 {show.as_} 時必須指定 show.expr")
    for name in (*trace.pointers, *trace.vars):
        add(name)
    for body in _PLACEHOLDER.findall(trace.caption or ""):
        name, index, _ = _parse_placeholder(body)
        add(name, show.length if name == show.expr else None)
        if isinstance(index, str):
            add(index)
    return [{"expr": e, "length": n} if n else {"expr": e} for e, n in exprs.items()]


def map_compile_errors(instrumented: str, errors: str) -> tuple[str, list[int]]:
    """Rewrite ``main.cpp:N:`` from instrumented to original line numbers (the
    include adds 1 line, each CPE_SNAP 1 line; a CPE_SNAP line maps to the line
    it precedes, or follows when it ends with ``AFTER_MARK``). Also returns the point ids whose CPE_SNAP line has an error."""
    mapping: dict[int, tuple[int, int | None]] = {}
    original = 0
    for no, text in enumerate(instrumented.split("\n")[1:], start=2):
        snap = _SNAP_LINE.match(text)
        if snap:
            mapping[no] = (original if text.endswith(AFTER_MARK) else original + 1, int(snap.group(1)))
        else:
            original += 1
            mapping[no] = (original, None)
    ids: list[int] = []

    def sub(match: re.Match) -> str:
        if int(match.group(1)) not in mapping:
            return match.group(0)
        line, pid = mapping[int(match.group(1))]
        if pid is not None and pid not in ids:
            ids.append(pid)
        return f"main.cpp:{line}:"

    return re.sub(r"main\.cpp:(\d+):", sub, errors), ids


# ── snapshots → frames ───────────────────────────────────────────────────────


def _text(value: object) -> str:
    if value is None:
        return MISSING
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _block(value: object) -> int | float | str:
    """A value for array / stacks slots (renderer accepts number | string only)."""
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else _text(value)


def _scalar(value: object) -> bool | int | float | str | None:
    """A value for grid cells / vars (number | string | bool | null)."""
    if isinstance(value, str):
        return _clip(value, MAX_VAR_TEXT)
    return value if value is None or isinstance(value, (bool, int, float)) else _clip(_text(value), MAX_VAR_TEXT)


def _is_scalar(value: object) -> bool:
    return not isinstance(value, (list, dict))


def fill_caption(template: str, values: dict, warnings: list[str]) -> str:
    def sub(match: re.Match) -> str:
        body = match.group(1)
        name, index, offset = _parse_placeholder(body)
        value = values.get(name)
        if index is not None:
            i = index if isinstance(index, int) else values.get(index)
            if type(i) is int and isinstance(value, (list, str)) and 0 <= i + offset < len(value):
                return _text(value[i + offset])
        elif name in values:
            return _text(value)
        warnings.append(f"說明裡的 {{{body}}} 超出範圍或沒有值，顯示為「{MISSING}」")
        return MISSING

    return _clip(_PLACEHOLDER.sub(sub, template), MAX_CAPTION_CHARS)


def _sequence(data: object, expr: str, kind: str) -> list:
    if isinstance(data, str):
        data = list(data)
    if not isinstance(data, list) or not all(_is_scalar(v) for v in data):
        raise TraceError(f"{expr} 不是一維的陣列 / vector / queue，不能用 as:\"{kind}\" 顯示")
    return data


def _grid_rows(data: object, expr: str) -> list[list]:
    if isinstance(data, str):
        return [list(data)]
    if isinstance(data, list) and data and all(isinstance(v, str) for v in data):
        return [list(row) for row in data]  # vector<string> map: one char per cell
    if isinstance(data, list) and all(_is_scalar(v) for v in data):
        return [data] if data else [[]]  # a 1D container is a one-row grid
    if isinstance(data, list):
        rows = [list(r) if isinstance(r, str) else r for r in data]
        if all(isinstance(r, list) and all(_is_scalar(v) for v in r) for r in rows):
            return rows
    raise TraceError(f"{expr} 不是二維陣列（或一維陣列），不能用 as:\"grid\" 顯示")


def _stacks(data: object, expr: str) -> list[list]:
    if isinstance(data, list) and all(_is_scalar(v) for v in data):
        return [data]  # std::stack / one vector: a single pile
    if isinstance(data, list) and all(isinstance(s, list) and all(_is_scalar(v) for v in s) for s in data):
        return data  # vector<vector<>>: one pile per inner vector
    raise TraceError(f"{expr} 不是 stack 或 vector<vector<>>，不能用 as:\"stacks\" 顯示")


def _changed(prev: list | None, cur: list) -> list[int]:
    if prev is None:
        return []
    return [i for i, v in enumerate(cur) if i >= len(prev) or prev[i] != v]


def build_animation(trace: StepTrace, snapshots: list[dict], drop_pointers: list[str] = ()) -> tuple[dict, list[str]]:
    """Frames for the first ``maxFrames`` snapshots of one point.

    ``drop_pointers`` (see ``invalid_pointers``) get no arrow; a name also in
    ``vars`` stays in the table.

    Returns (animation dict in the renderer contract, warnings). Raises
    TraceError when the plan doesn't fit the data (e.g. as:"grid" on an int)."""
    warnings: list[str] = []
    if drop_pointers:
        warnings += [f"指標 {p} 從未被用來索引 {trace.show.expr}，已從箭頭移除" for p in drop_pointers]
        trace = trace.model_copy(update={"pointers": [p for p in trace.pointers if p not in drop_pointers]})
    kind, expr = trace.show.as_, trace.show.expr
    snaps = snapshots[: trace.maxFrames]
    if len(trace.vars) > MAX_VARS:
        warnings.append(f"vars 最多顯示 {MAX_VARS} 個，只保留前 {MAX_VARS} 個")
    if kind == "vars" and not trace.vars:
        raise TraceError('show.as 為 "vars" 時 vars 不能是空的')

    mains: list = []
    for snap in snaps:
        values = snap["values"]
        if kind == "vars":
            mains.append(None)
            continue
        if expr not in values:
            raise TraceError(f"追蹤結果裡沒有 {expr}")
        if expr in snap.get("truncated", ()):
            warnings.append(f"{expr} 超過 64 個元素，只記錄了前 64 個")
        data = values[expr]
        if kind in ("array", "queue"):
            seq = _sequence(data, expr, kind)
            if len(seq) > MAX_ARRAY_VALUES:
                warnings.append(f"{expr} 超過 {MAX_ARRAY_VALUES} 個元素，只顯示前 {MAX_ARRAY_VALUES} 個")
            mains.append([_block(v) for v in seq[:MAX_ARRAY_VALUES]])
        elif kind == "stacks":
            piles = _stacks(data, expr)
            if len(piles) > MAX_STACKS or any(len(p) > MAX_STACK_HEIGHT for p in piles):
                warnings.append(f"{expr} 超過 {MAX_STACKS} 堆或單堆超過 {MAX_STACK_HEIGHT} 個，只顯示前 {MAX_STACKS} 堆、每堆最上面 {MAX_STACK_HEIGHT} 個")
            mains.append([[_block(v) for v in p[-MAX_STACK_HEIGHT:]] for p in piles[:MAX_STACKS]])
        else:  # grid
            rows = _grid_rows(data, expr)
            if len(rows) > MAX_GRID or any(len(r) > MAX_GRID for r in rows):
                warnings.append(f"{expr} 超過 {MAX_GRID}×{MAX_GRID}，只顯示左上角 {MAX_GRID}×{MAX_GRID}")
            mains.append([[_scalar(v) for v in r[:MAX_GRID]] for r in rows[:MAX_GRID]])

    if kind == "stacks":
        for piles in mains:
            blocks = [str(b) for p in piles for b in p]
            if len(set(blocks)) != len(blocks):
                warnings.append(f"{expr} 有重複的值，stack 動畫無法追蹤每一塊，改用表格（grid）顯示")
                kind = "grid"
                break

    frames: list[dict] = []
    prev = None
    for snap, main in zip(snaps, mains):
        values = snap["values"]
        frame: dict = {}
        if kind in ("array", "queue"):
            frame["values"] = main
            if kind == "queue":
                pointers = {"front": 0, "back": len(main) - 1} if main else {}
            else:
                pointers = {p: v for p in trace.pointers if type(v := values.get(p)) is int and 0 <= v < len(main)}
            if pointers:
                frame["pointers"] = pointers
            if mark := _changed(prev, main):
                frame["mark"] = mark
        elif kind == "stacks":
            frame["stacks"] = main
        elif kind == "grid":
            frame["cells"] = main
            if prev is not None:
                mark = [[r, c] for r, row in enumerate(main) for c in _changed(prev[r] if r < len(prev) else [], row)]
                if mark:
                    frame["mark"] = mark
        prev = main
        table = {name: _scalar(values.get(name)) for name in trace.vars[:MAX_VARS]}
        if table:
            frame["vars"] = table
        if trace.caption:
            frame["caption"] = fill_caption(trace.caption, values, warnings)
        frames.append(frame)

    return {"type": "array" if kind == "queue" else kind, "frames": frames}, list(dict.fromkeys(warnings))
