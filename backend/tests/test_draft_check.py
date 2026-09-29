from types import SimpleNamespace

import openai
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.schemas import DraftStep
from app.services.generation_service import (
    DraftIssue,
    MockGeneratorProvider,
    OpenAIGeneratorProvider,
    validate_draft,
)
from app.settings import Settings
from tests.test_draft_validation import COMMENT, FULL, READ, SOLUTION, fake_client, step


def test_validate_draft_without_solution_skips_last_step_rule():
    bad_last = [step(COMMENT), step(COMMENT + READ)]
    assert any("最後一步" in i.message for i in validate_draft(bad_last, SOLUTION))
    assert not any("最後一步" in i.message for i in validate_draft(bad_last, None))


# ── POST /api/drafts/check ───────────────────────────────────────────────────


class SpyProvider(MockGeneratorProvider):
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def review_draft(self, steps):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
async def app_client(tmp_path):
    app = create_app(Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 't.db'}", project_root=tmp_path))
    async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield app, c


def payload(ai=True):
    # step 2 drops the comment block → one cumulative-rule error; "Hi" subtitles → warnings
    steps = [step(COMMENT, subtitle="Hi"), step(FULL, focus=99, subtitle="Hi")]
    return {"steps": [s.model_dump(by_alias=True) for s in steps], "ai": ai}


@pytest.mark.anyio
async def test_check_returns_rule_and_ai_issues(app_client):
    app, client = app_client
    spy = SpyProvider([DraftIssue(1, "error", "字幕說用 map，但程式用陣列")])
    app.state.generation_provider = spy
    res = await client.post("/api/drafts/check", json=payload())
    assert res.status_code == 200
    issues = res.json()["issues"]
    rule = [i for i in issues if i["source"] == "rule"]
    assert {i["stepIndex"] for i in rule} == {0, 1}
    assert any("不是累加式" in i["message"] and i["level"] == "error" for i in rule)
    assert any("focusLine=99" in i["message"] for i in rule)
    assert [i for i in issues if i["source"] == "ai"] == [
        {"stepIndex": 1, "level": "error", "message": "字幕說用 map，但程式用陣列", "source": "ai"},
    ]
    assert spy.calls == 1


@pytest.mark.anyio
async def test_check_ai_false_skips_review(app_client):
    app, client = app_client
    spy = SpyProvider([])
    app.state.generation_provider = spy
    issues = (await client.post("/api/drafts/check", json=payload(ai=False))).json()["issues"]
    assert issues and all(i["source"] == "rule" for i in issues)
    assert spy.calls == 0


@pytest.mark.anyio
async def test_check_review_failure_keeps_rule_issues(app_client):
    app, client = app_client
    app.state.generation_provider = SpyProvider(RuntimeError("OpenAI 請求失敗：timeout"))
    res = await client.post("/api/drafts/check", json=payload())
    assert res.status_code == 200
    issues = res.json()["issues"]
    assert any(i["source"] == "rule" and i["level"] == "error" for i in issues)
    assert issues[-1] == {
        "stepIndex": None, "level": "warning", "message": "AI 審稿失敗：OpenAI 請求失敗：timeout", "source": "ai",
    }


@pytest.mark.anyio
async def test_check_with_default_mock_provider(app_client):
    _, client = app_client
    issues = (await client.post("/api/drafts/check", json=payload())).json()["issues"]
    assert [i for i in issues if i["source"] == "ai"] == [
        {"stepIndex": None, "level": "warning", "message": "未設定 OpenAI API key，已略過 AI 審稿", "source": "ai"},
    ]
    assert any(i["source"] == "rule" for i in issues)


# ── OpenAI provider ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_openai_review_maps_step_numbers(monkeypatch):
    calls = fake_client(monkeypatch, [{"issues": [
        {"stepNumber": 2, "level": "error", "message": "字幕提到尚未加入的輸出"},
        {"stepNumber": 9, "level": "warning", "message": "超出範圍"},
        {"stepNumber": 0, "level": "warning", "message": "零"},
    ]}])
    steps: list[DraftStep] = [step(COMMENT + READ), step(COMMENT + FULL)]
    issues = await OpenAIGeneratorProvider(api_key="sk-test", model="m").review_draft(steps)
    assert issues == [
        DraftIssue(1, "error", "字幕提到尚未加入的輸出"),
        DraftIssue(None, "warning", "超出範圍"),
        DraftIssue(None, "warning", "零"),
    ]
    prompt = calls[0][-1]["content"]
    assert "## 第 2 步" in prompt and "本步新增的行：第 10–10 行" in prompt
    assert " 10 |     cout << a + b << endl;" in prompt


@pytest.mark.anyio
async def test_openai_review_failures_raise_runtime_error(monkeypatch):
    provider = OpenAIGeneratorProvider(api_key="sk-test", model="m")
    fake_client(monkeypatch, [ConnectionError("down")])
    with pytest.raises(RuntimeError, match="請求失敗"):
        await provider.review_draft([step(FULL)])
    fake_client(monkeypatch, [None])  # refusal
    with pytest.raises(RuntimeError, match="無法使用"):
        await provider.review_draft([step(FULL)])


@pytest.mark.anyio
async def test_summarize_problem_empty_choices_is_runtime_error(monkeypatch):
    async def create(**_):
        return SimpleNamespace(choices=[])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **_: client)
    with pytest.raises(RuntimeError):
        await OpenAIGeneratorProvider(api_key="sk-test", model="m").summarize_problem(b"%PDF", 100)
