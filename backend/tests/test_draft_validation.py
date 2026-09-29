from types import SimpleNamespace

import openai
import pytest

from app.services.generation_service import (
    OpenAIGeneratorProvider,
    _AIDraft,
    _added_line_numbers,
    build_draft_from_ai,
    load_example_messages,
    validate_draft,
)
from app.schemas import DraftStep

COMMENT = "/*\n * 兩數相加\n */\n"
SKELETON = "#include <iostream>\nusing namespace std;\n\nint main() {\n\n    return 0;\n}\n"
READ = "#include <iostream>\nusing namespace std;\n\nint main() {\n    int a, b;\n    cin >> a >> b;\n    return 0;\n}\n"
FULL = (
    "#include <iostream>\nusing namespace std;\n\nint main() {\n    int a, b;\n    cin >> a >> b;\n"
    "    cout << a + b << endl;\n    return 0;\n}\n"
)
SOLUTION = FULL  # what the user pastes: no problem comment block

SUB_OK = "這裡我們先讀入兩個整數 a 和 b，接下來才能把它們相加並輸出結果。"  # 30–80 chars
SUB_LONG_OK = SUB_OK + "這一段說明比較長，用在題目、解法與結尾這三個結構性步驟。"  # 60–80 chars: fine for any step


def ai_step(file_label, content, highlight=None, focus=None, subtitle=SUB_OK, label="步驟"):
    return {
        "label": label,
        "fileLabel": file_label,
        "fileContent": content,
        "subtitle": subtitle,
        "highlight": highlight,
        "focusLine": focus,
    }


def valid_ai_draft(highlight_line=99):
    """A rule-abiding draft whose AI highlight ranges are deliberately wrong."""
    hl = {"startLine": highlight_line, "endLine": highlight_line, "color": "blue"}
    return {
        "jobName": "A + B",
        "steps": [
            ai_step("code01.cpp", COMMENT, hl, subtitle=SUB_LONG_OK),
            ai_step("code01.cpp", COMMENT, None, subtitle=SUB_LONG_OK),
            ai_step("code02.cpp", COMMENT + SKELETON, hl),
            ai_step("code03.cpp", COMMENT + READ, hl),
            ai_step("code04.cpp", COMMENT + FULL, hl),
            ai_step("code04.cpp", COMMENT + FULL, None, focus=7, subtitle=SUB_LONG_OK),
        ],
    }


def build(ai: dict):
    return build_draft_from_ai(_AIDraft.model_validate(ai), "fallback").steps


def step(content, highlight=None, focus=None, subtitle=SUB_OK):
    return DraftStep(
        label="x", **{"from": 0}, to=5, fileLabel="c.cpp", fileContent=content,
        subtitle=subtitle, highlight=highlight, focusLine=focus,
    )


def messages_of(issues, level):
    return [i.message for i in issues if i.level == level]


# ── diff-derived highlight ───────────────────────────────────────────────────


def test_highlight_is_recomputed_from_diff():
    steps = build(valid_ai_draft())
    # step 1 vs empty previous → every non-blank line
    assert (steps[0].highlight.startLine, steps[0].highlight.endLine) == (1, 3)
    # skeleton: blank lines are not counted at the edges
    assert (steps[2].highlight.startLine, steps[2].highlight.endLine) == (4, 10)
    # skeleton blank line inside main() replaced by two new lines
    assert (steps[3].highlight.startLine, steps[3].highlight.endLine) == (8, 9)
    # insertion in the middle of the file
    assert (steps[4].highlight.startLine, steps[4].highlight.endLine) == (10, 10)
    assert steps[4].highlight.color == "blue"  # AI color kept


def test_new_function_after_another_function_is_attributed_to_the_insertion():
    prev = "int f() {\n    return 1;\n}\nint main() {\n    return 0;\n}\n"
    cur = "int f() {\n    return 1;\n}\nint g() {\n    return 2;\n}\nint main() {\n    return 0;\n}\n"
    assert _added_line_numbers(prev, cur) == [4, 5, 6]


