"""AI draft generation.

Two providers share one async interface:

- ``MockGeneratorProvider`` — deterministic, offline, used when no OpenAI key
  is configured (and in tests).
- ``OpenAIGeneratorProvider`` — calls OpenAI to produce a tutorial draft that
  follows the project's four-section script structure (see ``skill.md``).

``build_generation_provider(settings)`` picks the right one at app startup.
"""

import base64
from dataclasses import dataclass
import json
import logging
import math
from pathlib import Path
import re
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from app.schemas import ArrayAnimation, DraftStep, HighlightPreset, StacksAnimation
from app.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedDraft:
    job_name: str
    steps: list[DraftStep]


class GeneratorProvider(Protocol):
    async def generate(
        self, name: str | None, problem_statement: str, solution_code: str, with_animation: bool = False
    ) -> GeneratedDraft: ...

    async def summarize_problem(self, pdf: bytes, problem_id: int) -> str: ...

    async def review_draft(self, steps: list[DraftStep]) -> list["DraftIssue"]: ...


# ── shared helpers ───────────────────────────────────────────────────────────


def _ensure_trailing_newline(value: str) -> str:
    return value if value.endswith("\n") else f"{value}\n"


def _normalize_text(value: str) -> str:
    return value.strip() or "使用者尚未提供題目內容。"


def _normalize_code(value: str) -> str:
    return _ensure_trailing_newline(value.strip() or "// TODO: paste the final C++ answer here")


def estimate_duration_seconds(subtitle: str) -> float:
    """Rough silent-preview length for a step.

    Mandarin TTS reads ~4.2 chars/sec; floor at 5s. Audio, when present, is
    measured at render time and extends the step further if needed.
    """
    chars = len(subtitle.strip())
    return round(max(5.0, chars / 4.2), 1)


# ── Mock provider ────────────────────────────────────────────────────────────


class MockGeneratorProvider:
    async def generate(
        self, name: str | None, problem_statement: str, solution_code: str, with_animation: bool = False
    ) -> GeneratedDraft:
        problem = _normalize_text(problem_statement)
        code = _normalize_code(solution_code)
        job_name = name.strip() if name and name.strip() else "GPT Mock Draft"
        problem_comment = _problem_comment(problem)
        code_lines = code.rstrip().split("\n")
        # Never more code steps than lines, so every code step adds at least one line.
        middle_count = min(5, len(code_lines), max(3, math.ceil(len(code_lines) / 6)))
        # Code steps are cumulative on top of step 1's comment block.
        offset = len(problem_comment.splitlines())
        steps: list[DraftStep] = [
            DraftStep(
                label="題目說明",
                from_=0,
                to=7,
                fileLabel="code01.cpp",
                fileContent=problem_comment,
                subtitle=f"這題的重點是：{_shorten(problem, 56)}",
                highlight={
                    "startLine": 1,
                    "endLine": len(problem_comment.rstrip().split("\n")),
                    "color": "blue",
                },
            ),
            DraftStep(
                label="解法說明",
                from_=7,
                to=15,
                fileLabel="code01.cpp",
                fileContent=problem_comment,
                subtitle="解法先假裝由 GPT 分析完成：我們會依照題意拆解輸入、核心處理與輸出，再逐段建立完整 C++ 程式。",
            ),
        ]

        for index in range(1, middle_count + 1):
            end = max(1, math.ceil((len(code_lines) * index) / middle_count))
            start = max(1, math.ceil((len(code_lines) * (index - 1)) / middle_count) + 1)
            previous_to = steps[-1].to
            steps.append(
                DraftStep(
                    label=_code_step_label(index, middle_count),
                    from_=previous_to,
                    to=previous_to + 7,
                    fileLabel=f"code{index + 1:02d}.cpp",
                    # Keep trailing blank lines so the file really has `end` lines.
                    fileContent=problem_comment + "\n".join(code_lines[:end]) + "\n",
                    subtitle=_code_step_subtitle(index, middle_count),
                    highlight={
                        "startLine": offset + start,
                        "endLine": offset + end,
                        "color": _highlight_color(index, middle_count),
                    },
                ),
            )

        previous_to = steps[-1].to
        steps.append(
            DraftStep(
                label="結尾",
                from_=previous_to,
                to=previous_to + 9,
                fileLabel=f"code{middle_count + 2:02d}.cpp",
                fileContent=problem_comment + code,
                subtitle="總結一下：這份草稿已經把題目、解法思路與完整程式串成影片步驟。接下來可以在編輯器微調字幕、高亮與標注，再匯出成可 render 的檔案。",
                focusLine=offset + 1,
            ),
        )
        return GeneratedDraft(job_name=job_name, steps=steps)

    async def summarize_problem(self, pdf: bytes, problem_id: int) -> str:
        return f"UVa {problem_id}（Mock 題目摘要）\n題意：這是離線模式產生的佔位題目說明，PDF 大小 {len(pdf)} bytes。"

    async def review_draft(self, steps: list[DraftStep]) -> list["DraftIssue"]:
        # Without this, ``ai=true`` looks exactly like "AI found nothing".
        return [DraftIssue(None, "warning", "未設定 OpenAI API key，已略過 AI 審稿")]


