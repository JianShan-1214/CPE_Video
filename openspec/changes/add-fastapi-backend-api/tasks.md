---
change: add-fastapi-backend-api
status: done
agent: Codex
updated: 2026-05-29
progress: 6/6
---

# Tasks：add-fastapi-backend-api

## 檔案結構

| 動作 | 檔案路徑 | 職責 |
|------|---------|------|
| 新增 | `backend/` | FastAPI app、schemas、routers、services、tests |
| 修改 | `web/src/lib/` | API client 與 backend-backed job hooks |
| 修改 | `web/src/pages/`, `web/src/components/ExportDialog.tsx` | 改用 backend APIs |
| 修改 | `web/vite.config.ts` | 移除 render middleware 責任 |

## Tasks

- [x] 1. 建立 OpenSpec artifacts 與 backend Python 專案骨架
- [x] 2. 實作 FastAPI health、SQLite 初始化、Job CRUD/import API
- [x] 3. 實作 mock generation provider 與 `/api/generate-draft`
- [x] 4. 實作 render job API、背景 render service、download endpoint
- [x] 5. 前端改用 API client 取代 localStorage 與 Vite render endpoint
- [x] 6. 跑完整驗證並更新 task 進度
