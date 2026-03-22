---
capability: step-visual-elements
type: new
---

# Spec：step-visual-elements

## 目的

定義每個步驟的視覺元素組合規則，確保 highlight、行號、annotations、捲動可完全獨立使用。

## 需求

### Config Schema

- `StepJSON.highlight` SHALL be optional (`highlight?: HighlightConfigJSON`)
- `StepJSON.focusLine` SHALL be optional (`focusLine?: number`), indicating the line to appear at the TOP of the viewport (not centered)
- `StepJSON.annotations` SHALL remain optional (unchanged)

### 行號（LineNumbers）

- Line numbers SHALL always be rendered regardless of whether `highlight` is present
- When `highlight` is present, lines within the highlight range SHALL render with highlight color and bold weight
- When `highlight` is absent, all line numbers SHALL render with a uniform dimmed color

### Highlight Overlay

- `HighlightOverlay` SHALL only be rendered when `highlight` is present

### 捲動（Scroll）

- When `focusLine` is set, that line SHALL appear at the top of the viewport; the scroll value SHALL NOT be constrained to only increase
- When `focusLine` is not set AND `highlight` is present, the viewport SHALL center on the highlight midpoint, and scroll SHALL only increase (monotonic)
- When both `focusLine` and `highlight` are absent, the viewport SHALL maintain the previous step's scroll position

## 限制條件

- `focusLine` 設定時不受「只增不減」限制，允許畫面往回捲
- 三個視覺元素（highlight、annotations、行號）可任意組合，互不依賴
