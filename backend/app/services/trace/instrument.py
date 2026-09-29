"""Insert CPE_SNAP(...) lines into a C++ source at LLM-chosen points.

Everything here is a trust boundary: points come from an LLM plan. Expressions
are whitelisted by a full-match regex so no code can be smuggled in, and the
insertion position is checked by a lightweight scanner (comments, strings,
braces, parens) so a snapshot never lands in the middle of a statement.
"""

import re
from typing import Literal, NotRequired, TypedDict

HEADER_INCLUDE = '#include "cpe_trace.hpp"'
AFTER_MARK = "  // cpe:after"
MAX_POINTS = 64
MAX_EXPRS_PER_POINT = 16


class TraceError(Exception):
    """A trace request that cannot be executed; the message is shown to the LLM/user."""


class TraceExpr(TypedDict):
    expr: str
    length: NotRequired[str | None]  # only for C arrays -> CPE_ARR(expr, length)


class TracePoint(TypedDict):
    id: int
    line: int  # 1-based line in the ORIGINAL source
    exprs: list[TraceExpr]
    when: NotRequired[Literal["before", "after"]]  # snapshot runs before (default) / after that line


_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_INDEX = rf"(?:{_IDENT}|[0-9]+|{_IDENT} ?[+-] ?[0-9]+)"
_EXPR_RE = re.compile(rf"{_IDENT}(?:\[{_INDEX}\]){{0,2}}", re.ASCII)
_LENGTH_RE = re.compile(rf"{_IDENT}|[0-9]+", re.ASCII)
_BLOCK_WORDS = {"else", "do", "try", "const", "noexcept", "mutable", "override"}


class _Line:
    __slots__ = ("after_do", "code", "in_block", "in_comment", "parens")

    def __init__(self) -> None:
        self.code = ""  # the line with comments/string contents blanked out
        self.in_block = False  # innermost enclosing `{` is a statement block
        self.parens = 0  # unclosed ( / [ inside that block at line start
        self.after_do = False  # last token before the line closed a `do { }`
        self.in_comment = False  # the line starts inside a /* block comment */


def _scan(source: str) -> list[_Line]:
    """Per-line lexical state. ponytail: no raw-string / trigraph support; the
    compile + equivalence run catches what this heuristic misses."""
    lines: list[_Line] = []
    stack: list[tuple[bool, int, str]] = []  # (is_block, saved parens, opener token)
    parens = 0
    prev_tok = ""  # last significant token: an identifier/number or one punctuation char
    closed_do = False
    word = ""
    state = "code"  # code | line_comment | block_comment | str | chr | pp

    def emit(tok: str) -> None:
        nonlocal prev_tok, parens, closed_do
        is_close = tok == "}"
        if tok == "{":
            if prev_tok == "{":
                is_block = bool(stack) and stack[-1][0]
            else:
                is_block = prev_tok in (")", "}", ";", ":") or prev_tok in _BLOCK_WORDS
            stack.append((is_block, parens, prev_tok))
            parens = 0
        elif is_close:
            opener = ""
            if stack:
                _, parens, opener = stack.pop()
            closed_do = opener == "do"
        elif tok in ("(", "["):
            parens += 1
        elif tok in (")", "]"):
            parens = max(parens - 1, 0)
        if not is_close:
            closed_do = False
        prev_tok = tok

    for raw in source.split("\n"):
        info = _Line()
        info.in_block = bool(stack) and stack[-1][0]
        info.parens = parens
        info.after_do = closed_do
        info.in_comment = state == "block_comment"
        if state in ("line_comment", "str", "chr"):
            state = "code"  # these never span lines (ignoring `\` continuations)
        if state == "code" and raw.lstrip().startswith("#"):
            state = "pp"
        code: list[str] = []
        i = 0
        while i < len(raw):
            c = raw[i]
            nxt = raw[i + 1] if i + 1 < len(raw) else ""
            if state in ("pp", "line_comment"):
                code.append(" ")
            elif state == "block_comment":
                code.append(" ")
                if c == "*" and nxt == "/":
                    state = "code"
                    code.append(" ")
                    i += 1
            elif state in ("str", "chr"):
                if c == "\\":
                    code.append("  ")
                    i += 1
                elif c == ('"' if state == "str" else "'"):
                    code.append(c)
                    state = "code"
                    emit(c)
                else:
                    code.append(" ")
            elif c.isalnum() or c == "_":
                code.append(c)
                word += c
            else:
                if word:
                    emit(word)
                    word = ""
                if c == "/" and nxt in "/*" and nxt:
                    state = "line_comment" if nxt == "/" else "block_comment"
                    code.append("  ")
                    i += 1
                else:
                    code.append(c)
                    if c in "\"'":
                        state = "str" if c == '"' else "chr"
                    elif not c.isspace():
                        emit(c)
            i += 1
        if word:
            emit(word)
            word = ""
        if state == "pp" and not raw.rstrip().endswith("\\"):
            state = "code"
        info.code = "".join(code).strip()
        lines.append(info)
    return lines


