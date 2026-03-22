# Proposal：optional-highlight-and-focus-line

## 摘要

將步驟的視覺元素解耦，使 `highlight` 成為可選項，並新增 `focusLine` 欄位讓使用者精確控制捲動位置。

## 動機

原本每個步驟必須有 `highlight` 才能正常運作，但實際製作影片時，有些步驟只需要 annotations 說明，不需要高亮任何程式碼；有些步驟（例如結尾展示全部程式碼）需要精確控制畫面捲到哪一行。強制 highlight 限制了這些使用場景。

## 解決方案

1. `highlight` 改為可選（`highlight?: HighlightConfigJSON`）
2. 行號永遠顯示，不依賴 highlight 存在；有 highlight 時高亮對應行號，沒有時一律 dimmed
3. 新增 `focusLine?: number`，讓使用者明確指定該步驟的視覺焦點行
4. 捲動邏輯：
   - 有 `focusLine` → 直接對齊該行（可往回捲）
   - 無 `focusLine`，有 `highlight` → 對齊 highlight 中心，只增不減（現有行為）
   - 無 `focusLine`，無 `highlight` → 維持上一步捲動位置

## 考慮過的替代方案

- 強制移除「只增不減」：使用者需對每個步驟設定 focusLine，負擔太重，否決。
- 分兩個 change 做：改動範圍小，合併做更合理。

## 影響範圍

- 影響的 specs：`step-visual-elements`（新增）
- 影響的 code：
  - `src/config-types.ts`
  - `src/Main.tsx`
  - `src/LineNumbers.tsx`
  - `src/calculate-metadata/calculate-metadata.tsx`
  - `src/Root.tsx`（`folder` 更名為 `example-bubble_sort`）
