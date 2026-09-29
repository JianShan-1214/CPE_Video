"""Trace plan → real execution → animation frames (Phase B)."""

import json
import sqlite3
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.schemas import DraftStep, StepTrace
from app.services.generation_service import MockGeneratorProvider, OpenAIGeneratorProvider, trace_draft
from app.services.trace import TraceError, find_compiler
from app.services.trace_animation import build_animation, invalid_pointers, map_compile_errors, map_line, plan_exprs
from app.settings import Settings
from tests.test_api import client, sample_step  # noqa: F401 — fixture
from tests.test_draft_check import app_client  # noqa: F401 — fixture
from tests.test_draft_validation import COMMENT, FULL, SOLUTION, fake_client, step, valid_ai_draft

try:
    find_compiler()
    HAS_CXX = True
except TraceError:
    HAS_CXX = False
needs_cxx = pytest.mark.skipif(not HAS_CXX, reason="no C++ compiler (g++ / clang++) on this machine")
REPO = Path(__file__).resolve().parents[2]


def plan(as_="array", expr="arr", length=None, pointers=(), vars=(), max_frames=12, caption=None, line=1):
    return StepTrace.model_validate(
        {
            "line": line,
            "show": {"as": as_, "expr": expr, "length": length},
            "pointers": list(pointers),
            "vars": list(vars),
            "maxFrames": max_frames,
            "caption": caption,
        }
    )


def snaps(*values_list, truncated=None):
    out = []
    for hit, values in enumerate(values_list, 1):
        snap = {"id": 0, "hit": hit, "values": values}
        if truncated:
            snap["truncated"] = truncated
        out.append(snap)
    return out


# ── line mapping ─────────────────────────────────────────────────────────────


def test_map_line_follows_insertions_and_reindent():
    step_file = "int main() {\n  int x;\n  x = 1;\n}\n"
    final = "#include <cstdio>\nint main() {\n    int x;\n    int y = 2;\n    x = 1;\n}\n"
    assert map_line(step_file, final, 1) == 2
    assert map_line(step_file, final, 3) == 5  # re-indented, shifted past an inserted line
    assert map_line("int main() {\n  // gone\n}\n", final, 2) is None


# ── plan → trace expressions ─────────────────────────────────────────────────


def test_plan_exprs_placeholders_dedup_and_length():
    p = plan(length="n", pointers=["j"], vars=["i", "j"], caption="{arr[j]} vs {arr[j + 1]}，i={i}，{tot}，{b[2]}")
    assert plan_exprs(p) == [
        {"expr": "arr", "length": "n"},
        {"expr": "j"},
        {"expr": "i"},
        {"expr": "tot"},
        {"expr": "b"},  # another container: traced whole, never b[2] itself
    ]
    assert plan_exprs(plan("vars", None, vars=["x"])) == [{"expr": "x"}]


@pytest.mark.parametrize(
    "bad",
    [plan(caption="{arr[j] * 2}"), plan(caption="{f(x)}"), plan(caption="{a[i][j]}"), plan("grid", None)],
)
def test_plan_exprs_rejects_bad_plans(bad):
    with pytest.raises(TraceError):
        plan_exprs(bad)


# ── frames from synthetic snapshots (no compiler) ────────────────────────────


def test_array_frames_mark_pointers_and_caption():
    p = plan(pointers=["j", "k", "flag"], vars=["j"], caption="{arr[j]} vs {arr[j + 1]}", max_frames=3)
    anim, warnings = build_animation(
        p,
        snaps(
            {"arr": [3, 1, 2], "j": 0, "k": 3, "flag": True},
            {"arr": [1, 3, 2], "j": 1, "k": -1, "flag": True},
            {"arr": [1, 2, 3], "j": 2, "k": 0, "flag": True},
            {"arr": [9, 9, 9], "j": 0, "k": 0, "flag": True},  # beyond maxFrames
        ),
    )
    assert anim == {
        "type": "array",
        "frames": [
            {"values": [3, 1, 2], "pointers": {"j": 0}, "vars": {"j": 0}, "caption": "3 vs 1"},
            {"values": [1, 3, 2], "pointers": {"j": 1}, "mark": [0, 1], "vars": {"j": 1}, "caption": "3 vs 2"},
            {"values": [1, 2, 3], "pointers": {"j": 2, "k": 0}, "mark": [1, 2], "vars": {"j": 2}, "caption": "3 vs —"},
        ],
    }
    assert warnings == ["說明裡的 {arr[j + 1]} 超出範圍或沒有值，顯示為「—」"]


