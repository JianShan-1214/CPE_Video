"""AI draft generation.

Two providers share one async interface:

- ``MockGeneratorProvider`` — deterministic, offline, used when no OpenAI key
  is configured (and in tests).
- ``OpenAIGeneratorProvider`` — calls OpenAI to produce a tutorial draft that
  follows the project's four-section script structure (see ``skill.md``).

``build_generation_provider(settings)`` picks the right one at app startup.
"""

from dataclasses import dataclass
import json
import logging
import math
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from app.schemas import DraftStep, HighlightPreset
from app.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedDraft:
    job_name: str
    steps: list[DraftStep]


class GeneratorProvider(Protocol):
    async def generate(
        self, name: str | None, problem_statement: str, solution_code: str
    ) -> GeneratedDraft: ...


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
        self, name: str | None, problem_statement: str, solution_code: str
    ) -> GeneratedDraft:
        problem = _normalize_text(problem_statement)
        code = _normalize_code(solution_code)
        job_name = name.strip() if name and name.strip() else "GPT Mock Draft"
        problem_comment = _problem_comment(problem)
        code_lines = code.rstrip().split("\n")
        middle_count = min(5, max(3, math.ceil(len(code_lines) / 6)))
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
                    fileContent=_ensure_trailing_newline("\n".join(code_lines[:end])),
                    subtitle=_code_step_subtitle(index, middle_count),
                    highlight={
                        "startLine": start,
                        "endLine": end,
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
                fileContent=code,
                subtitle="總結一下：這份草稿已經把題目、解法思路與完整程式串成影片步驟。接下來可以在編輯器微調字幕、高亮與標注，再匯出成可 render 的檔案。",
                focusLine=1,
            ),
        )
        return GeneratedDraft(job_name=job_name, steps=steps)


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


class _AIStep(BaseModel):
    label: str
    fileLabel: str
    fileContent: str
    subtitle: str
    highlight: _AIHighlight | None = None
    focusLine: int | None = Field(default=None, ge=1)


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


def validate_draft(steps: list[DraftStep], solution_code: str) -> list[DraftIssue]:
    """Check a draft against the script rules in ``skill.md``.

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

        if index > 0 and not _is_subsequence(_non_blank(steps[index - 1].fileContent), _non_blank(step.fileContent)):
            issues.append(DraftIssue(index, "error", f"第 {n} 步不是累加式：沒有完整保留第 {n - 1} 步的程式碼（順序須一致）。"))

        if step.focusLine is not None and not 1 <= step.focusLine <= line_count:
            issues.append(DraftIssue(index, "error", f"第 {n} 步的 focusLine={step.focusLine} 超出檔案範圍 1–{line_count}。"))

        if step.highlight is not None:
            start, end = step.highlight.startLine, step.highlight.endLine
            if not (1 <= start <= end <= line_count):
                issues.append(
                    DraftIssue(index, "error", f"第 {n} 步的 highlight {start}–{end} 無效（檔案共 {line_count} 行，且起始行不能大於結束行）。"),
                )

        if 2 <= index <= last - 1:
            added = len(_non_blank(step.fileContent)) - len(_non_blank(steps[index - 1].fileContent))
            if not 1 <= added <= 12:
                issues.append(DraftIssue(index, "warning", f"第 {n} 步新增了 {added} 行程式碼，建議每步新增 1–12 行。"))

        max_chars = 100 if index in (0, 1, last) else 80
        chars = len(step.subtitle.strip())
        if not 30 <= chars <= max_chars:
            issues.append(DraftIssue(index, "warning", f"第 {n} 步字幕有 {chars} 字，建議 30–{max_chars} 字。"))

    # The last file = step 1's problem comment block + the pasted solution.
    if _non_blank(steps[last].fileContent) != _non_blank(steps[0].fileContent) + _non_blank(solution_code):
        issues.append(
            DraftIssue(last, "error", f"最後一步（第 {last + 1} 步）的內容必須等於「第 1 步的題目註解」加上使用者提供的完整解答（忽略空行後逐行比對）。"),
        )

    return issues


# ── AI → draft ───────────────────────────────────────────────────────────────


def build_draft_from_ai(ai: _AIDraft, fallback_name: str) -> GeneratedDraft:
    """Convert the model output into ``DraftStep``s.

    Highlight ranges are recomputed from the diff against the previous step —
    the model's own line numbers are unreliable. Its color (and a null
    highlight) is kept.
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
        self, name: str | None, problem_statement: str, solution_code: str
    ) -> GeneratedDraft:
        from openai import AsyncOpenAI

        problem = _normalize_text(problem_statement)
        code = _normalize_code(solution_code)
        fallback_name = name.strip() if name and name.strip() else "AI 生成草稿"

        client = AsyncOpenAI(api_key=self._api_key)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
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

            draft = build_draft_from_ai(ai_draft, fallback_name)
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


def build_generation_provider(settings: Settings) -> GeneratorProvider:
    api_key = settings.resolved_openai_api_key()
    if api_key:
        return OpenAIGeneratorProvider(
            api_key=api_key,
            model=settings.resolved_openai_model(),
            example_dir=settings.resolved_project_root() / "public" / EXAMPLE_FOLDER,
        )
    return MockGeneratorProvider()
