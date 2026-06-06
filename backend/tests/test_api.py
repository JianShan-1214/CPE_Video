import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture
async def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        project_root=tmp_path,
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client


def sample_step(file_label: str = "code01.cpp", content: str = "int main() {}\n"):
    return {
        "label": "Intro",
        "from": 0,
        "to": 5,
        "fileLabel": file_label,
        "fileContent": content,
        "subtitle": "Hello",
        "highlight": {"startLine": 1, "endLine": 1, "color": "blue"},
    }


@pytest.mark.anyio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.anyio
async def test_job_crud_orders_by_updated_at(client):
    first = (await client.post("/api/jobs", json={"name": "First"})).json()
    second = (await client.post("/api/jobs", json={"name": "Second"})).json()

    assert first["name"] == "First"
    assert first["steps"] == []

    update_payload = {
        **first,
        "name": "First Updated",
        "steps": [sample_step()],
    }
    updated = await client.put(f"/api/jobs/{first['id']}", json=update_payload)
    assert updated.status_code == 200
    assert updated.json()["name"] == "First Updated"
    assert updated.json()["updatedAt"] >= first["updatedAt"]

    listed = await client.get("/api/jobs")
    assert listed.status_code == 200
    names = [job["name"] for job in listed.json()]
    assert names == ["First Updated", "Second"]

    fetched = await client.get(f"/api/jobs/{first['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["steps"][0]["fileLabel"] == "code01.cpp"

    deleted = await client.delete(f"/api/jobs/{second['id']}")
    assert deleted.status_code == 204
    missing = await client.get(f"/api/jobs/{second['id']}")
    assert missing.status_code == 404


@pytest.mark.anyio
async def test_import_rejects_missing_cpp_and_accepts_valid_config(client):
    config_json = '{"steps":[{"label":"A","from":0,"to":3,"file":"code01.cpp","subtitle":"Hi"}]}'

    missing = await client.post(
        "/api/jobs/import",
        json={"configJson": config_json, "cppFiles": {}, "name": "Import"},
    )
    assert missing.status_code == 400
    assert "找不到 cpp 檔" in missing.json()["detail"]

    imported = await client.post(
        "/api/jobs/import",
        json={
            "configJson": config_json,
            "cppFiles": {"code01.cpp": "int main() {}\n"},
            "name": "Import",
        },
    )
    assert imported.status_code == 201
    body = imported.json()
    assert body["name"] == "Import"
    assert body["steps"][0]["fileContent"] == "int main() {}\n"


@pytest.mark.anyio
async def test_generate_draft_creates_editable_job(client):
    response = await client.post(
        "/api/generate-draft",
        json={
            "name": "A plus B",
            "problemStatement": "輸入兩個整數，輸出總和。",
            "solutionCode": "#include <iostream>\nint main(){return 0;}\n",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "A plus B"
    assert len(body["steps"]) >= 4
    assert body["steps"][-1]["focusLine"] == 1


@pytest.mark.anyio
async def test_render_job_rejects_empty_and_download_before_success(client):
    job = (await client.post("/api/jobs", json={"name": "Empty"})).json()
    rejected = await client.post("/api/render-jobs", json={"jobId": job["id"]})
    assert rejected.status_code == 400

    update_payload = {**job, "steps": [sample_step()]}
    job = (await client.put(f"/api/jobs/{job['id']}", json=update_payload)).json()

    created = await client.post("/api/render-jobs", json={"jobId": job["id"]})
    assert created.status_code == 201
    render_job = created.json()
    assert render_job["status"] == "queued"

    status = await client.get(f"/api/render-jobs/{render_job['id']}")
    assert status.status_code == 200
    assert status.json()["status"] in {"queued", "running", "failed", "succeeded"}

    download = await client.get(f"/api/render-jobs/{render_job['id']}/download")
    if status.json()["status"] != "succeeded":
        assert download.status_code in {409, 400}


@pytest.mark.anyio
async def test_auth_guards_protected_routes_when_password_set(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}",
        project_root=tmp_path,
        auth_password="s3cret",
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            assert (await c.get("/api/auth/status")).json() == {"authRequired": True}
            # health stays open
            assert (await c.get("/health")).status_code == 200
            # OpenAPI docs are hidden when auth is enabled
            assert (await c.get("/openapi.json")).status_code == 404
            # protected routes require a token
            assert (await c.get("/api/jobs")).status_code == 401
            # wrong password is rejected
            assert (await c.post("/api/login", json={"password": "nope"})).status_code == 401
            # correct password yields a working token
            login = await c.post("/api/login", json={"password": "s3cret"})
            assert login.status_code == 200
            token = login.json()["token"]
            assert token
            ok = await c.get("/api/jobs", headers={"Authorization": f"Bearer {token}"})
            assert ok.status_code == 200
            # a bogus token is rejected
            bad = await c.get("/api/jobs", headers={"Authorization": "Bearer wrong"})
            assert bad.status_code == 401
