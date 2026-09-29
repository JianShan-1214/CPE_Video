import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.routers import generation
from app.services.problem_service import MAX_PDF_BYTES, ProblemFetchError, fetch_uva_pdf
from app.settings import Settings

PDF = b"%PDF-1.4 fake"


def _transport(status: int = 200, body: bytes = PDF, seen: list[str] | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(str(request.url))
        return httpx.Response(status, content=body)

    return httpx.MockTransport(handler)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("problem_id", "url"),
    [
        (101, "https://onlinejudge.org/external/1/101.pdf"),
        (10038, "https://onlinejudge.org/external/100/10038.pdf"),
    ],
)
async def test_fetch_builds_url(problem_id, url):
    seen: list[str] = []
    assert await fetch_uva_pdf(problem_id, transport=_transport(seen=seen)) == PDF
    assert seen == [url]


@pytest.mark.anyio
async def test_fetch_404_message():
    with pytest.raises(ProblemFetchError, match="找不到 UVa 101") as info:
        await fetch_uva_pdf(101, transport=_transport(status=404))
    assert info.value.status_code == 404


@pytest.mark.anyio
async def test_fetch_other_status_is_502():
    with pytest.raises(ProblemFetchError) as info:
        await fetch_uva_pdf(101, transport=_transport(status=500))
    assert info.value.status_code == 502


@pytest.mark.anyio
async def test_fetch_rejects_non_pdf():
    with pytest.raises(ProblemFetchError, match="不是 PDF"):
        await fetch_uva_pdf(101, transport=_transport(body=b"<html>nope</html>"))


@pytest.mark.anyio
async def test_fetch_rejects_oversized():
    with pytest.raises(ProblemFetchError, match="5 MB"):
        await fetch_uva_pdf(101, transport=_transport(body=PDF + b"0" * MAX_PDF_BYTES))


@pytest.mark.anyio
async def test_fetch_does_not_follow_redirects():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/"})

    with pytest.raises(ProblemFetchError, match="重新導向") as info:
        await fetch_uva_pdf(101, transport=httpx.MockTransport(handler))
    assert info.value.status_code == 502
    assert seen == ["https://onlinejudge.org/external/1/101.pdf"]


@pytest.mark.anyio
async def test_fetch_overall_deadline(monkeypatch):
    import anyio

    from app.services import problem_service

    monkeypatch.setattr(problem_service, "FETCH_DEADLINE_SECONDS", 0.2)

    async def drip():
        yield b"%PDF"
        while True:  # each chunk arrives well within the per-read timeout
            await anyio.sleep(0.05)
            yield b"0"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=drip())

    with anyio.fail_after(5):  # guard: the test itself must not hang
        with pytest.raises(ProblemFetchError, match="逾時") as info:
            await fetch_uva_pdf(101, transport=httpx.MockTransport(handler))
    assert info.value.status_code == 502


@pytest.mark.anyio
@pytest.mark.parametrize("bad", [99, 100000, True, "101"])
async def test_fetch_rejects_invalid_id(bad):
    with pytest.raises(ValueError):
        await fetch_uva_pdf(bad, transport=_transport())


@pytest.fixture
async def client(tmp_path):
    settings = Settings(database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", project_root=tmp_path)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
            yield test_client


@pytest.mark.anyio
async def test_problem_statement_endpoint(client, monkeypatch):
    async def fake_fetch(problem_id):
        return PDF

    monkeypatch.setattr(generation, "fetch_uva_pdf", fake_fetch)
    response = await client.post("/api/problem-statement", json={"uvaId": 101})
    assert response.status_code == 200
    body = response.json()
    assert body["uvaId"] == 101
    assert "UVa 101" in body["problemStatement"]


@pytest.mark.anyio
async def test_problem_statement_endpoint_errors(client, monkeypatch):
    assert (await client.post("/api/problem-statement", json={"uvaId": 5})).status_code == 422

    async def missing(problem_id):
        raise ProblemFetchError(f"找不到 UVa {problem_id}", 404)

    monkeypatch.setattr(generation, "fetch_uva_pdf", missing)
    response = await client.post("/api/problem-statement", json={"uvaId": 99999})
    assert response.status_code == 404
    assert response.json()["detail"] == "找不到 UVa 99999"


@pytest.mark.anyio
async def test_openai_summarize_sends_pdf_file_part(monkeypatch):
    import base64
    from types import SimpleNamespace

    import openai

    from app.services.generation_service import OpenAIGeneratorProvider

    captured = {}

    class FakeClient:
        def __init__(self, api_key, **client_kwargs):
            captured["client"] = client_kwargs

            async def create(**kwargs):
                captured.update(kwargs)
                message = SimpleNamespace(content=" 題意：... \n")
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])

            self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))

    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)
    text = await OpenAIGeneratorProvider(api_key="k", model="m").summarize_problem(PDF, 101)

    assert text == "題意：..."
    assert captured["client"] == {"timeout": 120, "max_retries": 1}
    file_part = captured["messages"][0]["content"][1]
    assert file_part == {
        "type": "file",
        "file": {"filename": "101.pdf", "file_data": "data:application/pdf;base64," + base64.b64encode(PDF).decode()},
    }