def test_array_truncation_string_chars_and_long_caption():
    anim, warnings = build_animation(plan(caption="字" * 50), snaps({"arr": list(range(20))}))
    assert anim["frames"][0]["values"] == list(range(16))
    assert anim["frames"][0]["caption"] == "字" * 39 + "…"
    assert any("超過 16" in w for w in warnings)
    anim, _ = build_animation(plan(expr="s"), snaps({"s": "ab"}, {"s": "ac"}))
    assert [f["values"] for f in anim["frames"]] == [["a", "b"], ["a", "c"]]
    assert anim["frames"][1]["mark"] == [1]


def test_queue_has_front_back():
    anim, _ = build_animation(plan("queue", "q"), snaps({"q": [4, 5, 6]}, {"q": [5, 6]}, {"q": []}))
    assert anim["type"] == "array"
    assert [f.get("pointers") for f in anim["frames"]] == [{"front": 0, "back": 2}, {"front": 0, "back": 1}, None]


def test_stacks_from_stack_and_vector_of_vectors():
    anim, warnings = build_animation(plan("stacks", "st"), snaps({"st": [1, 2]}, {"st": [1, 2, 3]}))
    assert anim == {"type": "stacks", "frames": [{"stacks": [[1, 2]]}, {"stacks": [[1, 2, 3]]}]}
    assert warnings == []
    anim, _ = build_animation(plan("stacks", "piles"), snaps({"piles": [[3, 2], [1], []]}))
    assert anim["frames"][0]["stacks"] == [[3, 2], [1], []]


def test_stacks_with_duplicates_fall_back_to_grid():
    anim, warnings = build_animation(plan("stacks", "piles"), snaps({"piles": [[1], [2]]}, {"piles": [[1, 2], [2]]}))
    assert anim == {"type": "grid", "frames": [{"cells": [[1], [2]]}, {"cells": [[1, 2], [2]], "mark": [[0, 1]]}]}
    assert any("改用表格" in w for w in warnings)


def test_grid_truncation_and_mark():
    big = [[r * 13 + c for c in range(13)] for r in range(13)]
    anim, warnings = build_animation(plan("grid", "dp"), snaps({"dp": big}))
    cells = anim["frames"][0]["cells"]
    assert (len(cells), {len(r) for r in cells}) == (12, {12})
    assert any("12×12" in w for w in warnings)
    anim, _ = build_animation(plan("grid", "g"), snaps({"g": ["#.", "."]}, {"g": ["##", ".", "x"]}))
    assert anim["frames"][0]["cells"] == [["#", "."], ["."]]
    assert anim["frames"][1]["mark"] == [[0, 1], [2, 0]]


def test_vars_only_and_type_mismatch():
    anim, _ = build_animation(plan("vars", None, vars=["n", "ok", "v"], caption="n={n}"), snaps({"n": 3, "ok": False, "v": [1, 2]}))
    assert anim == {"type": "vars", "frames": [{"vars": {"n": 3, "ok": False, "v": "[1,2]"}, "caption": "n=3"}]}
    with pytest.raises(TraceError):
        build_animation(plan("vars", None), snaps({}))
    with pytest.raises(TraceError, match="一維"):
        build_animation(plan(), snaps({"arr": 5}))


def test_map_compile_errors_to_original_lines():
    instrumented = '#include "cpe_trace.hpp"\nint main() {\n    CPE_SNAP(4, zzz);\n    int x;\n}'
    errors = "main.cpp:3:17: error: 'zzz' was not declared\nmain.cpp:4:9: warning: unused"
    text, ids = map_compile_errors(instrumented, errors)
    assert text == "main.cpp:2:17: error: 'zzz' was not declared\nmain.cpp:2:9: warning: unused"
    assert ids == [4]


# ── real execution ───────────────────────────────────────────────────────────


def draft_step(content, trace=None):
    return DraftStep.model_validate({**step(content).model_dump(by_alias=True), "trace": trace})


