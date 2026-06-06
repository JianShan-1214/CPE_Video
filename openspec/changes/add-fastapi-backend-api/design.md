# Design：add-fastapi-backend-api

## 概述

新增獨立 FastAPI API server，讓 web editor 從 localStorage/Vite middleware 過渡到持久化 backend。前端仍由 Vite 獨立提供，backend 只提供 API。

## 架構

```
web editor ── HTTP JSON/blob ── FastAPI
                                  ├─ SQLite jobs/render_jobs
                                  ├─ MockGeneratorProvider
                                  └─ Remotion CLI subprocess
```

## 關鍵決策

| 決策 | 選擇 | 理由 |
|------|------|------|
| Backend framework | FastAPI + Pydantic V2 | 產生 OpenAPI，適合 async endpoints |
| Persistence | SQLite + async SQLAlchemy | 單機部署簡單，測試容易 |
| Step storage | JSON column as text | v1 保持目前 `Job` shape，避免過早拆 schema |
| Render | BackgroundTasks + render job status | 避免長 HTTP request timeout |
| AI generation | Mock provider adapter | 保持現有 mock 行為，保留替換真模型的邊界 |
| Frontend deploy | Vite standalone | backend v1 不 serve web build |

## 整合點

- 前端新增 API client，取代 localStorage CRUD 與 `/api/render-mp4`。
- Backend render service 寫入 `public/__render_*` 後呼叫 `npx remotion render`。
- `scripts/gen-audio.mjs` 暫不移植。

## 開放問題

- 真 AI provider 與 prompt/schema 留待後續 change。
- 多使用者、登入、API key 留待部署需要時再設計。