def test_null_highlight_preserved_and_no_diff_keeps_ai_range():
    ai = valid_ai_draft()
    ai["steps"][1]["highlight"] = {"startLine": 2, "endLine": 3, "color": "red"}
    steps = build(ai)
    assert steps[5].highlight is None
    # step 2 is the same file as step 1 → nothing added → AI range kept
    assert (steps[1].highlight.startLine, steps[1].highlight.endLine, steps[1].highlight.color) == (2, 3, "red")


# ── validator rules ──────────────────────────────────────────────────────────


def test_valid_draft_has_no_issues():
    assert validate_draft(build(valid_ai_draft()), SOLUTION) == []


def test_cumulative_rule():
    ok = [step(COMMENT), step(COMMENT + "\n\n" + FULL, subtitle=SUB_LONG_OK)]
    assert not any("累加" in m for m in messages_of(validate_draft(ok, SOLUTION), "error"))
    broken = [step(COMMENT + READ), step(FULL)]  # dropped the comment block
    errors = messages_of(validate_draft(broken, SOLUTION), "error")
    assert any("第 2 步不是累加式" in m for m in errors)


def test_last_step_must_be_problem_comment_plus_solution():
    # blank lines dropped and tabs instead of 4 spaces are tolerated
    ok = [step(COMMENT), step(COMMENT + FULL.replace("\n\n", "\n").replace("    ", "\t"))]
    assert not any("最後一步" in m for m in messages_of(validate_draft(ok, SOLUTION), "error"))
    # a comment block without leading "*" is fine too
    bare = "/*\n題目：兩數相加\n*/\n"
    assert not any("最後一步" in m for m in messages_of(validate_draft([step(bare), step(bare + FULL)], SOLUTION), "error"))
    # dropping a code line that looks like a comment ("*p = 1;") is caught
    with_ptr = SOLUTION.replace("    return 0;", "    *p = 1;\n    return 0;")
    assert any("最後一步（第 2 步）" in m for m in messages_of(validate_draft([step(COMMENT), step(COMMENT + FULL)], with_ptr), "error"))
    bad = [step(COMMENT), step(COMMENT + READ)]
    assert any("最後一步（第 2 步）" in m for m in messages_of(validate_draft(bad, SOLUTION), "error"))


def test_focus_line_range():
    assert not any("focusLine" in m for m in messages_of(validate_draft([step(FULL, focus=9)], SOLUTION), "error"))
    errors = messages_of(validate_draft([step(FULL, focus=10)], SOLUTION), "error")
    assert any("focusLine=10" in m for m in errors)


def test_highlight_range():
    good = {"startLine": 2, "endLine": 9, "color": "blue"}
    assert not any("highlight" in m for m in messages_of(validate_draft([step(FULL, good)], SOLUTION), "error"))
    for bad in ({"startLine": 2, "endLine": 10, "color": "blue"}, {"startLine": 5, "endLine": 4, "color": "blue"}):
        errors = messages_of(validate_draft([step(FULL, bad)], SOLUTION), "error")
        assert any("highlight" in m for m in errors)


def test_middle_step_added_lines_warning():
    steps = [step(COMMENT), step(COMMENT), step(COMMENT), step(COMMENT + READ), step(COMMENT + FULL)]
    warnings = messages_of(validate_draft(steps, SOLUTION), "warning")
    assert any("第 3 步新增了 0 行" in m and "1–12" in m for m in warnings)
    assert not any("第 4 步新增" in m for m in warnings)  # 7 lines added
    assert not any("第 5 步新增" in m for m in warnings)  # last step is not a middle step