def bubble_steps(trace_plan, marker="\t\t\tif (arr[j] > arr[j + 1]) {"):
    folder = REPO / "public" / "example-bubble_sort"
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    files = [(folder / s["file"]).read_text(encoding="utf-8") for s in config["steps"]]
    assert config["steps"][-1]["file"] == max(p.name for p in folder.glob("code*.cpp"))
    index = next(i for i, f in enumerate(files) if marker in f.splitlines())
    line = files[index].splitlines().index(marker) + 1
    trace = {**trace_plan, "line": line}
    return index, [draft_step(f, trace if i == index else None) for i, f in enumerate(files)]


BUBBLE_PLAN = {
    "show": {"as": "array", "expr": "arr", "length": "n"},
    "pointers": ["j"],
    "vars": ["i", "j"],
    "maxFrames": 3,
    "caption": "{arr[j]} vs {arr[j + 1]}",
}


@needs_cxx
@pytest.mark.anyio
async def test_bubble_sort_frames_come_from_real_execution():
    index, steps = bubble_steps(BUBBLE_PLAN)
    out, issues = await trace_draft(steps, "")
    assert issues == []
    anim = out[index].animation.model_dump(mode="json")
    assert anim == {
        "type": "array",
        "frames": [
            {"values": [64, 34, 25, 12, 22, 11, 90], "pointers": {"j": 0}, "vars": {"i": 0, "j": 0}, "caption": "64 vs 34"},
            {"values": [34, 64, 25, 12, 22, 11, 90], "pointers": {"j": 1}, "mark": [0, 1], "vars": {"i": 0, "j": 1}, "caption": "64 vs 25"},
            {"values": [34, 25, 64, 12, 22, 11, 90], "pointers": {"j": 2}, "mark": [1, 2], "vars": {"i": 0, "j": 2}, "caption": "64 vs 12"},
        ],
    }
    assert all(s.animation is None for i, s in enumerate(out) if i != index)


@needs_cxx
@pytest.mark.anyio
async def test_out_of_scope_var_is_a_compile_error_for_that_step():
    index, steps = bubble_steps({**BUBBLE_PLAN, "vars": ["zzz"]})
    out, issues = await trace_draft(steps, "")
    assert out[index].animation is None
    assert [(i.step_index, i.level) for i in issues] == [(index, "error")]
    assert "無法編譯" in issues[0].message and "zzz" in issues[0].message
    assert "main.cpp:9:" in issues[0].message  # the if line in the final file, not the instrumented one


SUM = "#include <iostream>\nint main() {\n    int n, x, s = 0;\n    std::cin >> n;\n    for (int k = 0; k < n; k++) {\n        std::cin >> x;\n        s += x;\n        if (s < 0) {\n            s = 0;\n        }\n    }\n    std::cout << s << std::endl;\n}\n"
SUM_PLAN = {"line": 7, "show": {"as": "vars", "expr": None, "length": None}, "pointers": [], "vars": ["k", "x", "s"], "maxFrames": 12, "caption": "s={s}"}


@needs_cxx
@pytest.mark.anyio
async def test_stdin_program_with_wrong_sample_output_warns():
    steps = [draft_step("// 加總\n"), draft_step(SUM, SUM_PLAN)]
    out, issues = await trace_draft(steps, "3\n1 2 3\n", "7\n")
    assert [(i.step_index, i.level, i.message) for i in issues] == [(None, "warning", "你的解答在範例輸入下輸出與範例輸出不符")]
    assert [f.vars for f in out[1].animation.frames] == [{"k": 0, "x": 1, "s": 0}, {"k": 1, "x": 2, "s": 1}, {"k": 2, "x": 3, "s": 3}]
    _, issues = await trace_draft(steps, "3\n1 2 3\n", "6\n")
    assert issues == []


@needs_cxx
@pytest.mark.anyio
async def test_never_reached_point_warns_and_bad_line_errors():
    steps = [draft_step("// 加總\n"), draft_step(SUM, {**SUM_PLAN, "line": 9})]
    out, issues = await trace_draft(steps, "1\n5\n")
    assert out[1].animation is None
    assert [(i.step_index, i.level) for i in issues] == [(1, "warning")] and "從沒執行到" in issues[0].message
    steps = [draft_step(SUM), draft_step(SUM, SUM_PLAN)]  # step 2 adds nothing
    _, issues = await trace_draft(steps, "1\n5\n")
    assert [(i.step_index, i.level) for i in issues] == [(1, "error")] and "不是這一步新增的行" in issues[0].message