def _problem_comment(problem_statement: str) -> str:
    lines = [f" * {line}" for line in problem_statement.split("\n")]
    return "\n".join(["/*", *lines, " */", ""])


def _shorten(value: str, max_length: int) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= max_length else f"{compact[:max_length - 1]}…"


def _code_step_label(index: int, total: int) -> str:
    if index == 1:
        return "建立程式骨架"
    if index == total:
        return "完成完整程式"
    return f"程式碼講解 {index}"


def _code_step_subtitle(index: int, total: int) -> str:
    if index == 1:
        return "接下來先放入程式的前段內容，建立標頭、變數或主要函式骨架，讓後續邏輯有清楚的起點。"
    if index == total:
        return "最後補上剩餘程式碼，讓整份 C++ 答案成為可以編譯執行的完整版本。"
    return "這一段延續前面的程式碼，逐步補上核心處理邏輯，讓觀眾能跟著理解每個區塊的用途。"


def _highlight_color(index: int, total: int) -> str:
    if index == 1:
        return "lightblue"
    if index == total:
        return "green"
    return "yellow" if index % 2 == 0 else "blue"


# ── OpenAI provider ──────────────────────────────────────────────────────────


class _AIHighlight(BaseModel):
    startLine: int = Field(ge=1)
    endLine: int = Field(ge=1)
    color: HighlightPreset


# Strict structured outputs reject dicts (additionalProperties), so pointers
# are a list of {name, index} here and become a dict in ``build_draft_from_ai``.
class _AIPointer(BaseModel):
    name: str
    index: int


class _AIArrayFrame(BaseModel):
    values: list[int | float | str]
    pointers: list[_AIPointer] | None = None
    mark: list[int] | None = None
    caption: str | None = None


class _AIArrayAnimation(BaseModel):
    type: Literal["array"]
    frames: list[_AIArrayFrame]


class _AIStacksFrame(BaseModel):
    stacks: list[list[int | float | str]]
    caption: str | None = None


class _AIStacksAnimation(BaseModel):
    type: Literal["stacks"]
    labels: list[str] | None = None
    frames: list[_AIStacksFrame]


class _AIStep(BaseModel):
    label: str
    fileLabel: str
    fileContent: str
    subtitle: str
    highlight: _AIHighlight | None = None
    focusLine: int | None = Field(default=None, ge=1)
    # Plain union (no discriminator): strict mode allows anyOf but not oneOf.
    animation: _AIArrayAnimation | _AIStacksAnimation | None = None


class _AIDraft(BaseModel):
    jobName: str
    steps: list[_AIStep]


