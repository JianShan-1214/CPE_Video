import pytest

from app.services.trace import TraceError, instrument

SRC = """#include <iostream>
using namespace std;

int main() {
    int n = 3;
    // a comment
    int s = 0;
    for (int i = 0; i < n; i++) {
        s += i;
    }
    cout << s << endl;
    return 0;
}"""


def point(line, *exprs, pid=1):
    return {"id": pid, "line": line, "exprs": [{"expr": e} for e in exprs]}


def test_inserts_before_line_and_accounts_for_include():
    out = instrument(SRC, [point(9, "s", "i"), point(11, "s", pid=2)]).split("\n")
    assert out[0] == '#include "cpe_trace.hpp"'
    # original line L is at out[L] (include shifts by one) until the first insertion
    assert out[8] == "    for (int i = 0; i < n; i++) {"
    assert out[9] == "        CPE_SNAP(1, s, i);"
    assert out[10] == "        s += i;"
    assert out[12] == "    CPE_SNAP(2, s);"
    assert out[13] == "    cout << s << endl;"
    # nothing else changed
    assert [line for line in out[1:] if "CPE_SNAP" not in line] == SRC.split("\n")


def test_c_array_length_and_indexed_exprs():
    out = instrument(SRC, [{"id": 7, "line": 9, "exprs": [{"expr": "a", "length": "n"}, {"expr": "dp[i - 1][0]"}]}])
    assert "CPE_SNAP(7, CPE_ARR(a, n), dp[i - 1][0]);" in out


def test_several_points_on_one_line_keep_order():
    out = instrument(SRC, [point(9, "s", pid=1), point(9, "i", pid=2)]).split("\n")
    assert out[9:12] == ["        CPE_SNAP(1, s);", "        CPE_SNAP(2, i);", "        s += i;"]


@pytest.mark.parametrize(
    "line",
    [10, 13],  # a line starting with `}` = snapshot at the end of the block
)
def test_closing_brace_line_is_allowed(line):
    instrument(SRC, [point(line, "s")])


@pytest.mark.parametrize(
    ("src", "line", "fragment"),
    [
        (SRC, 3, "空白"),
        (SRC, 6, "註解"),
        (SRC, 1, "前置處理"),
        (SRC, 4, "不在函式本體內"),  # global scope
        ("int main() {\n  int x = 1;\n  if (x) {\n    x = 2;\n  } else {\n    x = 3;\n  }\n}", 5, "else"),
        ("int main() {\n  int x = 1;\n  if (x) x = 2;\n  else x = 3;\n}", 4, "else"),
        ("int main() {\n  try {\n    throw 1;\n  }\n  catch (int) {}\n}", 5, "catch"),
        ("int main() {\n  int s = 0;\n  for (int i = 0; i < 3; i++)\n    s += i;\n}", 4, "上一行"),
        ("int main() {\n  int x = 1;\n  if (x)\n    x = 2;\n}", 4, "上一行"),
        ("int f(int a, int b);\nint main() {\n  int x = f(1,\n    2);\n  return x;\n}", 4, "括號"),
        ("int main() {\n  int x = 0;\n  switch (x) {\n    case 0:\n      x = 1;\n  }\n}", 4, "case"),
        ("int main() {\n  int x = 0;\n  do {\n    x++;\n  }\n  while (x < 3);\n}", 6, "do"),
        ("struct P {\n  int x;\n  int y;\n};\nint main() {}", 3, "不在函式本體內"),
        ("#include <vector>\nint main() {\n  std::vector<int> v = {\n    1,\n    2};\n}", 5, "不在函式本體內"),
        ("int main() {\n  int x = 0;\n  /* x;\n  still comment; */\n  x = 1;\n}", 4, "註解"),
    ],
)
def test_rejects_unsafe_positions(src, line, fragment):
    with pytest.raises(TraceError, match=f"第 {line} 行前面不能插入追蹤點") as err:
        instrument(src, [point(line, "x")])
    assert fragment in str(err.value)


