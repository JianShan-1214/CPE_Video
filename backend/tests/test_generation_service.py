import json

import pytest

from app.services.generation_service import (
    MockGeneratorProvider,
    OpenAIGeneratorProvider,
    build_draft_from_ai,
    build_generation_provider,
    estimate_duration_seconds,
    parse_ai_response,
)
from app.settings import Settings

SAMPLE = {
    "jobName": "A + B",
    "steps": [
        {
            "label": "題目說明",
            "fileLabel": "code01.cpp",
            "fileContent": "/*\n * 兩數相加\n */\n",
            "subtitle": "這題要我們讀入兩個整數並輸出總和。",
            "highlight": {"startLine": 1, "endLine": 3, "color": "blue"},
            "focusLine": None,
        },
        {
            "label": "結尾",
            "fileLabel": "code02.cpp",
            "fileContent": "#include <iostream>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}\n",
            "subtitle": "總結一下：直接讀入兩數相加輸出，複雜度 O(1)。感謝收看。",
            "highlight": None,
            "focusLine": 2,
        },
    ],
}


def test_parse_ai_response_accepts_plain_json():
    draft = parse_ai_response(json.dumps(SAMPLE, ensure_ascii=False))
    assert draft.jobName == "A + B"
    assert len(draft.steps) == 2


def test_parse_ai_response_tolerates_code_fence():
    fenced = "```json\n" + json.dumps(SAMPLE, ensure_ascii=False) + "\n```"
    draft = parse_ai_response(fenced)
    assert len(draft.steps) == 2


def test_build_draft_computes_monotonic_timings_and_keeps_fields():
    ai = parse_ai_response(json.dumps(SAMPLE, ensure_ascii=False))
    draft = build_draft_from_ai(ai, fallback_name="fallback")
    assert draft.job_name == "A + B"
    steps = draft.steps
    assert steps[0].from_ == 0
    assert steps[1].from_ == steps[0].to
    assert steps[0].to > steps[0].from_
    # highlight preserved on step 1, dropped on the outro
    assert steps[0].highlight is not None
    assert steps[1].highlight is None
    assert steps[1].focusLine == 2
    # trailing newline enforced
    assert steps[0].fileContent.endswith("\n")


def test_estimate_duration_has_floor():
    assert estimate_duration_seconds("短") == 5.0
    assert estimate_duration_seconds("字" * 100) > 5.0


def test_build_generation_provider_selects_by_key():
    assert isinstance(build_generation_provider(Settings(openai_api_key=None)), MockGeneratorProvider)
    provider = build_generation_provider(Settings(openai_api_key="sk-test", openai_model="gpt-4o-mini"))
    assert isinstance(provider, OpenAIGeneratorProvider)


@pytest.mark.anyio
async def test_mock_provider_is_async_and_structured():
    draft = await MockGeneratorProvider().generate(
        name="X", problem_statement="說明", solution_code="int main(){}\n"
    )
    assert draft.job_name == "X"
    assert draft.steps[-1].focusLine == 1
