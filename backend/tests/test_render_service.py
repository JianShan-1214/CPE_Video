import pytest

from app.schemas import JobResponse
from app.services.render_service import build_render_files, build_render_props


def make_job(steps, theme="github-dark", width=None):
    return JobResponse(
        id="job-1",
        name="Render",
        createdAt=1,
        updatedAt=1,
        theme=theme,
        width=width or {"type": "fixed", "value": 1920},
        steps=steps,
    )


def test_build_render_props_carries_job_theme_and_width():
    job = make_job([], theme="nord", width={"type": "auto"})

    assert build_render_props(job, "__render_x_1") == {
        "folder": "__render_x_1",
        "theme": "nord",
        "width": {"type": "auto"},
    }


def test_build_render_files_rejects_conflicting_duplicate_file_labels():
    job = make_job(
        [
            {
                "label": "A",
                "from": 0,
                "to": 1,
                "fileLabel": "code01.cpp",
                "fileContent": "a\n",
                "subtitle": "A",
            },
            {
                "label": "B",
                "from": 1,
                "to": 2,
                "fileLabel": "code01.cpp",
                "fileContent": "b\n",
                "subtitle": "B",
            },
        ],
    )

    with pytest.raises(ValueError, match="同一個 cpp 檔名有不同內容"):
        build_render_files(job, "Render")