def test_scanner_ignores_braces_in_strings_and_comments():
    src = "int main() {\n  const char* s = \"}\";  // }\n  char c = '}';\n  int x = 0;\n  return x;\n}"
    instrument(src, [point(4, "x"), point(5, "x", pid=2)])


def test_lambda_body_inside_call_is_allowed():
    src = (
        "#include <algorithm>\n#include <vector>\nint main() {\n  std::vector<int> v{3, 1};\n"
        "  std::sort(v.begin(), v.end(), [](int a, int b) {\n    return a < b;\n  });\n}"
    )
    instrument(src, [point(6, "a", "b")])


def test_while_after_plain_block_is_allowed():
    src = "int main() {\n  int x = 0;\n  if (x) {\n    x = 1;\n  }\n  while (x < 3) {\n    x++;\n  }\n}"
    instrument(src, [point(6, "x")])


def test_preprocessor_lines_are_skipped_when_finding_previous_line():
    src = "int main() {\n  int x = 0;\n#ifdef LOCAL\n  x = 5;\n#endif\n  return x;\n}"
    instrument(src, [point(6, "x")])


@pytest.mark.parametrize("expr", ["x", "_a1", "a[i]", "a[0]", "g[i][j]", "a[i + 1]", "a[j-1]", "dp[n][0]"])
def test_expression_whitelist_accepts(expr):
    instrument(SRC, [point(9, expr)])


@pytest.mark.parametrize(
    "expr",
    [
        'x);system("id");(',
        "a[i](",
        "*p",
        "&x",
        "a->b",
        "a.b()",
        "v.size()",
        "a[i][j][k]",
        "a[i+j]",
        "a[b[i]]",
        "a[ i]",
        "a[i  + 1]",
        "f(x)",
        "x y",
        "x,y",
        "x\n",
        "1x",
        "",
        "變數",
        "x;",
        "(x)",
        None,
        5,
    ],
)
def test_expression_whitelist_rejects(expr):
    with pytest.raises(TraceError, match="不合法"):
        instrument(SRC, [{"id": 1, "line": 9, "exprs": [{"expr": expr}]}])


@pytest.mark.parametrize("length", ["n-1", "n); system(", "a[0]", "", " n", 3])
def test_length_whitelist_rejects(length):
    with pytest.raises(TraceError, match="陣列長度"):
        instrument(SRC, [{"id": 1, "line": 9, "exprs": [{"expr": "a", "length": length}]}])


@pytest.mark.parametrize(
    "points",
    [
        [],
        [{"line": 9, "exprs": [{"expr": "s"}]}],
        [point(0, "s")],
        [point(99, "s")],
        [point(9, "s"), point(11, "s")],  # duplicate id
        [{"id": 1, "line": 9, "exprs": []}],
        [{"id": True, "line": 9, "exprs": [{"expr": "s"}]}],
        [{"id": -1, "line": 9, "exprs": [{"expr": "s"}]}],
        [{"id": 1, "line": "9", "exprs": [{"expr": "s"}]}],
        [{"id": 1, "line": 9, "exprs": [{"expr": "s"}, {"expr": "s"}]}],
        [{"id": 1, "line": 9, "exprs": ["s"]}],
        "not a list",
    ],
)
def test_rejects_malformed_points(points):
    with pytest.raises(TraceError):
        instrument(SRC, points)


# ── when="after" ─────────────────────────────────────────────────────────────


def after(line, *exprs, pid=1):
    return {**point(line, *exprs, pid=pid), "when": "after"}


# UVa 1062 with a 5-line problem comment: the braceless if/else is lines 22–25.
UVA1062 = "/*\n * UVa 1062\n *\n *\n */\n" + """#include <algorithm>
#include <iostream>
#include <string>
#include <vector>
using namespace std;

int main() {

    string line;
    int tc = 0;
    while (cin >> line && line != "end") {
        ++tc;
        vector<int> tail;
        for (char ch : line) {
            int v = ch - 'A' + 1;
            auto it = lower_bound(tail.begin(), tail.end(), v);
            if (it == tail.end())
                tail.push_back(v);
            else
                *it = v;
        }
        cout << "Case " << tc << ": " << tail.size() << "\\n";
    }
    return 0;
}
"""


