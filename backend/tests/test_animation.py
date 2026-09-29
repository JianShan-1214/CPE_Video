import json

import openai
import pytest
from openai.lib._pydantic import to_strict_json_schema

from app.schemas import DraftStep
from app.services.generation_service import (
    ANIMATION_PROMPT,
    MockGeneratorProvider,
    OpenAIGeneratorProvider,
    _AIDraft,
    build_draft_from_ai,
    review_user_prompt,
    validate_draft,
)
from app.services.render_service import build_render_files
from tests.test_api import client, sample_step  # noqa: F401 — fixture
from tests.test_draft_check import app_client  # noqa: F401 — fixture
from tests.test_draft_validation import COMMENT, FULL, READ, SOLUTION, fake_client, run, step, valid_ai_draft
from tests.test_render_service import make_job

ARRAY = {
    "type": "array",
    "frames": [
        {"values": [3, 1, 2], "pointers": {"i": 0}, "mark": [0], "caption": "i 從 0 開始"},
        {"values": [1, 3, 2.5], "pointers": {"i": 1}},
    ],
}
STACKS = {"type": "stacks", "labels": ["A", "B"], "frames": [{"stacks": [[1, 2], []]}, {"stacks": [[1], [2]], "caption": "搬走 2"}]}
CODE = "int main() {\n    for (int i = 0; i < n; i++) {}\n}\n"


def anim_step(animation, content=CODE):
    return DraftStep.model_validate({**step(content).model_dump(by_alias=True), "animation": animation})


# ── B1: schema round-trip ────────────────────────────────────────────────────


def test_animation_round_trips_through_render_config():
    job = make_job([{**sample_step(), "animation": ARRAY}, {**sample_step("code02.cpp"), "animation": STACKS}, sample_step("code03.cpp")])
    _, config_json, _ = build_render_files(job, "x")
    steps = json.loads(config_json)["steps"]
    assert steps[0]["animation"] == ARRAY
    assert steps[1]["animation"] == STACKS
    assert "animation" not in steps[2]


@pytest.mark.anyio
async def test_animation_persists_and_imports(client):  # noqa: F811
    job = (await client.post("/api/jobs", json={"name": "A"})).json()
    saved = await client.put(f"/api/jobs/{job['id']}", json={**job, "steps": [{**sample_step(), "animation": ARRAY}]})
    assert saved.status_code == 200
    assert (await client.get(f"/api/jobs/{job['id']}")).json()["steps"][0]["animation"] == ARRAY

    config = {"steps": [{"label": "A", "from": 0, "to": 3, "file": "a.cpp", "subtitle": "Hi", "animation": STACKS}]}
    imported = await client.post("/api/jobs/import", json={"configJson": json.dumps(config), "cppFiles": {"a.cpp": "x\n"}})
    assert imported.status_code == 201
    assert imported.json()["steps"][0]["animation"] == STACKS


@pytest.mark.anyio
async def test_invalid_animation_shape_is_rejected(client):  # noqa: F811
    job = (await client.post("/api/jobs", json={"name": "A"})).json()
    for bad in ({"type": "tree", "frames": []}, {"type": "array", "frames": [{"values": [1], "pointers": {"i": 1.5}}]}):
        res = await client.put(f"/api/jobs/{job['id']}", json={**job, "steps": [{**sample_step(), "animation": bad}]})
        assert res.status_code == 422


# ── B2: AI output → draft ────────────────────────────────────────────────────


def ai_with_animation():
    ai = valid_ai_draft()
    ai["steps"][4]["animation"] = {
        "type": "array",
        "frames": [{"values": [1, 2], "pointers": [{"name": "a", "index": 0}, {"name": "b", "index": 1}], "mark": None, "caption": None}],
    }
    ai["steps"][3]["animation"] = {"type": "stacks", "labels": None, "frames": [{"stacks": [[1], [2]], "caption": "x"}]}
    return _AIDraft.model_validate(ai)


def test_with_animation_converts_pointer_list_to_dict():
    steps = build_draft_from_ai(ai_with_animation(), "f", with_animation=True).steps
    assert steps[4].animation.model_dump(exclude_none=True) == {"type": "array", "frames": [{"values": [1, 2], "pointers": {"a": 0, "b": 1}}]}
    assert steps[3].animation.type == "stacks"
    assert steps[0].animation is None


def test_without_animation_strips_model_output():
    assert all(s.animation is None for s in build_draft_from_ai(ai_with_animation(), "f").steps)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_ai_schema_is_strict_valid():
    schema = to_strict_json_schema(_AIDraft)
    for node in _walk(schema):
        assert "oneOf" not in node
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])


@pytest.mark.anyio
async def test_generate_sends_animation_prompt_only_when_asked(monkeypatch):
    calls = fake_client(monkeypatch, [valid_ai_draft()])
    await run()
    assert ANIMATION_PROMPT not in calls[0][0]["content"]

    ai = ai_with_animation().model_dump()
    calls = fake_client(monkeypatch, [ai])
    draft = await OpenAIGeneratorProvider(api_key="k", model="m").generate(None, "兩數相加", SOLUTION, with_animation=True)
    assert calls[0][0]["content"].endswith(ANIMATION_PROMPT)
    assert draft.steps[4].animation.frames[0].pointers == {"a": 0, "b": 1}