SYSTEM_PROMPT = """\
你是「CPE Video」教學影片的腳本切片助理。使用者會給你一道程式題目與完整的 C++ 解答，
你要把它切成一支教學影片的逐步腳本，並只回傳一個 JSON 物件（不要包任何說明文字或 markdown 圍欄）。

# 四段式結構（必備）
標準結構為「題目 → 解法 → 程式碼逐步講解 → 結尾」：

1. 第 1 步「題目說明」(fileLabel = "code01.cpp")：
   - fileContent 只放題目說明的「註解區塊」，不含任何可執行程式碼（連 main() 都不放）。
     例如：
     /*
      * 題目重點...
      */
   - highlight 指向註解行範圍，color 用 "blue"。

2. 第 2 步「解法說明」(fileLabel 仍為 "code01.cpp")：
   - fileContent 與第 1 步相同（同一段註解）。
   - 不要 highlight（highlight 設為 null）。
   - subtitle 用「解法很單純：」「核心想法是」等開頭，交代演算法策略（枚舉什麼／驗證什麼／為什麼可行），80–100 字。

3. 中間步驟 (fileLabel = "code02.cpp"、"code03.cpp" …)：
   - 每步新增 1–12 行程式碼，採「累加式」：codeNN.cpp 的 fileContent 必須包含前面所有步驟的程式碼，再加上這一步的新行（不是只有新增片段）。
   - 已經出現過的行不可以再修改或重新縮排；每一行一出現就必須是最終解答裡的樣子，講解才不會和程式碼不一致。
   - highlight.startLine / endLine 指向「這一步新增的行範圍」（1-indexed，以該步累加後的檔案計算）。
   - highlight.color 依性質選：blue=一般宣告、yellow=迴圈/流程、red=條件判斷、green=輸出/關鍵操作、lightblue=函式宣告；一步有多種性質時取主要操作的顏色。

4. 最後一步「結尾」(fileLabel 用最後一個完整檔，例 "code09.cpp")：
   - fileContent 是完整的 C++ 程式（與前一步的累加結果相同或就是完整解答）。
   - 不要 highlight（highlight 設為 null）。
   - focusLine 設為 main 函式起點（通常是 #include 之後那一行）。
   - subtitle 用「總結一下：」開頭，重述演算法核心、視情況帶複雜度評估，最後以「感謝收看」收尾，80–100 字。

# 規則
- 合理步數通常 8–15 步（含題目、解法、結尾三個結構性步驟），依程式長度調整。
- 累加式 cpp：每個 codeNN.cpp 包含所有先前步驟的程式碼，保留原始縮排與格式。
- 結構性步驟（解法說明、結尾）省略 highlight。
- subtitle 為引導式旁白，以「接下來」「這裡」「我們」等開頭，說明「做什麼」與「為什麼」，一般步驟 30–80 字。
- label 是時間軸上的簡短標題。
- 全部文字使用繁體中文。
- 最後一步的 fileContent 去掉註解後，必須與使用者提供的完整解答逐行一致。

# 欄位說明
- jobName：影片名稱。
- 每個 step 都要有 label / fileLabel / fileContent / subtitle；highlight 與 focusLine 不需要時設為 null。
- fileContent 是該步驟完整的 cpp 檔內容（累加後），以換行字元分行。
- animation：除非下方另有「演算法動畫」指示，一律設為 null。
"""

ANIMATION_PROMPT = """
# 演算法動畫（選用）
畫面右側可以顯示一段資料變化的動畫。只在「看到資料怎麼變」真的能幫助理解「這一步新增的程式碼」時才加
animation（例如走訪陣列的迴圈、交換、stack/queue 的 push/pop、枚舉），其餘步驟一律設為 null。
題目說明、解法說明、結尾這三步不加動畫。

- 用很小的具體範例資料，盡量取自題目的範例輸入。
- 每一格（frame）都必須是這段程式碼實際執行時會發生的狀態，不可以虛構程式沒做的事。
- 兩種型態：
  - {"type": "array", "frames": [{"values": [...], "pointers": [{"name": "i", "index": 0}], "mark": [0], "caption": "..."}]}
    pointers 的 name 用程式碼裡的變數名稱，index 是 values 內的 0 起算位置；mark 是要標亮的位置；不需要時設為 null。
  - {"type": "stacks", "labels": ["A", "B"], "frames": [{"stacks": [[1, 2], [3]], "caption": "..."}]}
    每個 stack 由下而上列出 block；同一格內 block 不可重複。
- 限制：values 最多 12 個、最多 8 格、caption 最多 30 字（繁體中文，說明這一格發生什麼）。
"""

