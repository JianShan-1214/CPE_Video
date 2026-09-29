"""Execute a user's C++ solution and record real variable snapshots at chosen lines."""

from .instrument import TraceError, TraceExpr, TracePoint, instrument
from .runner import (
    CompileResult,
    Equivalence,
    RunResult,
    TraceRun,
    check_equivalence,
    compile_and_run,
    find_compiler,
    run_trace,
)

__all__ = [
    "CompileResult",
    "Equivalence",
    "RunResult",
    "TraceError",
    "TraceExpr",
    "TracePoint",
    "TraceRun",
    "check_equivalence",
    "compile_and_run",
    "find_compiler",
    "instrument",
    "run_trace",
]
