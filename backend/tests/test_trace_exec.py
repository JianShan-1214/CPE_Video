"""Compiles and runs real C++: header serialization, sandbox limits, equivalence."""

import os
import shutil
import signal
import sys
import time
from pathlib import Path

import pytest

from app.services.trace import (
    TraceError,
    check_equivalence,
    compile_and_run,
    find_compiler,
    instrument,
    run_trace,
)
from app.services.trace.runner import SANDBOX_UID


def _compilers() -> list[str]:
    found: dict[str, str] = {}
    try:
        candidates = [find_compiler(), shutil.which("clang++")]
    except TraceError:
        return []
    for path in filter(None, candidates):
        found.setdefault(os.path.realpath(path), path)
    return list(found.values())


COMPILERS = _compilers()
pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not COMPILERS, reason="no C++ compiler (g++ / clang++) on this machine"),
]
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(params=COMPILERS or ["none"])
def each_compiler(request, monkeypatch):
    monkeypatch.setenv("CPE_CXX", request.param)


# ── header serialization ─────────────────────────────────────────────────────

TYPES_SRC = r"""
#include "cpe_trace.hpp"
#include <climits>
#include <iostream>
int main() {
    int i = -5; long long big = LLONG_MAX; unsigned u = 4000000000u; bool b = true;
    double d = 1.5; double inf = 1.0 / 0.0; double nan_ = std::nan(""); float f = 0.25f;
    char c = 'x'; char q = '"';
    std::string s = "q\"b\\s\nt\t\x01中文";
    int a[5] = {1, 2, 3, 4, 5};
    std::vector<int> v{1, 2, 3};
    std::vector<std::vector<int>> g{{1, 2}, {3}, {}};
    std::stack<int> st; st.push(1); st.push(2); st.push(3);
    std::queue<int> qu; qu.push(7); qu.push(8);
    std::deque<int> dq{4, 5};
    std::vector<bool> vb{true, false};
    std::vector<std::string> vs{"a", "b"};
    CPE_SNAP(1, i, big, u, b, d, inf, nan_, f, c, q, s);
    CPE_SNAP(2, CPE_ARR(a, 3), v, g, st, qu, dq, vb, vs, a[4]);
    std::cout << st.size() << qu.size() << "\n";
}
"""


async def test_header_serializes_every_supported_type(each_compiler):
    r = await compile_and_run(TYPES_SRC)
    assert r.compile.ok, r.compile.errors
    assert (r.exit_code, r.stdout) == (0, "32\n")  # containers were copied, not consumed
    assert r.snapshots == [
        {
            "id": 1,
            "hit": 1,
            "values": {
                "i": -5,
                "big": 9223372036854775807,
                "u": 4000000000,
                "b": True,
                "d": 1.5,
                "inf": None,
                "nan_": None,
                "f": 0.25,
                "c": "x",
                "q": '"',
                "s": 'q"b\\s\nt\t\x01中文',
            },
        },
        {
            "id": 2,
            "hit": 1,
            "values": {
                "a": [1, 2, 3],
                "v": [1, 2, 3],
                "g": [[1, 2], [3], []],
                "st": [1, 2, 3],  # bottom -> top
                "qu": [7, 8],  # front -> back
                "dq": [4, 5],
                "vb": [True, False],
                "vs": ["a", "b"],
                "a[4]": 5,
            },
        },
    ]


async def test_header_caps_hits_and_elements():
    r = await compile_and_run(r"""
#include "cpe_trace.hpp"
#include <iostream>
int main() {
    std::vector<int> big(100, 7);
    std::vector<std::vector<int>> grid(70, std::vector<int>(2, 1));
    int arr[100] = {0};
    int neg[1] = {0};
    for (int k = 0; k < 20; k++) {
        CPE_SNAP(3, k);
    }
    CPE_SNAP(4, big, grid, CPE_ARR(arr, 100), CPE_ARR(neg, -3));
    std::cout << "done\n";
}
""")
    assert (r.exit_code, r.stdout) == (0, "done\n")
    hits = [s for s in r.snapshots if s["id"] == 3]
    assert [s["hit"] for s in hits] == list(range(1, 13))
    assert [s["values"]["k"] for s in hits] == list(range(12))
    (capped,) = [s for s in r.snapshots if s["id"] == 4]
    assert capped["values"]["big"] == [7] * 64
    assert len(capped["values"]["grid"]) == 64
    assert capped["values"]["arr"] == [0] * 64
    assert capped["values"]["neg"] == []
    assert capped["truncated"] == ["big", "grid", "arr"]