# Finished video under ``public/`` used as the few-shot reference example.
EXAMPLE_FOLDER = "26D4_false_coin"
EXAMPLE_INTRO = "以下是一支已完成影片的參考範例。請模仿它的風格、步數切分方式與字幕語氣，不要沿用它的內容。"


# ── draft validation ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DraftIssue:
    step_index: int | None  # 0-based; None = whole draft
    level: Literal["error", "warning"]
    message: str


def _added_line_numbers(previous: str, current: str) -> list[int]:
    """1-indexed non-blank lines of ``current`` inside the region changed vs ``previous``.

    Trims the common prefix first, then the common suffix, so an insertion
    next to an identical line (a new function after another one's ``}``) is
    placed at the earliest position. Two separate edits yield the span
    between them — fine, callers only use min..max.
    """
    old = [line.rstrip() for line in previous.splitlines()]
    new = [line.rstrip() for line in current.splitlines()]
    start = 0
    while start < min(len(old), len(new)) and old[start] == new[start]:
        start += 1
    old_end, new_end = len(old), len(new)
    while old_end > start and new_end > start and old[old_end - 1] == new[new_end - 1]:
        old_end -= 1
        new_end -= 1
    return [j + 1 for j in range(start, new_end) if new[j].strip()]


def _non_blank(content: str) -> list[str]:
    return [line.rstrip().expandtabs(4) for line in content.splitlines() if line.strip()]


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    it = iter(haystack)
    return all(line in it for line in needle)


def validate_draft(steps: list[DraftStep], solution_code: str | None) -> list[DraftIssue]:
    """Check a draft against the script rules in ``skill.md``.

    ``solution_code=None`` (the editor keeps no pasted solution) skips the
    last-step-equals-solution rule.

    ``error`` issues break the video (and trigger an AI retry); ``warning``
    issues are style hints for the editor.
    """
    issues: list[DraftIssue] = []
    if not steps:
        return issues
    last = len(steps) - 1

    for index, step in enumerate(steps):
        n = index + 1
        line_count = len(step.fileContent.splitlines())

        cumulative_ok = index == 0 or _is_subsequence(_non_blank(steps[index - 1].fileContent), _non_blank(step.fileContent))
        if not cumulative_ok:
            issues.append(DraftIssue(index, "error", f"第 {n} 步不是累加式：沒有完整保留第 {n - 1} 步的程式碼（順序須一致）。"))

        if step.focusLine is not None and not 1 <= step.focusLine <= line_count:
            issues.append(DraftIssue(index, "error", f"第 {n} 步的 focusLine={step.focusLine} 超出檔案範圍 1–{line_count}。"))

        if step.highlight is not None:
            start, end = step.highlight.startLine, step.highlight.endLine
            if not (1 <= start <= end <= line_count):
                issues.append(
                    DraftIssue(index, "error", f"第 {n} 步的 highlight {start}–{end} 無效（檔案共 {line_count} 行，且起始行不能大於結束行）。"),
                )

        if 2 <= index <= last - 1 and cumulative_ok:  # a line count diff is meaningless once lines were dropped
            added = len(_non_blank(step.fileContent)) - len(_non_blank(steps[index - 1].fileContent))
            if not 1 <= added <= 12:
                issues.append(DraftIssue(index, "warning", f"第 {n} 步新增了 {added} 行程式碼，建議每步新增 1–12 行。"))

        max_chars = 100 if index in (0, 1, last) else 80
        chars = len(step.subtitle.strip())
        if not 30 <= chars <= max_chars:
            issues.append(DraftIssue(index, "warning", f"第 {n} 步字幕有 {chars} 字，建議 30–{max_chars} 字。"))

        if step.animation is not None:
            issues += _animation_issues(index, step)

    # The last file = step 1's problem comment block + the pasted solution.
    if solution_code is not None and _non_blank(steps[last].fileContent) != _non_blank(steps[0].fileContent) + _non_blank(solution_code):
        issues.append(
            DraftIssue(last, "error", f"最後一步（第 {last + 1} 步）的內容必須等於「第 1 步的題目註解」加上使用者提供的完整解答（忽略空行後逐行比對）。"),
        )

    return issues


