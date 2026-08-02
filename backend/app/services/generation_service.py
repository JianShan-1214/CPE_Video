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
import math
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError

from app.schemas import DraftStep, HighlightPreset
from app.settings import Settings


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
   - 每步新增 1–5 行程式碼，採「累加式」：codeNN.cpp 的 fileContent 必須包含前面所有步驟的程式碼，再加上這一步的新行（不是只有新增片段）。
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
- subtitle 為引導式旁白，以「接下來」「這裡」「我們」等開頭，說明「做什麼」與「為什麼」，一般步驟 30–60 字。
- label 是時間軸上的簡短標題。
- 全部文字使用繁體中文。

# 回傳格式（只回傳這個 JSON 物件）
{
  "jobName": "影片名稱",
  "steps": [
    {
      "label": "題目說明",
      "fileLabel": "code01.cpp",
      "fileContent": "/*\\n * ...\\n */\\n",
      "subtitle": "...",
      "highlight": { "startLine": 1, "endLine": 3, "color": "blue" },
      "focusLine": null
    }
  ]
}
每個 step 都要有 label / fileLabel / fileContent / subtitle 四個欄位；highlight 與 focusLine 不需要時設為 null。
"""


def parse_ai_response(content: str) -> _AIDraft:
    """Validate the model's JSON output into an ``_AIDraft``.

    Tolerates an accidental ```json fence around the object.
    """
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
        text = text.removeprefix("json").strip()
    data = json.loads(text)
    return _AIDraft.model_validate(data)


def build_draft_from_ai(ai: _AIDraft, fallback_name: str) -> GeneratedDraft:
    job_name = ai.jobName.strip() or fallback_name
    steps: list[DraftStep] = []
    cursor = 0.0
    for ai_step in ai.steps:
        duration = estimate_duration_seconds(ai_step.subtitle)
        highlight = ai_step.highlight.model_dump() if ai_step.highlight else None
        steps.append(
            DraftStep(
                label=ai_step.label,
                from_=round(cursor, 1),
                to=round(cursor + duration, 1),
                fileLabel=ai_step.fileLabel,
                fileContent=_ensure_trailing_newline(ai_step.fileContent),
                subtitle=ai_step.subtitle,
                focusLine=ai_step.focusLine,
                highlight=highlight,
            ),
        )
        cursor += duration
    return GeneratedDraft(job_name=job_name, steps=steps)


class OpenAIGeneratorProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def generate(
        self, name: str | None, problem_statement: str, solution_code: str
    ) -> GeneratedDraft:
        from openai import AsyncOpenAI

        problem = _normalize_text(problem_statement)
        code = _normalize_code(solution_code)
        fallback_name = name.strip() if name and name.strip() else "AI 生成草稿"
        user_prompt = (
            f"題目說明：\n{problem}\n\n"
            f"完整 C++ 解答：\n{code}\n\n"
            f"影片名稱（若空白請自訂一個簡短名稱）：{fallback_name}"
        )

        client = AsyncOpenAI(api_key=self._api_key)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                # No temperature: newer models reject anything but the default,
                # and the JSON schema in the prompt already pins the output shape.
                response = await client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
            except Exception as exc:  # noqa: BLE001 — surfaced as a 502 upstream
                raise RuntimeError(f"OpenAI 請求失敗：{exc}") from exc

            content = response.choices[0].message.content or ""
            try:
                ai_draft = parse_ai_response(content)
                if not ai_draft.steps:
                    raise ValueError("steps 為空")
                return build_draft_from_ai(ai_draft, fallback_name)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_error = exc
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {
                        "role": "user",
                        "content": f"上一個回覆無法解析（{exc}）。請只回傳符合格式的 JSON 物件，不要其他文字。",
                    },
                )

        raise RuntimeError(f"OpenAI 回傳的資料無法解析：{last_error}")


def build_generation_provider(settings: Settings) -> GeneratorProvider:
    api_key = settings.resolved_openai_api_key()
    if api_key:
        return OpenAIGeneratorProvider(api_key=api_key, model=settings.resolved_openai_model())
    return MockGeneratorProvider()
