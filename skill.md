---
name: cpe-video
description: 從零建立 CPE Video 教學影片——環境檢查、素材收集、AI 自動切片、逐步確認、產生音檔
metadata:
  tags: cpe, video, remotion, tts, cpp, tutorial
---

## When to use

當使用者想從零建立一支教學影片時使用此 skill，包括：

- 「建新影片」「從零開始做影片」
- 明確呼叫 `/cpe-video`
- 提供了 C++ 程式碼並詢問如何製作成影片

## How to use

載入 [skills/cpe-video.md](skills/cpe-video.md) 取得完整的執行流程，包含：

- **Phase 1**：環境檢查（`.env`、GCP 金鑰）
- **Phase 2**：素材收集（資料夾名稱、題目說明、C++ 原始碼）
- **Phase 3**：AI 分析與切片（自動決定步驟數、highlight、subtitle）
- **Phase 4**：逐步確認（每步一一展示，支援修改）
- **Phase 5**：產生檔案（cpp 切片、config.json）
- **Phase 6**：生成音檔（使用者確認後執行 gen-audio）

## Project context

執行前先閱讀以下文件以了解專案結構與設定格式：

- `README.md` — 完整使用說明與 config.json 欄位定義
- `public/bubble_sort/config.json` — 實際設定範例
