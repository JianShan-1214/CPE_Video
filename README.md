# CPE Video — 程式碼教學影片產生器

用 JSON 設定檔就能製作帶有打字機效果、逐行 highlight、浮動標注的程式碼教學影片。

---

## 快速開始

```bash
npm i          # 安裝相依套件
npm run dev    # 開啟預覽（localhost:3000）
npx remotion render src/index.ts Main out/Main.mp4  # 輸出影片
```

---

## 製作流程

```
1. 準備 cpp 檔  →  放到 public/
2. 編輯設定檔   →  public/config.json
3. 預覽         →  npm run dev
4. 輸出         →  npx remotion render
```

---

## 設定檔：`public/config.json`

所有步驟都在這一個檔案裡設定，不需要改任何程式碼。

### 完整結構

```jsonc
{
  "steps": [
    {
      // ── 必填 ──────────────────────────────────────────
      "label":    "步驟名稱",      // 在 Remotion Studio 時間軸顯示
      "from":     0,               // 步驟開始（秒）
      "to":       6,               // 步驟結束（秒）—— 每步可以不同長度
      "file":     "code01.cpp",    // public/ 資料夾內的程式碼檔名
      "subtitle": "這裡是字幕文字，顯示在畫面下方。",

      // ── highlight 設定（必填）──────────────────────────
      "highlight": {
        "startLine": 1,            // 要高亮的起始行（1-indexed）
        "endLine":   3,            // 要高亮的結束行
        "color": "blue"            // 顏色預設值（見下方色表）
      },

      // ── 浮動標注（選填，可多個）───────────────────────
      "annotations": [
        {
          "targetLine": 2,         // 標注指向的行（1-indexed）
          "text":       "說明文字",
          "startTime":  3.2,       // 距步驟開始幾秒後彈出（例：打字結束後）
          "theme":      "yellow"   // 標注顏色（見下方色表）
        }
      ]
    }
  ]
}
```

---

## 顏色說明

### highlight 顏色（`color` 欄位）

| 值 | 用途建議 | 邊框色 |
|----|---------|--------|
| `blue` | 一般說明 | `#58a6ff` |
| `yellow` | 迴圈 / 流程控制 | `#e3b341` |
| `red` | 條件判斷 | `#f85149` |
| `green` | 修改 / 輸出 | `#3fb950` |
| `lightblue` | 函式宣告 | `#79c0ff` |

需要完全自訂時，改用 `bgColor` + `borderColor`：

```jsonc
"highlight": {
  "startLine": 5,
  "endLine": 7,
  "bgColor":     "rgba(180, 100, 255, 0.20)",
  "borderColor": "#b464ff"
}
```

### 標注顏色（`theme` 欄位）

`"blue"` / `"yellow"` / `"green"` / `"red"`

---

## 時間設定

- `from` / `to` 單位為**秒**，每個步驟可以設定不同的長度
- `annotations.startTime` 是距**該步驟開始**的秒數
  - 打字機效果約佔前 2.8 秒，所以 `startTime: 3.2` 代表打字剛結束後彈出
- 建議每步 5–8 秒，讓觀看者有時間看清楚 highlight

```jsonc
// 範例：步驟 A 6 秒、步驟 B 8 秒（重點步驟可以更長）
{ "from": 0,  "to": 6,  ... },
{ "from": 6,  "to": 14, ... }
```

---

## 準備程式碼檔案

每個步驟對應一個 cpp 檔，放在 `public/` 資料夾。
檔名自由命名，在 `config.json` 的 `"file"` 欄位填入即可。

**慣例做法**（逐步新增程式碼）：

```
public/
  code01.cpp   ← 只有注解
  code02.cpp   ← 加上 #include
  code03.cpp   ← 再加上函式骨架
  ...
  code12.cpp   ← 完整程式
```

每個步驟只新增 1–3 行，打字機效果會自動把**新增的部分**打出來。

---

## 範例：新增一個步驟

1. 建立 `public/code13.cpp`（在上一個版本基礎上加新內容）
2. 在 `config.json` 的 `steps` 陣列末尾加入：

```jsonc
{
  "label":    "說明 return 0",
  "from":     72,
  "to":       78,
  "file":     "code13.cpp",
  "subtitle": "main 函式最後 return 0，代表程式正常結束。",
  "highlight": {
    "startLine": 36,
    "endLine":   36,
    "color":     "blue"
  }
}
```

3. `npm run dev` 預覽，確認沒問題後 render。

---

## 專案結構

```
public/
  config.json        ← 影片設定（你主要編輯這裡）
  code01.cpp         ← 程式碼步驟檔案
  code02.cpp
  ...

src/
  config-types.ts    ← config.json 的 TypeScript 型別定義
  Main.tsx           ← 主要渲染元件
  FloatingAnnotation.tsx  ← 浮動標注
  HighlightOverlay.tsx    ← 行高亮 + 遮罩
  LineNumbers.tsx         ← 行號
  SubtitleBar.tsx         ← 字幕列
  CodeTransition.tsx      ← 打字機效果

out/
  Main.mp4           ← 輸出影片
```

---

## 常用指令

```bash
npm run dev                                              # 預覽
npx remotion render src/index.ts Main out/Main.mp4      # 輸出（覆蓋）
npx remotion render src/index.ts Main out/MyVideo.mp4   # 輸出到指定檔名
npx remotion studio                                      # 開啟 Remotion Studio GUI
```
