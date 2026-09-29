## 為什麼

目前 web editor 的主要資料存在 localStorage，MP4 render 則依賴 Vite dev middleware。這讓資料無法跨瀏覽器持久化，也讓 render API 只能在開發伺服器中運作。

## 變更內容

- 新增 FastAPI backend，承接 Job CRUD、import、mock AI 草稿生成、背景 MP4 render。
- 使用 SQLite 持久化 jobs 與 render jobs。
- 前端改用 `VITE_API_BASE_URL` 呼叫 backend API。
- 保留現有 Remotion 預覽與 audio CLI。

## 能力範圍

### 新增能力
- `backend-video-api`：提供影片 job 管理、草稿生成、背景 render API。

### 修改能力
- 無。

## 影響範圍
- 影響的 specs：`backend-video-api`
- 影響的 code：`backend/`, `web/src/lib/`, `web/src/pages/`, `web/src/components/ExportDialog.tsx`, `web/vite.config.ts`
