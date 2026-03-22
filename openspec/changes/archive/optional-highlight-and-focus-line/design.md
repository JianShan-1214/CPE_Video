# Design：optional-highlight-and-focus-line

## 概述

解耦步驟視覺元素，highlight 改可選，行號永遠顯示，新增 focusLine 精確捲動控制。

## 架構

```
StepJSON (config)
  ├── highlight?   → HighlightOverlay（只在有 highlight 時渲染）
  ├── focusLine?   → 傳入 computeStepScroll()
  └── annotations? → AnnotationCallout（已可選，不變）

LineNumbers       → 永遠渲染，highlight 存在時高亮對應行號
```

### 捲動決策樹

```
有 focusLine?
  ├── YES → 對齊 focusLine，允許往回捲
  └── NO  → 有 highlight?
              ├── YES → 對齊 highlight 中心，max(val, prev)（只增不減）
              └── NO  → 維持 prev（不動）
```

## 關鍵決策

| 決策 | 選擇 | 理由 |
|------|------|------|
| 只增不減預設保留 | 是 | 避免使用者需對所有步驟設定 focusLine |
| focusLine 覆蓋只增不減 | 是 | 精確控制時使用者已明確表達意圖 |
| 行號永遠顯示 | 是 | 行號是程式碼可讀性基礎，不應依賴 highlight |
| 無 highlight 無 focusLine 時維持 prev | 是 | 最自然的行為，不跳動 |

## 整合點

- `config-types.ts`：`StepJSON` 型別更新
- `calculate-metadata.tsx`：將 `focusLine` 傳入 `StepProps`
- `Main.tsx`：`computeStepScroll()` 新邏輯；`LineNumbers` 移出 highlight 條件判斷
- `LineNumbers.tsx`：`config` 改為可選，無 highlight 時 render dimmed 行號

## 開放問題

- 無