# ── generate(): retry loop ───────────────────────────────────────────────────


def ai_with_trace(line):
    ai = valid_ai_draft()
    ai["steps"][4]["trace"] = {
        "line": line,
        "show": {"as": "vars", "expr": None, "length": None},
        "pointers": [],
        "vars": ["a", "b"],
        "maxFrames": 1,
        "caption": "a={a}, b={b}",
    }
    return ai


@needs_cxx
@pytest.mark.anyio
async def test_generate_feeds_trace_errors_back_then_builds_animation(monkeypatch):
    calls = fake_client(monkeypatch, [ai_with_trace(9), ai_with_trace(10), {"issues": []}])  # step 5 only adds line 10 (cout)
    draft = await OpenAIGeneratorProvider(api_key="k", model="m").generate(
        None, "兩數相加", SOLUTION, with_animation=True, sample_input="3 4\n", sample_output="7\n"
    )
    assert len(calls) == 3  # 2 drafts + 1 review
    assert calls[1][-2]["role"] == "assistant"
    assert "trace.line=9 不是這一步新增的行" in calls[1][-1]["content"]
    assert draft.steps[4].trace.line == 10
    assert draft.steps[4].animation.model_dump(mode="json") == {
        "type": "vars",
        "frames": [{"vars": {"a": 3, "b": 4}, "caption": "a=3, b=4"}],
    }


@pytest.mark.anyio
async def test_generate_without_animation_drops_model_trace(monkeypatch):
    fake_client(monkeypatch, [ai_with_trace(10)])
    draft = await OpenAIGeneratorProvider(api_key="k", model="m").generate(None, "兩數相加", SOLUTION)
    assert all(s.trace is None and s.animation is None for s in draft.steps)


@pytest.mark.anyio
async def test_mock_provider_attaches_no_trace():
    draft = await MockGeneratorProvider().generate(None, "p", SOLUTION, with_animation=True, sample_input="1 2\n")
    assert all(s.trace is None and s.animation is None for s in draft.steps)


# ── API ──────────────────────────────────────────────────────────────────────


def traced_payload(sample_input):
    ai_trace = ai_with_trace(10)["steps"][4]["trace"]
    steps = [step(COMMENT), step(COMMENT + FULL)]
    body = [s.model_dump(by_alias=True) for s in steps]
    body[1]["trace"] = {**ai_trace, "line": 10}
    return {"steps": body, "sampleInput": sample_input}


@needs_cxx
@pytest.mark.anyio
async def test_trace_endpoint_recomputes_with_new_sample_input(app_client):  # noqa: F811
    _, http = app_client
    first = await http.post("/api/drafts/trace", json=traced_payload("3 4\n"))
    assert first.status_code == 200
    assert first.json()["issues"] == []
    assert first.json()["steps"][1]["animation"]["frames"][0]["vars"] == {"a": 3, "b": 4}
    assert "animation" not in first.json()["steps"][0] or first.json()["steps"][0]["animation"] is None
    second = await http.post("/api/drafts/trace", json={**traced_payload("10 20\n"), "sampleOutput": "31\n"})
    body = second.json()
    assert body["steps"][1]["animation"]["frames"][0]["caption"] == "a=10, b=20"
    assert body["issues"] == [
        {"stepIndex": None, "level": "warning", "message": "你的解答在範例輸入下輸出與範例輸出不符", "source": "rule"}
    ]
    assert (await http.post("/api/drafts/trace", json={"steps": [], "sampleInput": ""})).status_code == 422