# Renderer limits — keep in sync with src/animation-layout.ts.
MAX_ARRAY_VALUES = 16
MAX_STACKS = 8
MAX_STACK_HEIGHT = 12
MAX_CAPTION_CHARS = 40


def _animation_issues(index: int, step: DraftStep) -> list[DraftIssue]:
    """Errors = the renderer would drop the whole animation; warnings = it plays but may mislead."""
    n = index + 1
    anim = step.animation
    errors: list[str] = []
    warnings: list[str] = []
    if not anim.frames:
        errors.append("沒有任何 frame")
    if isinstance(anim, StacksAnimation) and anim.labels is not None and len(anim.labels) > MAX_STACKS:
        errors.append(f"labels 有 {len(anim.labels)} 個，上限 {MAX_STACKS}")
    for f, frame in enumerate(anim.frames, 1):
        if isinstance(anim, ArrayAnimation):
            size = len(frame.values)
            if size > MAX_ARRAY_VALUES:
                errors.append(f"第 {f} 格有 {size} 個值，上限 {MAX_ARRAY_VALUES}")
            for name, i in (frame.pointers or {}).items():
                if not 0 <= i < size:
                    warnings.append(f"第 {f} 格的指標 {name}={i} 超出範圍 0–{size - 1}")
            for i in frame.mark or []:
                if not 0 <= i < size:
                    warnings.append(f"第 {f} 格的 mark {i} 超出範圍 0–{size - 1}")
        else:
            if len(frame.stacks) > MAX_STACKS:
                errors.append(f"第 {f} 格有 {len(frame.stacks)} 個 stack，上限 {MAX_STACKS}")
            if any(len(stack) > MAX_STACK_HEIGHT for stack in frame.stacks):
                errors.append(f"第 {f} 格有 stack 超過 {MAX_STACK_HEIGHT} 個 block")
            # Match JS String(): 1.0 → "1", so [[1], [1.0]] is a duplicate there too.
            blocks = [str(int(b)) if isinstance(b, float) and b.is_integer() else str(b) for stack in frame.stacks for b in stack]
            if len(set(blocks)) != len(blocks):
                # The renderer can't tell which block moved, so it drops the animation.
                errors.append(f"第 {f} 格有重複的 block id")
        if frame.caption is not None and len(frame.caption) > MAX_CAPTION_CHARS:
            warnings.append(f"第 {f} 格說明有 {len(frame.caption)} 字，建議 ≤ {MAX_CAPTION_CHARS} 字")
    if isinstance(anim, ArrayAnimation):
        names = dict.fromkeys(name for frame in anim.frames for name in (frame.pointers or {}))
        for name in names:
            if not re.search(rf"(?<!\w){re.escape(name)}(?!\w)", step.fileContent):
                warnings.append(f"指標 {name} 沒有出現在這一步的程式碼裡")
    return [DraftIssue(index, "error", f"第 {n} 步的動畫無法播放：{e}。") for e in errors] + [
        DraftIssue(index, "warning", f"第 {n} 步的動畫：{w}。") for w in warnings
    ]


