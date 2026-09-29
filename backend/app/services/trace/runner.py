"""Compile and run untrusted C++ under resource limits.

Guarantees (see tests/test_trace_sandbox.py):
- no shell; argv lists only; fresh temp dir per run, removed afterwards
- child env is empty except CPE_TRACE_FD (run) / PATH+TMPDIR (compile), so the
  backend's secrets (OPENAI_API_KEY, AUTH_PASSWORD, ...) are not inherited
- own session/process group, SIGKILLed as a group on wall-clock timeout
- rlimits: CPU, FSIZE, CORE=0, NPROC=1 (no fork/threads), AS (Linux only:
  macOS rejects RLIMIT_AS, so memory is unbounded there)
- when the backend runs as root (the Docker image does), compiler and program
  run as an unprivileged uid so they cannot read root-only files or
  /proc/<backend pid>/environ, cannot signal the backend, and RLIMIT_NPROC
  (ignored for root) applies
- output caps: excess stdout/stderr/snapshot bytes are drained and dropped
NOT provided: network isolation, filesystem isolation beyond Unix permissions.
"""

import json
import os
import resource
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import anyio

from .instrument import TraceError, TracePoint, instrument

HEADER_PATH = Path(__file__).with_name("cpe_trace.hpp")
COMPILE_TIMEOUT_SEC = 20.0
RUN_TIMEOUT_SEC = 3.0
MAX_SOURCE_BYTES = 256 * 1024
MAX_STDIN_BYTES = 1024 * 1024
STDOUT_CAP = 256 * 1024
STDERR_CAP = 16 * 1024
SNAPSHOT_CAP = 2 * 1024 * 1024
COMPILE_ERROR_CAP = 4096
# Used only when the backend is root. No passwd entry needed; must not be a uid
# anything else in the container runs as (RLIMIT_NPROC counts per uid).
SANDBOX_UID = 61000

_MB = 1024 * 1024
_RUN_LIMITS = (
    (resource.RLIMIT_CPU, 3),
    (resource.RLIMIT_AS, 512 * _MB),
    (resource.RLIMIT_FSIZE, 1 * _MB),
    (resource.RLIMIT_NPROC, 1),  # the program itself; fork()/threads fail
    (resource.RLIMIT_CORE, 0),
)
_COMPILE_LIMITS = (  # the compiler driver forks cc1plus/as/ld, so no NPROC here
    (resource.RLIMIT_CPU, int(COMPILE_TIMEOUT_SEC)),
    (resource.RLIMIT_AS, 2048 * _MB),
    (resource.RLIMIT_FSIZE, 64 * _MB),
    (resource.RLIMIT_CORE, 0),
)

# ponytail: one sandbox job at a time per process (threading lock works across
# event loops); use a small pool if throughput ever matters.
_run_lock = threading.Lock()


@dataclass
class CompileResult:
    ok: bool
    errors: str = ""  # compiler diagnostics, trimmed to COMPILE_ERROR_CAP chars
    timed_out: bool = False


@dataclass
class RunResult:
    compile: CompileResult
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None  # None if not run; negative = killed by that signal
    snapshots: list[dict] = field(default_factory=list)
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    snapshots_truncated: bool = False


@dataclass
class Equivalence:
    equivalent: bool
    matches_expected: bool | None
    original: RunResult
    traced: RunResult


@dataclass
class TraceRun:
    instrumented_source: str
    equivalence: Equivalence
    snapshots: dict[int, list[dict]]  # point id -> snapshots in execution order


def find_compiler() -> str:
    override = os.environ.get("CPE_CXX")
    if override:
        path = shutil.which(override)
        if not path:
            raise TraceError(f"CPE_CXX 指定的編譯器找不到：{override}")
        return path
    names = ["g++", "c++", "clang++"]
    if sys.platform == "darwin":  # Apple's g++ is clang; prefer a real Homebrew GCC
        names = [f"g++-{v}" for v in range(20, 8, -1)] + ["clang++", "g++"]
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    raise TraceError("伺服器沒有 C++ 編譯器")


