---
change: optional-highlight-and-focus-line
status: completed
agent: codex
updated: 2026-03-22
progress: 8/8
---

# Tasks：optional-highlight-and-focus-line

## 檔案結構

| 動作 | 檔案路徑 | 職責 |
|------|---------|------|
| 修改 | `src/config-types.ts` | `highlight` 改可選，新增 `focusLine?` |
| 修改 | `src/Main.tsx` | `StepProps` 更新、`computeStepScroll()` 新邏輯、LineNumbers 移出條件 |
| 修改 | `src/LineNumbers.tsx` | `config` 改為可選，無 highlight 時渲染 dimmed 行號 |
| 修改 | `src/calculate-metadata/calculate-metadata.tsx` | 傳入 `focusLine`，`highlight` 改為可選傳遞 |

## Tasks

- [x] `src/config-types.ts`：`StepJSON.highlight` 改為 `highlight?`，新增 `focusLine?: number`
- [x] `src/Main.tsx`：`StepProps` 加入 `focusLine: number | null`，`highlight` 改為 `HighlightConfig | null`
- [x] `src/Main.tsx`：`computeStepScroll()` 實作三段捲動邏輯（focusLine → highlight 中心只增不減 → 維持 prev）
- [x] `src/Main.tsx`：`LineNumbers` 移出 `{step.highlight && ...}` 條件，永遠渲染
- [x] `src/LineNumbers.tsx`：`config` 改為 `config?: HighlightConfig`，無 config 時所有行號 dimmed
- [x] `src/calculate-metadata/calculate-metadata.tsx`：傳入 `focusLine: stepConfig.focusLine ?? null`，`highlight` 改為可選
- [x] 手動測試：有 highlight 步驟、無 highlight 步驟、有 focusLine 步驟各驗證一次
- [x] `src/Root.tsx`：確認 `folder` 為 `example-bubble_sort`（開源後的正式資料夾名稱）

## Agent Log

| 時間 | Agent | 完成 | 備註 |
|------|-------|------|------|
| 2026-03-22 | codex | 8/8 | 新增 step visual helper 與原生測試，`npm run lint` 與 manual still render 驗證完成 |