# ── AI → draft ───────────────────────────────────────────────────────────────


def _animation_from_ai(anim: _AIArrayAnimation | _AIStacksAnimation | None) -> dict | None:
    if anim is None:
        return None
    data = anim.model_dump()
    if isinstance(anim, _AIArrayAnimation):
        for frame, ai_frame in zip(data["frames"], anim.frames):
            frame["pointers"] = {p.name: p.index for p in ai_frame.pointers} if ai_frame.pointers else None
    return data


def build_draft_from_ai(ai: _AIDraft, fallback_name: str, with_animation: bool = False) -> GeneratedDraft:
    """Convert the model output into ``DraftStep``s.

    Highlight ranges are recomputed from the diff against the previous step —
    the model's own line numbers are unreliable. Its color (and a null
    highlight) is kept. Animations are dropped unless ``with_animation``.
    """
    job_name = ai.jobName.strip() or fallback_name
    steps: list[DraftStep] = []
    cursor = 0.0
    previous_content = ""
    for ai_step in ai.steps:
        duration = estimate_duration_seconds(ai_step.subtitle)
        file_content = _ensure_trailing_newline(ai_step.fileContent)
        highlight = ai_step.highlight.model_dump() if ai_step.highlight else None
        if highlight:
            added = _added_line_numbers(previous_content, file_content)
            if added:
                highlight["startLine"], highlight["endLine"] = min(added), max(added)
        previous_content = file_content
        steps.append(
            DraftStep(
                label=ai_step.label,
                from_=round(cursor, 1),
                to=round(cursor + duration, 1),
                fileLabel=ai_step.fileLabel,
                fileContent=file_content,
                subtitle=ai_step.subtitle,
                focusLine=ai_step.focusLine,
                highlight=highlight,
                animation=_animation_from_ai(ai_step.animation) if with_animation else None,
            ),
        )
        cursor += duration
    return GeneratedDraft(job_name=job_name, steps=steps)


def _user_prompt(problem: str, code: str, name: str) -> str:
    return (
        f"題目說明：\n{problem}\n\n"
        f"完整 C++ 解答：\n{code}\n\n"
        f"影片名稱（若空白請自訂一個簡短名稱）：{name}"
    )


def load_example_messages(folder: Path) -> list[dict[str, str]]:
    """Turn a finished video in ``public/<folder>`` into a few-shot user/assistant pair.

    The problem statement is ``code01.cpp`` (the comment block); the solution is
    the last step's file with that block removed — matching what users paste.
    Returns ``[]`` when the folder is missing or unreadable.
    """
    try:
        config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        files = {s["file"]: (folder / s["file"]).read_text(encoding="utf-8") for s in config["steps"]}
        steps = config["steps"]
        problem = files[steps[0]["file"]]
        solution = files[steps[-1]["file"]].removeprefix(problem)
        draft = _AIDraft(
            jobName=folder.name,
            steps=[
                _AIStep(
                    label=s["label"],
                    fileLabel=s["file"],
                    fileContent=files[s["file"]],
                    subtitle=s["subtitle"],
                    highlight=s.get("highlight"),
                    focusLine=s.get("focusLine"),
                )
                for s in steps
            ],
        )
    except (OSError, ValueError, KeyError, TypeError, IndexError):  # ValidationError is a ValueError
        return []
    return [
        {"role": "user", "content": f"{EXAMPLE_INTRO}\n\n{_user_prompt(problem.strip(), solution.strip(), folder.name)}"},
        {"role": "assistant", "content": draft.model_dump_json()},
    ]