def test_subtitle_length_warning():
    steps = [step(FULL, subtitle=SUB_LONG_OK), step(FULL, subtitle=SUB_LONG_OK),
             step(FULL, subtitle=SUB_LONG_OK), step(FULL, subtitle=SUB_LONG_OK * 2), step(FULL, subtitle="太短")]
    warnings = messages_of(validate_draft(steps, SOLUTION), "warning")
    assert not any("第 1 步字幕" in m or "第 2 步字幕" in m or "第 3 步字幕" in m for m in warnings)
    assert any("第 4 步字幕" in m and "30–80" in m for m in warnings)
    assert any("第 5 步字幕有 2 字" in m and "30–100" in m for m in warnings)


# ── retry loop with a fake OpenAI client ─────────────────────────────────────


def fake_client(monkeypatch, responses):
    """Patch ``openai.AsyncOpenAI``; each ``parse`` call pops the next draft dict (None = refusal, Exception = raised)."""
    calls: list[list[dict]] = []

    async def parse(*, model, messages, response_format):
        calls.append([dict(m) for m in messages])
        data = responses.pop(0)
        if isinstance(data, Exception):
            raise data
        parsed = response_format.model_validate(data) if data is not None else None
        message = SimpleNamespace(parsed=parsed, refusal=None if data else "I can't", content=str(data))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **_: client)
    return calls


def broken_ai_draft():
    ai = valid_ai_draft()
    ai["steps"][5]["fileContent"] = COMMENT + READ  # last step doesn't match the solution
    return ai


async def run(provider=None):
    provider = provider or OpenAIGeneratorProvider(api_key="sk-test", model="m")
    return await provider.generate(name=None, problem_statement="兩數相加", solution_code=SOLUTION)


@pytest.mark.anyio
async def test_retry_sends_errors_back_and_returns_fixed_draft(monkeypatch):
    calls = fake_client(monkeypatch, [broken_ai_draft(), valid_ai_draft()])
    draft = await run()
    assert len(calls) == 2
    assert draft.steps[-1].fileContent == COMMENT + FULL
    feedback = calls[1][-1]["content"]
    assert calls[1][-2]["role"] == "assistant"
    assert "最後一步（第 6 步）" in feedback


@pytest.mark.anyio
async def test_always_invalid_returns_last_draft(monkeypatch):
    last = broken_ai_draft()
    last["jobName"] = "last"
    calls = fake_client(monkeypatch, [broken_ai_draft(), broken_ai_draft(), last])
    draft = await run()
    assert len(calls) == 3
    assert draft.job_name == "last"


@pytest.mark.anyio
async def test_failed_retry_request_keeps_previous_draft(monkeypatch):
    calls = fake_client(monkeypatch, [broken_ai_draft(), ConnectionError("network down")])
    draft = await run()
    assert len(calls) == 2
    assert draft.steps[-1].fileContent == COMMENT + READ


@pytest.mark.anyio
async def test_never_parseable_raises(monkeypatch):
    fake_client(monkeypatch, [None, None, None])
    with pytest.raises(RuntimeError, match="無法解析"):
        await run()


@pytest.mark.anyio
async def test_few_shot_example_is_sent(monkeypatch, tmp_path):
    from app.settings import Settings
    from app.services.generation_service import build_generation_provider

    provider = build_generation_provider(Settings(openai_api_key="sk-test"))
    calls = fake_client(monkeypatch, [valid_ai_draft()])
    await run(provider)
    roles = [m["role"] for m in calls[0]]
    assert roles == ["system", "user", "assistant", "user"]
    assert "參考範例" in calls[0][1]["content"]
    # a missing example folder is skipped silently
    missing = OpenAIGeneratorProvider(api_key="sk-test", model="m", example_dir=tmp_path / "nope")
    calls = fake_client(monkeypatch, [valid_ai_draft()])
    await run(missing)
    assert [m["role"] for m in calls[0]] == ["system", "user"]


def test_malformed_example_config_is_skipped(tmp_path):
    (tmp_path / "config.json").write_text('{"steps": [{"label": "x", "file": "a.cpp"}]}', encoding="utf-8")
    (tmp_path / "a.cpp").write_text("// x\n", encoding="utf-8")
    assert load_example_messages(tmp_path) == []  # missing subtitle must not crash app startup