def _limiter(limits):
    def apply() -> None:  # runs in the child between fork and exec
        for res, value in limits:
            hard = resource.getrlimit(res)[1]
            if hard != resource.RLIM_INFINITY:
                value = min(value, hard)
            try:
                resource.setrlimit(res, (value, value))
            except (ValueError, OSError):
                if not (res == resource.RLIMIT_AS and sys.platform == "darwin"):
                    raise

    return apply


def _privilege_drop() -> dict:
    # Popen switches uid/gid before preexec_fn, so the rlimits (NPROC) apply to the new uid.
    if os.geteuid() == 0:
        return {"user": SANDBOX_UID, "group": SANDBOX_UID, "extra_groups": []}
    return {}


def _execute(argv, *, cwd, env, stdin, timeout, limits, caps, trace=False):
    """Run argv; returns (returncode, timed_out, {stream: bytes}, {stream: truncated})."""
    trace_r = trace_w = None
    if trace:
        trace_r, trace_w = os.pipe()
        env = {**env, "CPE_TRACE_FD": str(trace_w)}
    try:
        try:
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(trace_w,) if trace else (),
                start_new_session=True,
                # CPython re-inits its own locks after fork and the hook only calls setrlimit.
                # ponytail: residual deadlock risk from C locks held by other threads; an
                # exec trampoline (prlimit / tiny launcher) removes it if it ever shows up.
                preexec_fn=_limiter(limits),  # noqa: PLW1509
                **_privilege_drop(),
            )
        finally:
            if trace_w is not None:
                os.close(trace_w)
        streams = {proc.stdout.fileno(): "stdout", proc.stderr.fileno(): "stderr"}
        if trace:
            streams[trace_r] = "snapshots"
        data = {name: bytearray() for name in streams.values()}
        truncated = dict.fromkeys(streams.values(), False)
        deadline = time.monotonic() + timeout
        timed_out = False
        with selectors.DefaultSelector() as sel:
            for fd in streams:
                sel.register(fd, selectors.EVENT_READ)
            while sel.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                for key, _ in sel.select(remaining):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        sel.unregister(key.fd)
                        continue
                    name = streams[key.fd]
                    room = caps[name] - len(data[name])
                    if len(chunk) > room:
                        truncated[name] = True
                    data[name] += chunk[: max(room, 0)]  # keep draining so the child never blocks
        if not timed_out:
            try:
                proc.wait(max(deadline - time.monotonic(), 0))
            except subprocess.TimeoutExpired:
                timed_out = True
        if timed_out:
            # The leader is not reaped yet, so its pgid cannot have been recycled.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        proc.stdout.close()
        proc.stderr.close()
        return proc.returncode, timed_out, {k: bytes(v) for k, v in data.items()}, truncated
    finally:
        if trace_r is not None:
            os.close(trace_r)


def _parse_snapshots(raw: bytes, truncated: bool) -> list[dict]:
    """Snapshot lines are written by untrusted code: parse defensively, drop junk."""
    lines = raw.split(b"\n")
    if truncated or lines[-1]:
        lines = lines[:-1]  # partial last line
    snaps = []
    for line in lines:
        try:
            snap = json.loads(line.decode("utf-8", "replace"))
        except (ValueError, RecursionError):
            continue
        if (
            isinstance(snap, dict)
            and type(snap.get("id")) is int
            and type(snap.get("hit")) is int
            and isinstance(snap.get("values"), dict)
        ):
            snaps.append(snap)
    return snaps


def _trim(text: str, cap: int) -> str:
    return text if len(text) <= cap else text[:cap] + "\n…（訊息過長，已截斷）"