@pytest.mark.anyio
async def test_job_round_trips_sample_io_and_trace(client):  # noqa: F811
    job = (await client.post("/api/jobs", json={"name": "A"})).json()
    assert (job["sampleInput"], job["sampleOutput"]) == ("", "")
    trace = ai_with_trace(10)["steps"][4]["trace"]
    body = {**job, "sampleInput": "3 4\n", "sampleOutput": "7\n", "steps": [{**sample_step(), "trace": trace}]}
    assert (await client.put(f"/api/jobs/{job['id']}", json=body)).status_code == 200
    got = (await client.get(f"/api/jobs/{job['id']}")).json()
    assert (got["sampleInput"], got["sampleOutput"]) == ("3 4\n", "7\n")
    assert got["steps"][0]["trace"]["show"] == {"as": "vars", "expr": None, "length": None}
    assert got["steps"][0]["trace"]["vars"] == ["a", "b"]


@pytest.mark.anyio
async def test_startup_migration_adds_sample_columns(tmp_path):
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE jobs (id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, theme VARCHAR NOT NULL, "
            "width_json TEXT NOT NULL, steps_json TEXT NOT NULL, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)"
        )
        conn.execute("INSERT INTO jobs VALUES ('j1', 'Old', 'github-dark', '{\"type\": \"auto\"}', '[]', 1, 1)")
    for _ in range(2):  # idempotent across restarts
        app = create_app(Settings(database_url=f"sqlite+aiosqlite:///{db}", project_root=tmp_path))
        async with app.router.lifespan_context(app), AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
            got = (await http.get("/api/jobs/j1")).json()
            assert (got["name"], got["sampleInput"], got["sampleOutput"]) == ("Old", "", "")
    with sqlite3.connect(db) as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(jobs)")]
    assert cols.count("sample_input") == 1 and cols.count("sample_output") == 1


# ── when="after" ─────────────────────────────────────────────────────────────

SWAP_LINE = "\t\t\t\tarr[j + 1] = temp;"


def test_map_compile_errors_after_point_maps_to_its_own_line():
    instrumented = '#include "cpe_trace.hpp"\nint main() {\n    int x;\n    CPE_SNAP(4, zzz);  // cpe:after\n    CPE_SNAP(5, x);\n    x = 1;\n}'
    errors = "main.cpp:4:17: error: 'zzz'\nmain.cpp:5:3: note\nmain.cpp:6:5: warning"
    text, ids = map_compile_errors(instrumented, errors)
    assert text == "main.cpp:2:17: error: 'zzz'\nmain.cpp:3:3: note\nmain.cpp:3:5: warning"
    assert ids == [4, 5]


def test_stored_plan_without_when_defaults_to_before():
    assert plan().when == "before"


@needs_cxx
@pytest.mark.anyio
async def test_bubble_sort_after_swap_shows_post_swap_arrays():
    index, steps = bubble_steps({**BUBBLE_PLAN, "when": "after", "caption": None}, SWAP_LINE)
    out, issues = await trace_draft(steps, "")
    assert issues == []
    assert [f.values for f in out[index].animation.frames] == [
        [34, 64, 25, 12, 22, 11, 90],
        [34, 25, 64, 12, 22, 11, 90],
        [34, 25, 12, 64, 22, 11, 90],
    ]


@needs_cxx
@pytest.mark.anyio
async def test_after_point_compile_error_names_its_own_line():
    index, steps = bubble_steps({**BUBBLE_PLAN, "when": "after", "vars": ["zzz"]}, SWAP_LINE)
    _, issues = await trace_draft(steps, "")
    assert [(i.step_index, i.level) for i in issues] == [(index, "error")]
    assert "main.cpp:12:" in issues[0].message  # the swap line in the final file


@needs_cxx
@pytest.mark.anyio
async def test_uva1062_after_braceless_else_shows_real_tail():
    from bisect import bisect_left

    from tests.test_trace_instrument import UVA1062

    sample = "A\nCBACBACBACBACBA\nCCCCBBBBAAAA\nACMICPC\nend\n"
    expected = []
    for word in sample.split()[:-1]:
        tail = []
        for ch in word:
            v = ord(ch) - ord("A") + 1
            k = bisect_left(tail, v)
            tail[k:k + 1] = [v]
            expected.append(list(tail))
    trace = {"line": 25, "when": "after", "show": {"as": "array", "expr": "tail", "length": None}, "pointers": [], "vars": ["v"], "maxFrames": 12, "caption": "放入 {v}"}
    steps = [draft_step("/*\n * UVa 1062\n *\n *\n */\n"), draft_step(UVA1062, trace)]
    out, issues = await trace_draft(steps, sample, "Case 1: 1\nCase 2: 3\nCase 3: 1\nCase 4: 4\n")
    assert issues == []
    frames = out[1].animation.frames
    assert [f.values for f in frames] == expected[:12]
    assert frames[1].caption == "放入 3"


