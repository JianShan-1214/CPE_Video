from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_serializer, model_validator


HighlightPreset = Literal["blue", "yellow", "red", "green", "lightblue"]
AnnotationTheme = Literal["blue", "yellow", "green", "red"]
# Keep in sync with ``themeSchema`` in src/calculate-metadata/theme.tsx — the
# editor's theme picker offers every value listed there.
Theme = Literal[
    "dark-plus",
    "dracula-soft",
    "dracula",
    "github-dark",
    "github-dark-dimmed",
    "github-light",
    "light-plus",
    "material-darker",
    "material-default",
    "material-lighter",
    "material-ocean",
    "material-palenight",
    "min-dark",
    "min-light",
    "monokai",
    "nord",
    "one-dark-pro",
    "poimandres",
    "slack-dark",
    "slack-ochin",
    "solarized-dark",
    "solarized-light",
]
RenderStatus = Literal["queued", "running", "succeeded", "failed"]


class HighlightPresetConfig(BaseModel):
    startLine: int = Field(ge=1)
    endLine: int = Field(ge=1)
    color: HighlightPreset


class HighlightCustomConfig(BaseModel):
    startLine: int = Field(ge=1)
    endLine: int = Field(ge=1)
    bgColor: str
    borderColor: str


HighlightConfig = HighlightPresetConfig | HighlightCustomConfig


class Annotation(BaseModel):
    targetLine: int = Field(ge=1)
    text: str
    startTime: float = Field(ge=0)
    theme: AnnotationTheme | None = None


class FixedWidth(BaseModel):
    type: Literal["fixed"]
    value: int


class AutoWidth(BaseModel):
    type: Literal["auto"]


WidthConfig = FixedWidth | AutoWidth


# Optional per-step algorithm animation; mirrors ``StepAnimation`` in
# src/config-types.ts. Only the shape is enforced here — size limits are
# reported by ``validate_draft`` so the editor can show them instead of a 422.
AnimationValue = int | FiniteFloat | str


class _OmitNone(BaseModel):
    # The renderer treats ``caption: null`` etc. as invalid and drops the whole
    # animation, so optional fields are omitted instead of sent as null.
    @model_serializer(mode="wrap")
    def _omit_none(self, handler):
        return {k: v for k, v in handler(self).items() if v is not None}


# Variable-table values; the renderer shows null as an empty cell.
VarValue = bool | int | FiniteFloat | str | None
AnimationVars = dict[str, VarValue]  # ≤ 8 entries, reported by validate_draft


class ArrayFrame(_OmitNone):
    values: list[AnimationValue]
    pointers: dict[str, int] | None = None
    mark: list[int] | None = None
    caption: str | None = None
    vars: AnimationVars | None = None


class ArrayAnimation(BaseModel):
    type: Literal["array"]
    frames: list[ArrayFrame]


class StacksFrame(_OmitNone):
    stacks: list[list[AnimationValue]]
    caption: str | None = None
    vars: AnimationVars | None = None


class StacksAnimation(_OmitNone):
    type: Literal["stacks"]
    labels: list[str] | None = None
    frames: list[StacksFrame]


class GridFrame(_OmitNone):
    cells: list[list[VarValue]]
    mark: list[tuple[int, int]] | None = None
    caption: str | None = None
    vars: AnimationVars | None = None


class GridAnimation(BaseModel):
    type: Literal["grid"]
    frames: list[GridFrame]


class VarsFrame(_OmitNone):
    vars: AnimationVars
    caption: str | None = None


class VarsAnimation(BaseModel):
    type: Literal["vars"]
    frames: list[VarsFrame]


StepAnimation = Annotated[
    ArrayAnimation | StacksAnimation | GridAnimation | VarsAnimation, Field(discriminator="type")
]


# The LLM's trace plan for a step: the backend runs the real program and builds
# ``animation`` from snapshots taken before/after ``line``. Also the strict-mode AI
# schema, so no free-key dicts and no non-None defaults.
class TraceShow(BaseModel):
    as_: Literal["array", "grid", "stacks", "queue", "vars"] = Field(alias="as")
    expr: str | None = None
    length: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class StepTrace(BaseModel):
    line: int = Field(ge=1)  # 1-based, in this step's fileContent; must be a line this step adds
    show: TraceShow
    pointers: list[str]
    vars: list[str]
    maxFrames: int = Field(ge=1, le=12)
    caption: str | None = None
    when: Literal["before", "after"]  # snapshot runs before / after ``line`` executes

    @model_validator(mode="before")
    @classmethod
    def _default_when(cls, data):
        # Stored plans predate ``when``. Not a field default: strict mode rejects those.
        if isinstance(data, dict) and "when" not in data:
            return {**data, "when": "before"}
        return data


class DraftStep(BaseModel):
    label: str
    from_: float = Field(alias="from")
    to: float
    fileLabel: str
    fileContent: str
    subtitle: str
    focusLine: int | None = Field(default=None, ge=1)
    highlight: HighlightConfig | None = None
    annotations: list[Annotation] | None = None
    animation: StepAnimation | None = None
    trace: StepTrace | None = None

    model_config = ConfigDict(populate_by_name=True)


class CheckedDraftStep(DraftStep):
    # Bounds live only on the check request: stored jobs may already exceed them.
    fileContent: str = Field(max_length=50_000)
    subtitle: str = Field(max_length=1_000)


class JobCreateRequest(BaseModel):
    name: str | None = None


class JobUpdateRequest(BaseModel):
    name: str
    theme: Theme
    width: WidthConfig
    steps: list[DraftStep]
    sampleInput: str = ""
    sampleOutput: str = ""


class JobResponse(BaseModel):
    id: str
    name: str
    createdAt: int
    updatedAt: int
    theme: Theme
    width: WidthConfig
    steps: list[DraftStep]
    sampleInput: str = ""
    sampleOutput: str = ""


class ImportJobRequest(BaseModel):
    configJson: str
    cppFiles: dict[str, str]
    name: str | None = None


class GenerateDraftRequest(BaseModel):
    name: str | None = None
    problemStatement: str
    solutionCode: str
    withAnimation: bool = False
    sampleInput: str = ""
    sampleOutput: str = ""


class ProblemStatementRequest(BaseModel):
    uvaId: int = Field(ge=100, le=99999)


class ProblemStatementResponse(BaseModel):
    uvaId: int
    problemStatement: str
    sampleInput: str = ""
    sampleOutput: str = ""


class DraftCheckRequest(BaseModel):
    steps: list[CheckedDraftStep] = Field(min_length=1, max_length=60)
    ai: bool = True


class DraftCheckIssue(BaseModel):
    stepIndex: int | None
    level: Literal["error", "warning"]
    message: str
    source: Literal["rule", "ai"]


class DraftCheckResponse(BaseModel):
    issues: list[DraftCheckIssue]


class DraftTraceRequest(BaseModel):
    steps: list[CheckedDraftStep] = Field(min_length=1, max_length=60)
    sampleInput: str = ""
    sampleOutput: str = ""


class DraftTraceResponse(BaseModel):
    steps: list[DraftStep]
    issues: list[DraftCheckIssue]


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


class RenderJobCreateRequest(BaseModel):
    jobId: str
    folderName: str | None = None


class RenderJobCreateResponse(BaseModel):
    id: str
    status: RenderStatus


class RenderJobResponse(BaseModel):
    id: str
    jobId: str
    status: RenderStatus
    progress: float | None = None
    error: str | None = None
    outputFilename: str | None = None
    createdAt: int
    updatedAt: int