def _check_expr(expr: object, what: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(expr, str) or not pattern.fullmatch(expr):
        raise TraceError(
            f"{what} {expr!r} 不合法：只接受變數名稱、a[i]、a[i][j]"
            "（索引可為變數、整數或「變數±整數」），不能有函式呼叫、指標、成員存取或其他符號"
        )
    return expr


def _check_position(lines: list[_Line], line_no: int) -> None:
    info = lines[line_no - 1]
    where = f"第 {line_no} 行前面不能插入追蹤點："
    code = info.code
    if not code:
        raise TraceError(where + "這一行是空白、註解或 # 前置處理指令，請改選下一個有程式碼的行")
    if re.match(r"(\}\s*)?(else|catch)\b", code):
        raise TraceError(where + "這一行以 else / catch 開頭，插入會拆散 if/else 或 try/catch")
    if re.match(r"(case\b|default\s*:)", code):
        raise TraceError(where + "這一行是 switch 的 case 標籤，跳到這裡時不會經過追蹤點")
    if info.after_do and code.startswith("while"):
        raise TraceError(where + "這一行是 do { } while 的結尾條件")
    if not info.in_block:
        raise TraceError(where + "這一行不在函式本體內（全域、struct/class 或初始化串列中）")
    if info.parens:
        raise TraceError(where + "這一行在一個跨行的敘述中間（前面的括號還沒閉合）")
    prev = next((l.code for l in reversed(lines[: line_no - 1]) if l.code), "")
    if prev and prev[-1] not in ";{}":
        raise TraceError(
            f"{where}上一行 `{prev[-60:]}` 不是完整敘述（不是以 ; {{ }} 結尾），"
            "可能是沒有大括號的 for/if 本體或跨行敘述，請改選別的行"
        )


def _check_after(lines: list[_Line], line_no: int) -> None:
    """A snapshot on a new line right after ``line_no``: the lexical state there is
    the state at the start of the next line."""
    code = lines[line_no - 1].code
    where = f"第 {line_no} 行後面不能插入追蹤點："
    if not code:
        raise TraceError(where + "這一行是空白、註解或 # 前置處理指令，請改選有程式碼的行")
    if code[-1] not in ";}":
        raise TraceError(
            where + "這一行不是以 ; 或 } 結尾（不是一個敘述的最後一行），請改選敘述的最後一行，或改用 when=\"before\""
        )
    nxt = lines[line_no] if line_no < len(lines) else None
    if nxt is None or not nxt.in_block:
        raise TraceError(where + "這一行後面不在函式本體內（函式、struct/class 或初始化串列已經結束）")
    if nxt.in_comment:
        raise TraceError(where + "這一行結尾的 /* 區塊註解還沒結束")
    if nxt.parens:
        raise TraceError(where + "這一行在一個跨行的敘述中間（前面的括號還沒閉合）")
    after = next((l for l in lines[line_no:] if l.code), None)
    if after is None:
        return
    if re.match(r"else\b", after.code):
        raise TraceError(
            where + "下一個有程式碼的行以 else 開頭，插在這裡會拆散 if/else。"
            "要看整個 if/else 執行後的狀態，請改選 else 分支的最後一行並用 when=\"after\""
        )
    if re.match(r"catch\b", after.code):
        raise TraceError(where + "下一個有程式碼的行以 catch 開頭，插在這裡會拆散 try/catch")
    if after.after_do and after.code.startswith("while"):
        raise TraceError(where + "下一個有程式碼的行是 do { } while 的結尾條件，請改選 while 那一行並用 when=\"after\"")
    # ponytail: a braceless `do stmt; while (...)` slips through; the compile step reports it.


def instrument(source: str, points: list[TracePoint]) -> str:
    """Return ``source`` with the trace header included and one CPE_SNAP line
    inserted immediately before (or, with ``when="after"``, after) each point's
    line. After-lines end with ``AFTER_MARK`` so compile errors map back to the
    right line. Raises TraceError."""
    if not isinstance(points, list) or not points:
        raise TraceError("至少要有一個追蹤點")
    if len(points) > MAX_POINTS:
        raise TraceError(f"追蹤點最多 {MAX_POINTS} 個")
    lines = _scan(source)
    raw_lines = source.split("\n")
    before: dict[int, list[str]] = {}
    after: dict[int, list[str]] = {}
    seen_ids: set[int] = set()
    for point in points:
        try:
            pid, line_no, exprs = point["id"], point["line"], point["exprs"]
        except (KeyError, TypeError) as exc:
            raise TraceError(f"追蹤點格式錯誤，需要 id、line、exprs：{point!r}") from exc
        if type(pid) is not int or not 0 <= pid < 2**31:
            raise TraceError(f"追蹤點 id 必須是非負整數：{pid!r}")
        if pid in seen_ids:
            raise TraceError(f"追蹤點 id {pid} 重複")
        seen_ids.add(pid)
        if type(line_no) is not int or not 1 <= line_no <= len(raw_lines):
            raise TraceError(f"追蹤點 {pid} 的行號 {line_no!r} 超出範圍（1–{len(raw_lines)}）")
        if not isinstance(exprs, list) or not 1 <= len(exprs) <= MAX_EXPRS_PER_POINT:
            raise TraceError(f"追蹤點 {pid} 需要 1–{MAX_EXPRS_PER_POINT} 個運算式")
        when = point.get("when", "before")
        if when == "before":
            _check_position(lines, line_no)
        elif when == "after":
            _check_after(lines, line_no)
        else:
            raise TraceError(f"追蹤點 {pid} 的 when 必須是 \"before\" 或 \"after\"：{when!r}")

        args: list[str] = []
        names: set[str] = set()
        for item in exprs:
            if not isinstance(item, dict):
                raise TraceError(f"追蹤點 {pid} 的運算式格式錯誤：{item!r}")
            expr = _check_expr(item.get("expr"), "運算式", _EXPR_RE)
            if expr in names:
                raise TraceError(f"追蹤點 {pid} 的運算式 {expr} 重複")
            names.add(expr)
            length = item.get("length")
            if length is None:
                args.append(expr)
            else:
                length = _check_expr(length, "陣列長度", _LENGTH_RE)
                args.append(f"CPE_ARR({expr}, {length})")
        indent = re.match(r"[ \t]*", raw_lines[line_no - 1]).group(0)
        snap = f"{indent}CPE_SNAP({pid}, {', '.join(args)});"
        if when == "before":
            before.setdefault(line_no, []).append(snap)
        else:
            after.setdefault(line_no, []).append(snap + AFTER_MARK)

    out = [HEADER_INCLUDE]
    for no, text in enumerate(raw_lines, start=1):
        out.extend(before.get(no, ()))
        out.append(text)
        out.extend(after.get(no, ()))
    return "\n".join(out)