def test_after_inserts_on_the_next_line():
    out = instrument(SRC, [after(9, "s"), point(10, "i", pid=2), point(9, "i", pid=3)]).split("\n")
    assert out[9:14] == [
        "        CPE_SNAP(3, i);",
        "        s += i;",
        "        CPE_SNAP(1, s);  // cpe:after",  # after 9 comes before "before 10" (same spot)
        "    CPE_SNAP(2, i);",
        "    }",
    ]
    assert [line for line in out[1:] if "CPE_SNAP" not in line] == SRC.split("\n")


def test_after_closing_brace_and_adjacent_lines():
    out = instrument(SRC, [after(10, "s"), after(11, "s", pid=2), point(12, "s", pid=3)]).split("\n")
    assert out[10:16] == [
        "    }",
        "    CPE_SNAP(1, s);  // cpe:after",
        "    cout << s << endl;",
        "    CPE_SNAP(2, s);  // cpe:after",
        "    CPE_SNAP(3, s);",
        "    return 0;",
    ]


def test_uva1062_braceless_if_else():
    lines = UVA1062.split("\n")
    assert lines[21].strip() == "if (it == tail.end())" and lines[23].strip() == "else"
    instrument(UVA1062, [after(25, "tail")])  # after the whole if/else, inside the for body
    with pytest.raises(TraceError, match="第 23 行後面不能插入追蹤點") as err:
        instrument(UVA1062, [after(23, "tail")])
    assert "else" in str(err.value) and 'when="after"' in str(err.value)
    with pytest.raises(TraceError, match="第 23 行前面"):  # "before" still rejects the braceless body
        instrument(UVA1062, [point(23, "tail")])


def test_after_braceless_loop_body_runs_after_the_statement():
    src = "int main() {\n  int s = 0;\n  for (int i = 0; i < 3; i++)\n    s += i;\n  return s;\n}"
    assert "    CPE_SNAP(1, s);  // cpe:after\n  return s;" in instrument(src, [after(4, "s")])


@pytest.mark.parametrize(
    ("src", "line", "fragment"),
    [
        (SRC, 3, "空白"),
        (SRC, 6, "註解"),
        (SRC, 8, "; 或 }"),  # `for (...) {`
        (SRC, 13, "不在函式本體內"),  # main's closing brace
        ("int g = 1;\nint main() {}", 1, "不在函式本體內"),
        ("int main() {\n  int x = 1;\n  if (x) {\n    x = 2;\n  }\n  else {\n    x = 3;\n  }\n}", 5, "else"),
        ("int main() {\n  int x = 1;\n  if (x) x = 2;\n  // note\n\n  else x = 3;\n}", 3, "else"),
        ("int main() {\n  try {\n    throw 1;\n  }\n  catch (int) {}\n}", 4, "catch"),
        ("int main() {\n  int x = 0;\n  do {\n    x++;\n  }\n  while (x < 3);\n}", 5, "do"),
        ("int main() {\n  for (int i = 0;\n       i < 3;\n       i++) {}\n}", 2, "括號"),
        ("int main() {\n  int x = 1; /* start\n  still comment */\n  x = 2;\n}", 2, "註解"),
    ],
)
def test_after_rejects_unsafe_positions(src, line, fragment):
    with pytest.raises(TraceError, match=f"第 {line} 行後面不能插入追蹤點") as err:
        instrument(src, [after(line, "x")])
    assert fragment in str(err.value)


def test_after_allows_next_line_closing_brace_before_else_or_while():
    src = "int main() {\n  int x = 0;\n  if (x) {\n    x = 2;\n  } else {\n    x = 3;\n  }\n  do {\n    x++;\n  } while (x < 3);\n}"
    instrument(src, [after(4, "x"), after(6, "x", pid=2), after(9, "x", pid=3), after(10, "x", pid=4)])


def test_rejects_unknown_when():
    with pytest.raises(TraceError, match="when"):
        instrument(SRC, [{**point(9, "s"), "when": "during"}])
