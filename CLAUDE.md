# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run dev                              # 開啟 Remotion Studio 預覽 (localhost:3000)
npm run render <folder>                  # 輸出影片，例：npm run render bubble_sort
npm run gen-audio <folder>               # 產生 AI 語音（需 .env 設定 GCP 金鑰）
npm run gen-audio <folder> --force       # 強制重新產生所有語音
npm run gen-audio <folder> --step N      # 只重新產生第 N 步語音
npm run lint                             # tsc + eslint 靜態檢查
```

**執行測試**（Node 內建 test runner，無需額外框架）：

```bash
node --test src/step-visual-elements.test.mjs   # 執行單一測試檔
node --test src/**/*.test.mjs                   # 執行所有測試
```

測試檔以 `.test.mjs` 結尾，使用 `node:test` + `node:assert/strict`。

## 架構

### 資料流

```
public/<folder>/config.json
        ↓  (async, before render)
calculateMetadata  ←  get-files.ts (讀 cpp 原始碼)
        ↓             process-snippet.ts (syntax highlight via codehike)
Props (steps, themeColors, codeWidth, charWidth)
        ↓
Root.tsx  →  Main.tsx
                ↓
          Series<CodeStep>  ─── 各步驟依 durationInFrames 排列
                ↓
          CodeTransition / HighlightOverlay / HighlightBox
          LineNumbers / FloatingAnnotation / AudioPlayer
```

### 關鍵模組職責

| 檔案 | 職責 |
|------|------|
| `src/config-types.ts` | `config.json` 的 TypeScript 型別與 `HIGHLIGHT_PRESETS` 顏色對應表 |
| `src/calculate-metadata/calculate-metadata.tsx` | Remotion `calculateMetadata`：讀 config、highlight 程式碼、計算音訊長度、展開 annotation 座標，回傳完整 `Props` |
| `src/calculate-metadata/schema.ts` | Zod schema；`folder` 欄位透過 `getStaticFiles()` 自動偵測 `public/` 下的子資料夾 |
| `src/Main.tsx` | 主渲染元件；用 `useMemo` 預計算所有步驟的 `scrollTargets`，再交給 `Series<CodeStep>` 逐步渲染 |
| `src/step-visual-elements.ts` | 純函式：`computeStepScroll`（捲動目標）與 `getLineNumberAppearance`（行號樣式）；有獨立測試 |
| `src/step-animations.ts` | 動畫相關型別（`HighlightConfig`、`AnnotationCallout`）與 `targetLineY` 工具函式 |
| `src/font.ts` | 字型載入（JetBrains Mono）與全域 layout 常數 |

### Layout 常數

`fontSize`、`lineHeight`、`verticalPadding`、`CODE_AREA_HEIGHT` 在以下三個地方**各自定義**，修改時必須同步更新：

- `src/font.ts` — 來源定義
- `src/step-animations.ts` — `LINE_HEIGHT_PX`
- `src/step-visual-elements.ts` — `FONT_SIZE`, `LINE_HEIGHT`, `VERTICAL_PADDING`, `CODE_AREA_HEIGHT`

### calculateMetadata 的時序

`calculateMetadata` 在 Remotion 渲染前非同步執行，負責：
1. 讀取 `public/<folder>/config.json`
2. 逐步讀取 cpp 原始碼並做 syntax highlight
3. 嘗試讀取各步驟音訊長度（`public/<folder>/audio/step_NN.mp3`）；若音訊比 config 設定長，自動延伸 `durationInFrames`
4. 展開 annotation 的 `lineStartX` / `lineEndX`（像素座標，依 charWidth 計算）
5. 計算影片總寬（依最長程式碼行自動調整）

### 捲動邏輯（step-visual-elements.ts）

- `focusLine` 設定 → 該行對齊畫面頂部，不受「只增不減」限制
- 僅有 `highlight` → 置中 highlight 範圍，捲動值單調遞增
- 兩者均無 → 維持上一步捲動位置

### 新增影片

在 `public/` 新建資料夾並放入 `config.json` 與 cpp 檔，`schema.ts` 會在下次啟動 Studio 時自動偵測到新資料夾，無需修改任何程式碼。

FPS 固定為 30（定義在 `calculate-metadata.tsx`）。