async def test_recording_is_noop_without_trace_fd():
    r = await compile_and_run(r"""
#include "cpe_trace.hpp"
#include <cstdlib>
#include <iostream>
int main() {
    unsetenv("CPE_TRACE_FD");
    int x = 1;
    CPE_SNAP(1, x);
    std::cout << "ok\n";
}
""")
    assert (r.exit_code, r.stdout, r.snapshots) == (0, "ok\n", [])


async def test_forged_snapshot_lines_are_dropped():
    r = await compile_and_run(r"""
#include <cstdio>
#include <cstdlib>
int main() {
    FILE* f = fdopen(atoi(getenv("CPE_TRACE_FD")), "w");
    fputs("not json\n[1,2]\n{\"id\":\"1\",\"hit\":1,\"values\":{}}\n", f);
    for (int i = 0; i < 5000; i++) fputc('[', f);
    fputs("\n{\"id\":9,\"hit\":1,\"values\":{\"x\":1}}\n{\"id\":9,", f);
    return 0;
}
""")
    assert r.snapshots == [{"id": 9, "hit": 1, "values": {"x": 1}}]


# ── sandbox ──────────────────────────────────────────────────────────────────


async def test_wall_timeout_kills_process_group():
    start = time.monotonic()
    r = await compile_and_run(r"""
#include <iostream>
#include <unistd.h>
int main() {
    std::cout << getpid() << std::endl;
    for (;;) sleep(1);  // no CPU use: only the wall-clock timeout can stop it
}
""")
    assert r.timed_out and r.exit_code == -signal.SIGKILL
    assert time.monotonic() - start < 20
    with pytest.raises(ProcessLookupError):
        os.kill(int(r.stdout), 0)


async def test_cpu_bound_infinite_loop_is_stopped():
    r = await compile_and_run("int main() { volatile unsigned long x = 0; for (;;) x++; }")
    assert r.exit_code is not None and r.exit_code < 0
    assert r.timed_out or r.exit_code in (-signal.SIGXCPU, -signal.SIGKILL)


async def test_huge_stdout_is_truncated_but_drained():
    r = await compile_and_run(r"""
#include <cstdio>
int main() {
    for (int i = 0; i < 200000; i++) std::puts("0123456789012345678901234567890123456789");
    return 0;
}
""")
    assert r.stdout_truncated and not r.timed_out and r.exit_code == 0
    assert len(r.stdout) == 256 * 1024


