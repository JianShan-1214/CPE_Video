# 部署指南（Zeabur）

CPE Video 以**單一 Docker image** 上線：FastAPI 後端同時提供 API、執行 Remotion render、
產生語音，並 serve 已 build 的 web 編輯器（同一個網域，無 CORS 問題）。

```
瀏覽器 ──HTTPS──> Zeabur ──> 容器
                              ├─ FastAPI (API + 靜態前端)
                              ├─ SQLite（jobs / render jobs）
                              ├─ OpenAI（草稿生成）
                              ├─ Remotion CLI + Chrome Headless（render MP4）
                              └─ gen-audio.mjs + GCP TTS（語音旁白）
```

---

## 一、環境變數

| 變數 | 必填 | 預設 | 說明 |
|------|------|------|------|
| `AUTH_PASSWORD` | 建議 | （空＝不啟用登入） | 共用存取密碼。設了之後所有 `/api` 都需登入。 |
| `OPENAI_API_KEY` | 是 | — | 沒設會 fallback 到 mock 生成（罐頭文字）。 |
| `OPENAI_MODEL` | 否 | `gpt-4o-mini` | 想要更好品質可設 `gpt-4o`。 |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | 語音需要 | — | GCP 服務帳戶金鑰的**完整 JSON 內容**；啟動時會寫成檔案。 |
| `GOOGLE_APPLICATION_CREDENTIALS` | 語音需要（本機） | — | 金鑰**檔案路徑**（本機 .env 用這個；雲端用上面的 JSON 版）。 |
| `RENDER_REQUIRE_AUDIO` | 否 | `false` | `true` 時語音失敗就讓 render 失敗；預設失敗則 render 無聲版。 |
| `RENDER_TIMEOUT_SEC` | 否 | `1800` | 單支 render 逾時秒數。 |
| `DATA_DIR` | 雲端建議 | `backend/data` | SQLite 與金鑰檔位置；雲端請指到 volume。 |
| `OUTPUT_DIR` | 雲端建議 | `<repo>/out` | 輸出 MP4 位置；雲端請指到 volume。 |
| `DATABASE_URL` | 否 | `sqlite+aiosqlite:///<DATA_DIR>/cpe_video.db` | 要換 DB 才需設。 |
| `CORS_ORIGINS` | 否 | localhost 開發埠 | 只有「前端與後端分開部署」時才需要。 |
| `WEB_DIST_DIR` | 否 | `<repo>/web/dist` | 覆寫要 serve 的前端目錄。 |
| `PORT` | 否 | `8080` | Zeabur 會自動注入。 |

> **金鑰安全**：`.env`、`*.mp4`、`node_modules` 等都在 `.dockerignore` 內，不會打包進 image。
> 雲端金鑰一律走 Zeabur 環境變數，不要 commit。

---

## 二、Zeabur 部署步驟

1. **推上 GitHub**：把這個 repo（含 `Dockerfile`）推到 GitHub。
2. **建立服務**：Zeabur → New Project → Deploy from GitHub → 選此 repo。
   Zeabur 偵測到 `Dockerfile` 會自動用它 build。
3. **掛 Volume（持久化）**：在服務的 Volumes 新增一個 volume，掛載路徑 `/data`。
   SQLite 與輸出的 MP4 要放這裡，才不會在重新部署後消失。
4. **設定環境變數**（Variables）：
   ```
   AUTH_PASSWORD=<你們的共用密碼>
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-4o-mini
   GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account",...}   ← 整段貼上
   DATA_DIR=/data/db
   OUTPUT_DIR=/data/out
   ```
5. **產生網域**：在 Networking 產生一個 `*.zeabur.app` 網域（自動 HTTPS），或綁自訂網域。
6. **開網站**：開網域 → 輸入 `AUTH_PASSWORD` 登入 → 開始用。

> **資源**：render 是用 Chrome headless 算影片，吃 CPU/記憶體。建議實例 **≥ 2 GB RAM**。
> 同時間只跑得動少量 render（單一背景任務），小團隊足夠。

---

## 三、本機開發

需要 Node 22、Python 3.12（用 `uv`）。

```bash
# 1) 安裝依賴
npm install                        # 根目錄 remotion + web workspace
cd backend && uv sync && cd ..

# 2) 後端（讀根目錄 .env：OPENAI_API_KEY / AUTH_PASSWORD / GOOGLE_APPLICATION_CREDENTIALS）
cd backend && uv run uvicorn app.main:app --reload --port 8080

# 3) 前端（另開終端；/api 會 proxy 到 8080）
npm run web:dev                    # http://localhost:5173
```

不設 `AUTH_PASSWORD` 時登入會被跳過（方便本機開發）。

要驗證「production 同源」行為，可改成：

```bash
npm run web:build                  # 產生 web/dist
cd backend && uv run uvicorn app.main:app --port 8080
# 直接開 http://localhost:8080 ，後端會 serve 前端
```

---

## 四、驗證

```bash
# 後端測試
cd backend && uv run pytest -q

# 前端型別 + build
cd web && npm run build

# 前端單元測試
node --test --experimental-strip-types web/src/lib/api-client.test.ts
```