@pytest.mark.anyio
async def test_generate_endpoint_passes_flag(app_client):  # noqa: F811
    app, http = app_client
    seen = []

    class Spy(MockGeneratorProvider):
        async def generate(self, name, problem_statement, solution_code, with_animation=False):
            seen.append(with_animation)
            return await super().generate(name, problem_statement, solution_code)

    app.state.generation_provider = Spy()
    body = {"problemStatement": "p", "solutionCode": "int main(){}\n"}
    assert (await http.post("/api/generate-draft", json=body)).status_code == 201
    assert (await http.post("/api/generate-draft", json={**body, "withAnimation": True})).status_code == 201
    assert seen == [False, True]


# ── B3: animation validation ─────────────────────────────────────────────────


def issues_of(animation, content=CODE):
    return [(i.level, i.message) for i in validate_draft([anim_step(animation, content)], None) if "動畫" in i.message]


def test_valid_animations_have_no_issues():
    assert issues_of(ARRAY) == []
    assert issues_of(STACKS) == []


def test_animation_errors_are_what_the_renderer_drops():
    too_many = {"type": "array", "frames": [{"values": list(range(17))}]}
    assert [lvl for lvl, _ in issues_of(too_many)] == ["error"]
    assert issues_of({"type": "array", "frames": []})[0][0] == "error"
    wide = {"type": "stacks", "frames": [{"stacks": [[i] for i in range(9)]}]}
    tall = {"type": "stacks", "frames": [{"stacks": [list(range(13))]}]}
    dup = {"type": "stacks", "frames": [{"stacks": [[1], ["1"]]}]}
    dup_float = {"type": "stacks", "frames": [{"stacks": [[1], [1.0]]}]}  # JS String(1.0) == "1"
    labels = {"type": "stacks", "labels": list("ABCDEFGHI"), "frames": [{"stacks": [[1]]}]}
    for bad in (wide, tall, dup, dup_float, labels):
        assert [lvl for lvl, _ in issues_of(bad)] == ["error"], bad


def test_animation_warnings():
    anim = {
        "type": "array",
        "frames": [{"values": [1, 2], "pointers": {"i": 2, "k": 0}, "mark": [5], "caption": "字" * 41}],
    }
    found = issues_of(anim)
    assert all(lvl == "warning" for lvl, _ in found)
    text = "\n".join(m for _, m in found)
    assert "指標 i=2 超出範圍 0–1" in text
    assert "mark 5 超出範圍" in text
    assert "41 字" in text
    assert "指標 k 沒有出現" in text
    assert "指標 i 沒有出現" not in text  # "i" is a whole word in CODE, not just a letter in "int"


# ── Part A: check request bounds, review prompt, added-lines warning ─────────


@pytest.mark.anyio
async def test_check_request_bounds(app_client):  # noqa: F811
    _, http = app_client
    ok = step(FULL).model_dump(by_alias=True)
    assert (await http.post("/api/drafts/check", json={"steps": [ok], "ai": False})).status_code == 200
    for steps in ([], [ok] * 61, [{**ok, "fileContent": "x" * 50_001}], [{**ok, "subtitle": "x" * 1_001}]):
        assert (await http.post("/api/drafts/check", json={"steps": steps, "ai": False})).status_code == 422


@pytest.mark.anyio
async def test_job_put_is_not_bounded(client):  # noqa: F811
    job = (await client.post("/api/jobs", json={"name": "A"})).json()
    res = await client.put(f"/api/jobs/{job['id']}", json={**job, "steps": [{**sample_step(), "subtitle": "x" * 2_000}]})
    assert res.status_code == 200


def test_review_prompt_includes_highlight_and_focus_line():
    prompt = review_user_prompt([step(FULL, {"startLine": 7, "endLine": 7, "color": "green"}), step(FULL, focus=4)])
    assert "標亮的行：第 7–7 行\nfocusLine：無" in prompt
    assert "標亮的行：無\nfocusLine：第 4 行" in prompt


def test_cumulative_error_suppresses_added_lines_warning():
    steps = [step(COMMENT), step(COMMENT), step(COMMENT + READ), step(READ), step(COMMENT + FULL)]
    messages = [i.message for i in validate_draft(steps, None)]
    assert any("第 4 步不是累加式" in m for m in messages)
    assert not any("第 4 步新增了" in m for m in messages)


@pytest.mark.anyio
async def test_openai_clients_have_bounded_timeouts(monkeypatch):
    kwargs = []

    def factory(**kw):
        kwargs.append(kw)
        raise ConnectionError("stop")

    monkeypatch.setattr(openai, "AsyncOpenAI", factory)
    provider = OpenAIGeneratorProvider(api_key="k", model="m")
    with pytest.raises(ConnectionError):
        await provider.generate(None, "p", "c")
    with pytest.raises(ConnectionError):
        await provider.review_draft([step(FULL)])
    assert kwargs == [
        {"api_key": "k", "timeout": 180, "max_retries": 1},
        {"api_key": "k", "timeout": 120, "max_retries": 1},
    ]