def _compile_and_run_sync(source: str, stdin: str) -> RunResult:
    if len(source.encode()) > MAX_SOURCE_BYTES:
        raise TraceError(f"程式碼超過 {MAX_SOURCE_BYTES // 1024} KB")
    stdin_bytes = stdin.encode()
    if len(stdin_bytes) > MAX_STDIN_BYTES:
        raise TraceError(f"輸入資料超過 {MAX_STDIN_BYTES // _MB} MB")
    compiler = find_compiler()
    with _run_lock, tempfile.TemporaryDirectory(prefix="cpe-trace-", ignore_cleanup_errors=True) as tmp:
        src, header, exe = (os.path.join(tmp, n) for n in ("main.cpp", "cpe_trace.hpp", "prog"))
        Path(src).write_text(source, encoding="utf-8")
        shutil.copyfile(HEADER_PATH, header)
        if os.geteuid() == 0:
            for path in (tmp, src, header):
                os.chown(path, SANDBOX_UID, SANDBOX_UID)

        code, timed_out, out, _ = _execute(
            [compiler, "-std=c++17", "-O0", "-o", "prog", "main.cpp"],
            cwd=tmp,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "TMPDIR": tmp},
            stdin=subprocess.DEVNULL,
            timeout=COMPILE_TIMEOUT_SEC,
            limits=_COMPILE_LIMITS,
            caps={"stdout": COMPILE_ERROR_CAP, "stderr": 64 * 1024},
        )
        errors = (out["stderr"] + out["stdout"]).decode("utf-8", "replace")
        if timed_out:
            errors = f"編譯逾時（超過 {COMPILE_TIMEOUT_SEC:g} 秒）\n" + errors
        compiled = CompileResult(
            ok=code == 0 and not timed_out, errors=_trim(errors, COMPILE_ERROR_CAP), timed_out=timed_out
        )
        if not compiled.ok:
            return RunResult(compile=compiled)

        # Anonymous file: no path the child (or anything else) could swap out.
        with tempfile.TemporaryFile() as stdin_file:
            stdin_file.write(stdin_bytes)
            stdin_file.seek(0)
            code, timed_out, out, cut = _execute(
                [exe],
                cwd=tmp,
                env={},
                stdin=stdin_file,
                timeout=RUN_TIMEOUT_SEC,
                limits=_RUN_LIMITS,
                caps={"stdout": STDOUT_CAP, "stderr": STDERR_CAP, "snapshots": SNAPSHOT_CAP},
                trace=True,
            )
    return RunResult(
        compile=compiled,
        stdout=out["stdout"].decode("utf-8", "replace"),
        stderr=out["stderr"].decode("utf-8", "replace"),
        exit_code=code,
        snapshots=_parse_snapshots(out["snapshots"], cut["snapshots"]),
        timed_out=timed_out,
        stdout_truncated=cut["stdout"],
        stderr_truncated=cut["stderr"],
        snapshots_truncated=cut["snapshots"],
    )


async def compile_and_run(source: str, stdin: str = "") -> RunResult:
    """Compile ``source`` and run it on ``stdin`` in a worker thread (never blocks the loop)."""
    return await anyio.to_thread.run_sync(_compile_and_run_sync, source, stdin)


def _normalize(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _complete(result: RunResult) -> bool:
    return result.compile.ok and not result.timed_out and not result.stdout_truncated


async def check_equivalence(
    original_source: str, instrumented_source: str, stdin: str, expected_stdout: str | None = None
) -> Equivalence:
    original = await compile_and_run(original_source, stdin)
    traced = await compile_and_run(instrumented_source, stdin)
    equivalent = (
        _complete(original)
        and _complete(traced)
        and original.stdout == traced.stdout
        and original.exit_code == traced.exit_code
    )
    matches = None
    if expected_stdout is not None:
        matches = _complete(original) and _normalize(original.stdout) == _normalize(expected_stdout)
    return Equivalence(equivalent=equivalent, matches_expected=matches, original=original, traced=traced)


async def run_trace(source: str, points: list[TracePoint], stdin: str, expected_stdout: str | None = None) -> TraceRun:
    """Instrument, run original + traced, and group the traced snapshots by point id.
    Callers must check ``equivalence.equivalent`` before trusting the snapshots."""
    instrumented = instrument(source, points)
    eq = await check_equivalence(source, instrumented, stdin, expected_stdout)
    by_id: dict[int, list[dict]] = {p["id"]: [] for p in points}
    for snap in eq.traced.snapshots:
        if snap["id"] in by_id:  # ids not in the plan can only be forged by the program
            by_id[snap["id"]].append(snap)
    return TraceRun(instrumented_source=instrumented, equivalence=eq, snapshots=by_id)
