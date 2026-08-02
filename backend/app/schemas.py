from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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

    model_config = ConfigDict(populate_by_name=True)


class JobCreateRequest(BaseModel):
    name: str | None = None


class JobUpdateRequest(BaseModel):
    name: str
    theme: Theme
    width: WidthConfig
    steps: list[DraftStep]


class JobResponse(BaseModel):
    id: str
    name: str
    createdAt: int
    updatedAt: int
    theme: Theme
    width: WidthConfig
    steps: list[DraftStep]


class ImportJobRequest(BaseModel):
    configJson: str
    cppFiles: dict[str, str]
    name: str | None = None


class GenerateDraftRequest(BaseModel):
    name: str | None = None
    problemStatement: str
    solutionCode: str


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