async def test_backend_secrets_are_not_visible(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    r = await compile_and_run(r"""
#include <cstdlib>
#include <iostream>
extern char** environ;
int main() {
    const char* k = std::getenv("OPENAI_API_KEY");
    std::cout << (k ? k : "NULL") << "\n";
    for (char** e = environ; *e; e++) std::cout << *e << "\n";
}
""")
    lines = r.stdout.splitlines()
    assert lines[0] == "NULL"
    assert [line.split("=")[0] for line in lines[1:]] == ["CPE_TRACE_FD"]


async def test_fork_is_refused():
    # Bounded, and children exit at once: harmless even if the limit were missing.
    r = await compile_and_run(r"""
#include <iostream>
#include <sys/wait.h>
#include <unistd.h>
int main() {
    int ok = 0;
    for (int i = 0; i < 50; i++) {
        pid_t p = fork();
        if (p == 0) _exit(0);
        if (p > 0) { ok++; waitpid(p, nullptr, 0); }
    }
    std::cout << ok << "\n";
}
""")
    assert (r.exit_code, r.stdout) == (0, "0\n")


async def test_big_file_write_is_stopped_by_fsize():
    r = await compile_and_run(r"""
#include <cstdio>
#include <iostream>
int main() {
    FILE* f = std::fopen("big.bin", "wb");
    static char buf[1 << 16];
    for (int i = 0; i < 160; i++) std::fwrite(buf, 1, sizeof buf, f);  // 10 MB
    std::fclose(f);
    std::cout << "wrote all\n";
}
""")
    assert r.exit_code == -signal.SIGXFSZ
    assert "wrote all" not in r.stdout


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS does not enforce RLIMIT_AS")
async def test_memory_limit():
    r = await compile_and_run(r"""
#include <iostream>
#include <new>
#include <vector>
int main() {
    try { std::vector<char> v(1u << 30, 1); std::cout << v[12345] << "\n"; }
    catch (const std::bad_alloc&) { std::cout << "bad_alloc\n"; }
}
""")
    assert r.stdout == "bad_alloc\n"


@pytest.mark.skipif(os.name != "posix" or os.geteuid() != 0, reason="privilege drop only happens when running as root")
async def test_runs_as_unprivileged_uid_when_root():
    r = await compile_and_run(r"""
#include <fstream>
#include <iostream>
#include <unistd.h>
int main() {
    std::ifstream env("/proc/1/environ");
    std::cout << getuid() << " " << geteuid() << " " << env.is_open() << "\n";
}
""")
    assert r.stdout == f"{SANDBOX_UID} {SANDBOX_UID} 0\n"


async def test_compile_error_is_returned_and_trimmed():
    # long lines: clang stops after 20 errors, each must echo a long source line
    r = await compile_and_run("int main() {\n" + f"  int {'x' * 300} = ;\n" * 400 + "}\n")
    assert not r.compile.ok and r.exit_code is None
    assert "main.cpp:2" in r.compile.errors
    assert len(r.compile.errors) < 4200 and r.compile.errors.endswith("已截斷）")


async def test_nonzero_exit_code_and_stdin():
    r = await compile_and_run(
        "#include <iostream>\nint main() { int a, b; std::cin >> a >> b; std::cout << a + b; return 7; }",
        "2 40\n",
    )
    assert (r.exit_code, r.stdout, r.timed_out) == (7, "42", False)


async def test_oversized_input_is_rejected():
    with pytest.raises(TraceError):
        await compile_and_run("int main() {}", "x" * (2 * 1024 * 1024))


# ── equivalence / end to end ─────────────────────────────────────────────────


def _bubble_sort_source() -> str:
    files = sorted((REPO / "public" / "example-bubble_sort").glob("code*.cpp"))
    return files[-1].read_text(encoding="utf-8")


def _expected_bubble_states(arr: list[int]) -> list[list[int]]:
    states = []
    n = len(arr)
    for i in range(n - 1):
        for j in range(n - i - 1):
            states.append(list(arr))
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return states


async def test_bubble_sort_trace_is_equivalent_and_real():
    src = _bubble_sort_source()
    line = next(i for i, text in enumerate(src.split("\n"), 1) if "if (arr[j] > arr[j + 1])" in text)
    points = [{"id": 1, "line": line, "exprs": [{"expr": "arr", "length": "n"}, {"expr": "j"}]}]
    result = await run_trace(src, points, "")

    eq = result.equivalence
    assert eq.equivalent, (eq.traced.compile.errors, eq.traced.stderr)
    assert eq.matches_expected is None
    assert eq.original.stdout == eq.traced.stdout
    snaps = result.snapshots[1]
    expected = _expected_bubble_states([64, 34, 25, 12, 22, 11, 90])[:12]
    assert [s["values"]["arr"] for s in snaps] == expected
    assert [s["values"]["j"] for s in snaps] == [0, 1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 0]


async def test_equivalence_detects_changed_output_and_expected_mismatch():
    src = '#include <iostream>\nint main() { std::cout << "a  \\n\\n"; }'
    changed = '#include <iostream>\nint main() { std::cout << "b\\n"; }'
    eq = await check_equivalence(src, changed, "", expected_stdout="a\n")
    assert not eq.equivalent
    assert eq.matches_expected is True  # trailing spaces / blank lines ignored
    eq = await check_equivalence(src, src, "", expected_stdout="b")
    assert eq.equivalent and eq.matches_expected is False


PREFIX_SUM = """#include <iostream>
#include <vector>
using namespace std;

int main() {
    int n;
    cin >> n;
    vector<int> a(n);
    for (int i = 0; i < n; i++) cin >> a[i];
    long long sum = 0;
    for (int i = 0; i < n; i++) {
        sum += a[i];
    }
    cout << sum << endl;
    return 0;
}
"""


async def test_end_to_end_solution_reading_stdin():
    points = [{"id": 5, "line": 12, "exprs": [{"expr": "i"}, {"expr": "sum"}, {"expr": "a[i]"}, {"expr": "a"}]}]
    result = await run_trace(PREFIX_SUM, points, "5\n1 2 3 4 5\n", expected_stdout="15")
    eq = result.equivalence
    assert eq.equivalent and eq.matches_expected
    assert [s["values"]["sum"] for s in result.snapshots[5]] == [0, 1, 3, 6, 10]
    assert [s["values"]["a[i]"] for s in result.snapshots[5]] == [1, 2, 3, 4, 5]
    assert result.snapshots[5][0]["values"]["a"] == [1, 2, 3, 4, 5]
    assert "CPE_SNAP(5, i, sum, a[i], a);" in instrument(PREFIX_SUM, points)