class OpenAIGeneratorProvider:
    MAX_ATTEMPTS = 3

    def __init__(self, api_key: str, model: str, example_dir: Path | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._example_messages = load_example_messages(example_dir) if example_dir else []

    async def generate(
        self, name: str | None, problem_statement: str, solution_code: str, with_animation: bool = False
    ) -> GeneratedDraft:
        from openai import AsyncOpenAI

        problem = _normalize_text(problem_statement)
        code = _normalize_code(solution_code)
        fallback_name = name.strip() if name and name.strip() else "AI 生成草稿"

        # A full draft is a long completion: generous timeout, but no 600s × 3 hang.
        client = AsyncOpenAI(api_key=self._api_key, timeout=180, max_retries=1)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT + (ANIMATION_PROMPT if with_animation else "")},
            *self._example_messages,
            {"role": "user", "content": _user_prompt(problem, code, fallback_name)},
        ]

        last_error: Exception | None = None
        best: tuple[GeneratedDraft, list[DraftIssue]] | None = None
        for _attempt in range(self.MAX_ATTEMPTS):
            try:
                # Structured outputs pin the shape to ``_AIDraft``. No
                # temperature: newer models reject anything but the default.
                response = await client.chat.completions.parse(
                    model=self._model,
                    messages=messages,
                    response_format=_AIDraft,
                )
            except ValidationError as exc:
                last_error = exc
                messages.append({"role": "user", "content": f"上一個回覆無法解析（{exc}）。請重新回傳完整的 JSON。"})
                continue
            except Exception as exc:  # noqa: BLE001 — surfaced as a 502 upstream
                if best is not None:  # a retry failed (network, truncated output): keep the draft we have
                    logger.warning("AI retry failed, keeping previous draft: %s", exc)
                    break
                raise RuntimeError(f"OpenAI 請求失敗：{exc}") from exc

            message = response.choices[0].message
            ai_draft = message.parsed
            if message.refusal or ai_draft is None or not ai_draft.steps:
                last_error = ValueError(message.refusal or "沒有回傳任何步驟")
                messages.append({"role": "user", "content": f"上一個回覆無法使用（{last_error}）。請依指示回傳完整的 JSON。"})
                continue

            draft = build_draft_from_ai(ai_draft, fallback_name, with_animation)
            issues = validate_draft(draft.steps, code)
            best = (draft, issues)
            errors = [issue.message for issue in issues if issue.level == "error"]
            if not errors:
                break
            messages.append({"role": "assistant", "content": message.content or ai_draft.model_dump_json()})
            messages.append(
                {
                    "role": "user",
                    "content": "上一個回覆有以下錯誤，請只修正這些問題，其餘保持不變，並重新回傳完整的 JSON：\n"
                    + "\n".join(f"- {e}" for e in errors),
                },
            )

        if best is None:
            raise RuntimeError(f"OpenAI 回傳的資料無法解析：{last_error}")
        draft, issues = best
        for issue in issues:
            logger.log(logging.WARNING if issue.level == "error" else logging.INFO, "AI draft issue: %s", issue.message)
        return draft

    async def summarize_problem(self, pdf: bytes, problem_id: int) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key, timeout=120, max_retries=1)
        file_data = f"data:application/pdf;base64,{base64.b64encode(pdf).decode()}"
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROBLEM_PROMPT.format(problem_id=problem_id)},
                            {"type": "file", "file": {"filename": f"{problem_id}.pdf", "file_data": file_data}},
                        ],
                    },
                ],
            )
            text = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001 — surfaced as a 502 upstream
            raise RuntimeError(f"OpenAI 請求失敗：{exc}") from exc
        if not text:
            raise RuntimeError("OpenAI 沒有回傳題目內容")
        return text

    async def review_draft(self, steps: list[DraftStep]) -> list[DraftIssue]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key, timeout=120, max_retries=1)
        try:
            response = await client.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": REVIEW_PROMPT},
                    {"role": "user", "content": review_user_prompt(steps)},
                ],
                response_format=_AIReview,
            )
            message = response.choices[0].message
        except Exception as exc:  # noqa: BLE001 — reported as an AI warning upstream
            raise RuntimeError(f"OpenAI 請求失敗：{exc}") from exc
        if message.refusal or message.parsed is None:
            raise RuntimeError(f"OpenAI 審稿回覆無法使用：{message.refusal or '無法解析'}")
        return [
            DraftIssue(item.stepNumber - 1 if 1 <= item.stepNumber <= len(steps) else None, item.level, item.message)
            for item in message.parsed.issues
        ]


