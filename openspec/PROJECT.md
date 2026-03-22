# CPE Video

> 最後更新：2026-03-22（wrap: optional-highlight-and-focus-line）

## 系統概述

以 Remotion（React）製作程式碼教學影片的工具。使用者透過 JSON config 定義「步驟」，每個步驟包含程式碼、字幕、highlight 區域、浮動標注等，系統自動計算捲動位置並渲染成影片。

## 技術棧

- Framework：Remotion (React)
- Language：TypeScript
- Config：JSON（使用者定義影片內容）
- Syntax Highlighting：自製 pipeline

## 能力清單

| Capability | 簡介 | Spec 位置 |
|-----------|------|---------|
| step-visual-elements | 每個步驟的視覺元素組合：highlight、行號、annotations、捲動控制 | openspec/specs/step-visual-elements/spec.md |

## 架構決策記錄（ADR）

| 時間 | 決策 | 理由 | 來源 Change |
|------|------|------|------------|
| 2026-03-22 | highlight 改為可選，新增 focusLine 欄位 | 支援純 annotation 步驟、精確捲動控制 | optional-highlight-and-focus-line |