def test_review_prompt_states_snapshot_timing_and_ground_truth():
    from app.services.generation_service import REVIEW_PROMPT, review_user_prompt

    frames = {"type": "array", "frames": [{"values": [1, 2]}]}
    steps = [
        DraftStep.model_validate({**draft_step(FULL).model_dump(by_alias=True), "animation": frames, "trace": {**BUBBLE_PLAN, "line": 7, "when": w}})
        for w in ("before", "after")
    ]
    steps.append(DraftStep.model_validate({**draft_step(FULL).model_dump(by_alias=True), "animation": frames}))
    prompt = review_user_prompt(steps)
    assert "每一格是第 7 行執行前的真實狀態" in prompt.split("## 第 2 步")[0]
    assert "每一格是第 7 行執行後的真實狀態" in prompt.split("## 第 2 步")[1]
    assert "真實狀態" not in prompt.split("## 第 3 步")[1]  # hand-written animation: no claim
    assert "不要回報動畫數值有錯" in REVIEW_PROMPT


def test_trace_prompt_explains_when_and_placeholders():
    from app.services.generation_service import TRACE_PROMPT

    assert '"after"' in TRACE_PROMPT and '"before"' in TRACE_PROMPT and "else 分支的最後一行" in TRACE_PROMPT
    assert "必須」寫成 {佔位符}" in TRACE_PROMPT


# ── pointers must index the shown container ──────────────────────────────────

PTR_SRC = """\
void show(int a[], int n) {
    for (int k = 0; k < n; k++) cout << a[k];
}
int main() {
    int a[5], g[3][3];
    int i = 0, j = 1, k = 2, r = 0, c = 0, m = 0;
    // a[m] in a comment
    string s = "a[m]";
    a[j + 1] = a[idx[i]];
    g[r][c] = 1;
    return 0;
}
"""


@pytest.mark.parametrize(
    ("as_", "expr", "pointers", "bad"),
    [
        ("array", "a", ["i", "j", "m"], ["m"]),  # nested index counts; comment / string don't
        ("array", "a", ["k"], ["k"]),  # a[k] only in another function
        ("grid", "g", ["r", "c"], []),  # 2nd dimension accepted for grid
        ("array", "g", ["c"], ["c"]),  # ...but not for array
        ("queue", "a", ["m"], []),  # queue front/back are implicit
        ("vars", None, ["m"], []),
    ],
)
def test_invalid_pointers(as_, expr, pointers, bad):
    assert invalid_pointers(plan(as_=as_, expr=expr, pointers=pointers), PTR_SRC, line=10) == bad


def test_build_animation_drops_pointers_but_keeps_vars():
    anim, warnings = build_animation(plan(pointers=["i", "j"], vars=["i"]), snaps({"arr": [1, 2, 3], "i": 0, "j": 2}), ["i"])
    assert anim["frames"] == [{"values": [1, 2, 3], "pointers": {"j": 2}, "vars": {"i": 0}}]
    assert warnings == ["指標 i 從未被用來索引 arr，已從箭頭移除"]


@needs_cxx
@pytest.mark.anyio
async def test_bubble_sort_outer_counter_is_not_a_pointer():
    index, steps = bubble_steps({**BUBBLE_PLAN, "pointers": ["i", "j"]})  # printArray's arr[i] doesn't count
    out, issues = await trace_draft(steps, "")
    assert [(i.step_index, i.level, i.message) for i in issues] == [
        (index, "error", f"第 {index + 1} 步的追蹤計畫有誤：pointers 裡的 i 從未被用來索引 arr，請移到 vars"),
        (index, "warning", f"第 {index + 1} 步的動畫：指標 i 從未被用來索引 arr，已從箭頭移除"),
    ]
    frames = out[index].animation.frames
    assert [f.pointers for f in frames] == [{"j": 0}, {"j": 1}, {"j": 2}]
    assert frames[0].vars == {"i": 0, "j": 0}