class _AIReviewIssue(BaseModel):
    stepNumber: int
    level: Literal["error", "warning"]
    message: str


class _AIReview(BaseModel):
    issues: list[_AIReviewIssue]


REVIEW_PROMPT = """\
你是「CPE Video」教學影片的審稿員。使用者會給你一支影片的逐步腳本：每一步有畫面上顯示的 C++ 程式碼（附行號）、
這一步新增的行、畫面上標亮（highlight）的行與畫面對齊的行（focusLine），以及這一步的旁白字幕。
字幕裡的「這裡」「這一行」指的是標亮的行；沒有標亮時指的是 focusLine 或新增的行。
核心原則：旁白絕對不能和畫面上的程式碼不一致。

請逐步比對字幕與該步的程式碼、新增的行，只回報「具體的問題」：
- 字幕描述了畫面上沒有的程式碼，或提到之後步驟才會加入的程式碼。
- 這一步新增了程式碼，字幕卻完全沒有解釋它。
- 事實或演算法上的錯誤（例如把邏輯、變數用途、邊界條件講錯）。
- 步驟之間互相矛盾。
- 錯誤的時間或空間複雜度說法。

不要回報文風、用字、字數、語氣等風格建議。沒有問題就回傳空的 issues 陣列。
第 1、2 步是題目與解法說明、最後一步是總結，這三步不需要逐行解釋程式碼。

每個問題回傳：stepNumber（1 起算的步驟編號）、level（"error" = 內容錯誤或與程式碼矛盾；"warning" = 缺漏或可能誤導）、
message（繁體中文，一句話具體指出問題，例如「字幕說用 map 計數，但第 12 行用的是陣列」）。
"""


def review_user_prompt(steps: list[DraftStep]) -> str:
    parts: list[str] = []
    previous = ""
    for index, step in enumerate(steps):
        numbered = "\n".join(f"{n:>3} | {line}" for n, line in enumerate(step.fileContent.splitlines(), 1))
        added = _added_line_numbers(previous, step.fileContent)
        added_text = f"第 {min(added)}–{max(added)} 行" if added else "無"
        highlight_text = f"第 {step.highlight.startLine}–{step.highlight.endLine} 行" if step.highlight else "無"
        focus_text = f"第 {step.focusLine} 行" if step.focusLine is not None else "無"
        previous = step.fileContent
        parts.append(
            f"## 第 {index + 1} 步「{step.label}」\n"
            f"程式碼：\n{numbered}\n"
            f"本步新增的行：{added_text}\n"
            f"標亮的行：{highlight_text}\n"
            f"focusLine：{focus_text}\n"
            f"字幕：{step.subtitle.strip()}"
        )
    return "\n\n".join(parts)


PROBLEM_PROMPT = """\
附件是 UVa 線上解題系統第 {problem_id} 題的題目 PDF。請把它整理成繁體中文的題目說明，作為教學影片的題目文字，依序包含：

題意：
輸入格式：
輸出格式：
範例輸入：
範例輸出：

規則：
- 範例輸入與範例輸出必須逐字照抄原文，各自放在 ``` 程式碼區塊中。
- 其餘內容用純文字（不要用 markdown 標題、粗體或表格）。
- 只描述題目，不要給任何解法、演算法或提示。
- 只回傳題目說明本身，不要加開場白或結語。
"""


def build_generation_provider(settings: Settings) -> GeneratorProvider:
    api_key = settings.resolved_openai_api_key()
    if api_key:
        return OpenAIGeneratorProvider(
            api_key=api_key,
            model=settings.resolved_openai_model(),
            example_dir=settings.resolved_project_root() / "public" / EXAMPLE_FOLDER,
        )
    return MockGeneratorProvider()
