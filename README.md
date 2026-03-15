# CPE Video — 程式碼教學影片產生器

用 JSON 設定檔就能製作帶有打字機效果、逐行 highlight、浮動標注、**AI 語音旁白**的程式碼教學影片。

---

## 快速開始

```bash
npm i                              # 安裝相依套件
npm run dev                        # 開啟預覽（localhost:3000）
npm run gen-audio <影片資料夾>     # 產生 AI 語音旁白（需有 subtitle）
npm run render <影片資料夾>        # 輸出影片
```

---

## 製作流程

```
1. 準備 cpp 檔  →  放到 public/<影片資料夾>/
2. 編輯設定檔   →  public/<影片資料夾>/config.json（含 subtitle 欄位）
3. 產生語音     →  npm run gen-audio <影片資料夾>
4. 預覽         →  npm run dev
5. 輸出         →  npm run render <影片資料夾>
```

---

## 設定檔：`public/<影片資料夾>/config.json`

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
      "file":     "code01.cpp",    // 該影片資料夾內的程式碼檔名（不需路徑）
      "subtitle": "這裡是字幕文字，也是 AI 旁白的朗讀內容。",

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

## AI 語音旁白

`subtitle` 欄位同時作為字幕與 AI 語音的來源，使用 **Google Cloud Gemini 2.5 Flash TTS**（`Achernar` 聲音，`cmn-TW`）。原生支援中英混雜，無需額外設定。

### 前置設定（一次性）

**1. 開啟 GCP API 與權限**

在 [Google Cloud Console](https://console.cloud.google.com/) 完成以下設定：
- 啟用 **Cloud Text-to-Speech API**
- 啟用 **Vertex AI API**
- 建立 Service Account，授予兩個角色：
  - `Cloud Text-to-Speech API User`
  - `Vertex AI User`
- 下載 Service Account 的 **JSON 金鑰**

**2. 建立 `.env`**

```bash
cp .env.example .env
```

編輯 `.env`，填入金鑰路徑：

```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json
```

### 產生語音

```bash
npm run gen-audio bubble_sort               # 產生所有缺少的步驟音訊
npm run gen-audio bubble_sort --force       # 強制重新產生全部
npm run gen-audio bubble_sort --step 3      # 只重新產生第 3 步（1-indexed）
```

音訊檔存放在 `public/<影片資料夾>/audio/step_01.mp3` 等路徑，**不需手動指定**，render 時會自動讀取。

### 時長自動延伸

若音訊比 config 設定的 `to - from` 還長，該步驟會自動延伸，確保旁白播完才切換到下一步。

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
- 有語音時，步驟時長會自動延伸到音訊結束，不需手動調整 `to`

```jsonc
// 範例：步驟 A 6 秒、步驟 B 8 秒（重點步驟可以更長）
{ "from": 0,  "to": 6,  ... },
{ "from": 6,  "to": 14, ... }
```

---

## 資料夾管理（多支影片）

每支影片對應 `public/` 底下**一層**獨立資料夾：

```
public/
  bubble_sort/         ← 第一支影片
    config.json
    code01.cpp
    code02.cpp
    audio/             ← gen-audio 自動建立
      step_01.mp3
      step_02.mp3
      ...
  merge_sort/          ← 第二支影片
    config.json
    code01.cpp
    ...
```

`config.json` 的 `"file"` 欄位只填**檔名**，不需要加資料夾路徑。

---

## 常用指令

```bash
npm run dev                              # 開啟 Remotion Studio 預覽
npm run render <folder>                  # 輸出影片（例：npm run render bubble_sort）
npm run gen-audio <folder>               # 產生語音旁白
npm run gen-audio <folder> --force       # 強制重新產生所有語音
npm run gen-audio <folder> --step N      # 只重新產生第 N 步語音
npm run lint                             # TypeScript + ESLint 檢查
```

---

## 新建一支影片

1. 在 `public/` 底下建立資料夾，例如 `public/my_topic/`
2. 建立 `config.json`（可複製 `bubble_sort/config.json` 作為模板）
3. 準備各步驟的 cpp 檔，放在同一個資料夾
4. 產生語音：

```bash
npm run gen-audio my_topic
```

5. 預覽與輸出：

```bash
npm run dev
npm run render my_topic
```

---

## 程式碼檔案準備

每個步驟對應一個 cpp 檔，放在影片資料夾裡。

**慣例做法**（逐步新增程式碼）：

```
code01.cpp   ← 只有注解
code02.cpp   ← 加上 #include
code03.cpp   ← 再加上函式骨架
...
code12.cpp   ← 完整程式
```

每個步驟只新增 1–3 行，打字機效果會自動把**新增的部分**打出來。

---

## 專案結構

```
public/
  bubble_sort/       ← 影片資料夾（可建立多個）
    config.json      ← 影片設定（你主要編輯這裡）
    code01.cpp       ← 程式碼步驟檔案
    code02.cpp
    audio/           ← AI 語音旁白（gen-audio 自動產生）
      step_01.mp3
      ...

scripts/
  gen-audio.mjs      ← AI 語音產生腳本
  render.mjs         ← 輸出影片腳本

src/
  config-types.ts    ← config.json 的 TypeScript 型別定義
  Main.tsx           ← 主要渲染元件
  AudioPlayer.tsx    ← 語音旁白播放器
  FloatingAnnotation.tsx  ← 浮動標注
  HighlightOverlay.tsx    ← 行高亮 + 遮罩
  LineNumbers.tsx         ← 行號
  SubtitleBar.tsx         ← 字幕列
  CodeTransition.tsx      ← 打字機效果

out/
  bubble_sort.mp4    ← 輸出影片
```
