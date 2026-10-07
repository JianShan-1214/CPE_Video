---
name: cpe-video
description: >-
  把一題 C++ 解法（CPE／OJ 題）做成教學影片：用 tools/cpe-tools 自動追蹤程式（autoanim）→ 寫口語旁白並驗證（narrate）
  → Remotion 渲染（Story 模式，可加 TTS）。也涵蓋出片前檢查（overlapcheck 等）、元件覆蓋表，以及舊式手動 config 流程。
metadata:
  tags: cpe, video, remotion, tts, cpp, tutorial, autoanim
---
# CPE Video：C++ 解法 → 教學影片

本檔所有路徑都相對於 repo 根目錄。指令中 `<folder>` 是 `public/` 底下的資料夾名稱。

## 何時使用
- 手上有一題的完整 C++ 解法＋一組小輸入（與預期輸出），想產出逐步講解影片。
- 要重跑追蹤／旁白、做出片前檢查、或判斷某種資料結構目前能不能自動呈現。
- 要用舊式 `config.json`＋累加 cpp 的手動流程（見附錄 B）。

## 不在本 skill 範圍
- 修改 `tools/cpe-tools` 或 `src/` 的程式本身（新增元件、tracer 支援新型別）——見「新增元件步驟」與「疑難排解」。
- 題目解法撰寫與測資設計。

## 前置需求
| 項目 | 版本／說明 | 誰需要 |
|---|---|---|
| OS | Linux 或 macOS（沙箱 runner 使用 POSIX `resource` 模組；Windows 請用 WSL） | autoanim |
| Python | 3.12 以上（與 `backend/pyproject.toml` 的 `requires-python` 一致） | 全部 Python 工具 |
| Python 套件 | `tree-sitter`、`tree-sitter-cpp`（解析 C++）、`anyio`（`backend/app/services/trace/runner.py` 使用）；其餘工具只用標準函式庫 | autoanim |
| C++ 編譯器 | `g++`（或 `c++`／`clang++`；可用環境變數 `CPE_CXX` 指定）——tracer 會實際編譯並執行你的程式 | autoanim |
| Node.js／npm | Node 18 以上（`scripts/*.mjs` 為 ESM 並使用內建 `fetch`）；`npm install` 安裝 Remotion 等依賴 | story-build／render／TTS |
| ffprobe（ffmpeg） | 有音檔時 `story-build` 用來量每句長度；抽影格檢查也會用到 ffmpeg | 正式語音版、檢查 |
| `OPENAI_API_KEY` | 只透過環境變數提供（例如 `export OPENAI_API_KEY=...`）；不要寫進任何會進 git 的檔案 | `story-audio`（TTS） |

`autoanim.py` 會自行把 `backend/` 加進 `sys.path`，所以不需要安裝整個 backend，只要上表的三個 Python 套件。`narrate.py`、檢查器、`coverage.py`、`sync_skill.py` 任何 Python 3.12+ 都能直接跑。

## 安裝
```bash
# 1. Node 依賴（Remotion）
npm install

# 2. Python 環境（位置自訂，以下用 repo 內被 .gitignore 忽略的 .venv 為例）
python3 -m venv .venv
. .venv/bin/activate
pip install tree-sitter tree-sitter-cpp anyio

# 3. 確認
g++ --version
python tools/cpe-tools/autoanim.py --help
```

## 端到端流程
1. 準備輸入：完整解法 `X.cpp`、小輸入 `X.in`、預期輸出 `X.out`。輸入越小越好（見「顯示上限」）；教學片用 `split2` 版面時，程式單行請 ≤58 字元。這些檔案放在 repo 外或不要 commit。
2. autoanim：追蹤 → 基礎 story（含模板旁白）。
3. 看 autoanim 結尾的缺元件警示與 `warnings.json`，決定照退化畫面出片或先補元件。
4. narrate：`dump` → 寫 `narration.json` → `apply`（要 exit 0、沒有 warning）。
5. 無語音版 render → 跑「出片前檢查」→ 人工看片。
6. （選用）TTS：`story-audio` → 再 render 正式語音版 → 再檢查一次音畫對齊。

建議的影片結構：題目說明 → 解法概念 → 程式逐段講解（split2）→ 片尾完整程式（fullcode 場景）。

### 1) autoanim：追蹤並產生基礎 story
```bash
cd tools/cpe-tools
python autoanim.py <base_folder> --cpp X.cpp --stdin X.in --expect X.out --layout split2 --title "<標題>"
```
- 流程：tree-sitter 插樁 → 沙箱分別編譯執行原版與插樁版（輸出必須一致；有 `--expect` 時還必須吻合）→ 事件流 → 基礎 story → 自我對拍。
- 輸出：`public/<base_folder>/` 下的 `story.json`、`code.cpp`、`verify.json`、`trace_events.json`、`narr_meta.json`、`warnings.json`。同名資料夾已存在時會直接覆寫這些檔案；建議命名 `auto_<題>_base`。
- 參數（皆來自 `autoanim.py --help`）：
  | 參數 | 說明 |
  |---|---|
  | `folder`（位置參數） | 輸出資料夾名稱 |
  | `--cpp`（必填） | C++ 原始碼 |
  | `--stdin`（必填） | 輸入檔 |
  | `--expect` | 預期輸出；不符就中止 |
  | `--title` | 影片標題 |
  | `--layout split\|split2\|concept\|wide` | 預設 `split`；教學片建議 `split2`（左程式面板＋右動畫窗）。`fullcode` 不是這裡的 layout，而是 narrate 的片尾場景 |
  | `--no-comps` / `--disable graph,seq,slots,tree,keyed` | 全部或個別關閉動畫元件 |
  | `--out` | 輸出根目錄，預設 `public/` |
  | `--stage-fit auto\|off` | 動畫區依內容自適應放大，並寫入最小可讀尺寸警示（預設 auto） |
  | `--stage-w N` | 虛擬舞台寬；預設 split2 為 1000，其餘 1200 |
  | `--show-born` | 只設一次就不再改的純量也顯示 |
  | `--layout-rev 1\|2` | 預設 2（字幕下移，與程式列不重疊） |
- 顯示上限：1D 陣列 ≤16、2D ≤8×10、純量 ≤8；超過只顯示前段並出警示。
- 陣列只顯示程式寫入過的格子；未初始化的殘值格顯示「?」。
- 當索引用的純量顯示成 ▲指標：黃＝本 cue 改變，綠＝本場先前已定案；離開作用域或尚未初始化時收起。

### 2) narrate：口語旁白層
```bash
cd tools/cpe-tools
python3 narrate.py dump <base_folder>                                   # 印出給寫旁白者（人或 AI）看的精簡稿
python3 narrate.py apply <base_folder> <path/to/narration.json> <new_folder> [--no-build] [--stage-fit auto|off]
```
- `apply` 不改任何動畫 op（畫面＝trace），只合併文字並驗證（見「驗證涵蓋範圍」）；成功後在 repo 根目錄自動跑 `node scripts/story-build.mjs <new_folder> --no-audio`（`--no-build` 可略過）。
- 驗證失敗會列出 ✗ 並 exit 1（story 仍會寫出）：修 `narration.json` 後重跑。
- 有元件時 cue 數會變，務必重跑 `dump` 再寫 narration。
- 環境變數 `NARRATE_PUB` 可改讀寫其他 public 目錄（測試用；此時自動 story-build 仍以 repo 的 `public/` 為準）。

### 3) Remotion：build／render／TTS（在 repo 根目錄）
```bash
npm run story-build <folder> -- --no-audio          # 產生 public/<folder>/timeline.json 並做規則檢查
npm run story-render <folder> -- --no-audio         # 無語音版，預設輸出 out/<folder>_noaudio.mp4
npm run story-render <folder> -- --no-audio my.mp4  # 也可指定輸出檔（副檔名 .mp4）
npm run dev                                          # Remotion Studio 預覽

# 選用：TTS（OpenAI）
export OPENAI_API_KEY=...
npm run story-audio <folder>             # 逐句產生 public/<folder>/audio/<cueId>.mp3；已存在的會跳過
npm run story-audio <folder> -- --force  # 全部重產（例如換了聲音）
npm run story-render <folder>            # 有音檔時自動用真實長度並混音，預設輸出 out/<folder>.mp4
```
- 也可直接 `node scripts/story-render.mjs <folder> --no-audio [out.mp4]`。
- `story-render` 會先自動跑 `story-build`。render 需要數分鐘，一次跑一支即可。
- TTS 設定（環境變數）：`OPENAI_TTS_VOICE`（聲音，可自選）、`OPENAI_TTS_MODEL`（預設 `gpt-4o-mini-tts`）、`OPENAI_BASE_URL`、`TTS_INSTRUCTIONS`（語氣指示）。換聲音後要加 `--force` 重產。

## 出片前檢查（每支片都跑）
```bash
cd tools/cpe-tools
python3 overlapcheck.py <folder>          # 重放每個 cue 結束時的可見元素，找重疊／出界；目標 0
python3 overlapcheck_strict.py <folder>   # 同上但 plain 標籤也算；目標 0
python3 dumpcues.py <folder> <id前綴…>     # 印出每個 cue 結束時指定前綴元素的狀態（抽查用）
python3 pixel_table.py <folder>           # 不渲染推算 1920×1080 成片的最小元素像素表（--strict-exit 未達標時 exit 1）
cat ../../public/<folder>/verify.json      # autoanim 對拍結果（ok 應等於 checked）
cat ../../public/<folder>/narr_verify.json # narrate 驗證結果
cat ../../public/<folder>/warnings.json    # 缺元件／舞台尺寸警示
cd ../.. && npx tsc --noEmit               # 有改到 src/ 時
ffmpeg -ss <秒數> -i out/<folder>_noaudio.mp4 -frames:v 1 frame.png   # 抽影格人工檢查
```
- `overlapcheck*.py`、`pixel_table.py` 也接受資料夾的絕對路徑；`dumpcues.py` 只接受 `public/` 下的名稱。
- 抽 6–8 張影格檢查：字幕單行、元素不重疊、cap 不遮擋、沒有殘值外露、split2 字級、片尾完整程式。
- 有語音版再檢查音畫是否對齊。

## 缺元件規則
- autoanim 結尾的「缺元件警示」與 `warnings.json` 一定要看。status：支援／部分支援／退化／不支援。
- 「不支援」（變數完全不顯示）與「退化」的項目，出片前要確認畫面仍可接受；不要假裝通用陣列版就是該結構的正確呈現。
- 元件補齊後只改 `coverage.py`，再跑 `python3 tools/cpe-tools/sync_skill.py` 更新本檔的覆蓋表。

## 版本控制注意
- 只把工具與通用文件放進 git；題目解法 cpp、測資、narration json、mp4、影格截圖不要 commit。
- `public/<folder>/` 是產出物，是否提交依專案慣例決定。

## 疑難排解
| 症狀 | 原因／處理 |
|---|---|
| `ModuleNotFoundError: tree_sitter`（或 `tree_sitter_cpp`、`anyio`） | 用裝了這些套件的 Python 執行 autoanim（見「安裝」） |
| `伺服器沒有 C++ 編譯器` | 安裝 g++／clang++，或設定 `CPE_CXX` 指向編譯器；`CPE_CXX 指定的編譯器找不到` 表示該名稱不在 PATH |
| `⚠ 插樁版輸出與原版不同，中止`（exit 2） | 插樁影響了程式行為（常見：未定義行為、讀未初始化變數）；先修程式讓輸出穩定 |
| `⚠ 原版輸出與預期不符`（exit 2） | `--expect` 檔與實際輸出不同（注意行尾空白、結尾換行） |
| `沒有任何追蹤事件`（exit 3） | 程式沒有可追蹤的變數變化；確認輸入有被讀到、變數型別受支援 |
| 程式逾時／被終止 | 沙箱執行上限約 3 秒 CPU、512 MB 記憶體（Linux）、不可 fork；改用更小的輸入 |
| `限制:` 訊息或畫面只顯示部分陣列 | 超過顯示上限；縮小輸入 |
| narrate `驗證失敗（N 項）`（exit 1） | 依 ✗ 訊息修 narration.json：每個原 cue 都要有一筆、數字必須能在該 cue 的事實集合找到（或用 `allow_numbers`）、字幕／cap 長度規則 |
| `fullcode[...] 程式 N 行 > 容量 50` 或單行 >58 字元 | 精簡程式或分段；或在 narration 頂層加 `"fullcode_allow_overflow": true` 降為警示 |
| `OPENAI_API_KEY 未設定` | 在環境變數設定後再跑 `story-audio` |
| story-build 報 `ffprobe` 錯誤 | 安裝 ffmpeg（含 ffprobe），或先用 `--no-audio` |
| story-build／narrate 出現字數或 cap 警告 | 依訊息調整旁白（每場 45–70 字、字幕片段 ≤18 字、cap ≤14 字且不重複旁白） |

---

## Story 模式（cue 綁旁白；現行標準）

資料夾 `public/<folder>/` 內放 `story.json`、`code.cpp`（完整答案，不再累加多檔），用：

- `npm run story-build <folder>`：量每句旁白音檔長度（沒音檔就以約 4.3 字/秒估算），產出 `timeline.json` 並做規則檢查（旁白字數、字幕片段 ≤18 字、cap ≤14 字且不重複旁白、相鄰場景開頭不同、「這裡要注意」≤1 次）。
- `npm run story-render <folder> [--no-audio] [out.mp4]`：無語音版用 `--no-audio`；有 `audio/<cueId>.mp3` 時自動用真實長度並混音。
- `npm run story-audio <folder> [--force]`：逐句（cue）產 TTS；聲音與語氣可用環境變數 `OPENAI_TTS_VOICE`、`TTS_INSTRUCTIONS` 設定。建議無語音版確認後再跑（會呼叫付費 API）。

### story.json 結構
`scenes[] → cues[]`。每個 cue = 一句旁白（也是一句字幕來源）：

| 欄位 | 說明 |
|---|---|
| `text` | 旁白／字幕來源；切成單行字幕時每段 ≤18 字 |
| `say` | TTS 專用讀法（可選） |
| `cap` | 動畫上方極短重點，≤14 字，不重複旁白 |
| `lines` | 此句高亮的程式行；`[]` 為不高亮 |
| `focus` | `anim`／`code`（任何時刻只有一個焦點） |
| `ops[]` | 舞台元素變化；以 `at`＝念到該句的比例 0~1 綁旁白（不寫 from/to） |
| `pauseAfter` | 句尾停頓秒數 |

舞台元素以 id 保存狀態，跨 cue／跨場景延續（不重建已存在的列／卡片）。

### 版面與焦點（single-focus）
- layout（autoanim／場景）：`split`／`split2`（教學片預設）／`concept`（動畫大、程式縮底部）／`wide`／場景級 `fullcode`（片尾完整程式雙欄，非 autoanim layout）。
- 任何時刻只有一個焦點（`focus`），非焦點降到約 30–35% 亮度。程式碼一開始就直接出現，不逐字打字，只做逐行高亮。
- 字幕：固定在畫面下方同一位置、單行、≤18 字，依標點切片段並按語音長度比例切換；**字幕必須留在畫面上**。

### 顏色語意（全片固定）
黃＝處理中（程式高亮也固定黃）、綠＝已確定、灰＝已用過／跳過、紅＝無效／易錯／要注意。

### 內容規則
1. 每場景只講一個概念；旁白 45–70 字、每句宜 ≤20 字（樣板場景可更短）。
2. 先例子（用本題範例的真實輸入／數字）再通則；核心場景必回答「為什麼」。
3. 樣板（標頭、全域變數、main、讀入／清空）合併成一個約 10 秒的 code 場景，省下的時間給核心。
4. 不提前使用沒介紹過的名稱；每場景最多 1–2 個程式名稱，其餘用中文角色名；第一次用到才介紹。
5. 轉場詞輪流；「這裡要注意」全片最多 1 次；不重念畫面上已有的數字清單；符號寫成中文。
6. 結尾＝一句核心想法＋一個常見陷阱，不複述全文。
7. 第 1 場景就要讓範例輸入／輸出出現在畫面上。
8. 迴圈類動畫：第一輪慢且逐句對齊旁白、第二輪一句帶過、其餘快轉；狀態變化用「原地翻牌」，不要疊影轉場；每個狀態至少停留約 1.2 秒（快轉除外）。
9. 主視覺要貫穿全片（同一套元件語意從頭用到尾）。

---

## narration.json 格式與限制

```
{ "title": "影片標題（可選）",
  "scenes": { "<sceneId>": {
      "title": "場景標題≤16字（可選；預設沿用）",
      "merge_into_prev_scene": true,
      "cues": { "<cueId>": {
          "text": "口語旁白（必填；字幕自動切單行≤18字）",
          "cap": "畫面短標註≤14字，不與旁白重複（不寫＝不顯示）",
          "about": ["<arr>"],
          "claims": ["<var>=<值>","before.<var>=<值>"],
          "allow_numbers": [<n>], "allow_letters": ["<L>"], "letters_from": ["<arr>"],
          "say": "TTS 專用讀法", "pauseAfter": 0.6,
          "scene_break": "新場景標題",
          "merge_into_prev": true, "at": 0.7
      } } } },
  "extra_scenes": [
    {"after":"<sceneId>","id":"<x>","title":"…","layout":"fullcode",
     "cues":[{"id":"<xc>","text":"…","cap":"…","lines":[…]}]}
  ]
}
```
限制：
- 每個原 cue 都要有一筆（旁白或 `merge_into_prev`）。
- `merge_into_prev` 只能併「逐事件／開場」cue，且與被併入者的高亮行需相同；快轉 cue 不併。
- `extra_scenes` 可插純旁白場景；`layout="fullcode"`＝片尾完整程式雙欄（不捲動；單行 ≤58 字元；超過幾何容量則 apply 報錯）。
- 有圖／樹／佇列／map 元件時，每場逐事件 cue 會變多，cue 編號與無元件版不同——務必重跑 dump。

### 驗證涵蓋範圍（apply 一律會做）
- **(a) 畫面＝trace**：重放 ops 逐 cue 對 autoanim 的預期畫面文字；另以渲染器實際順序（cue 內依時間鍵排序）重放一次，確認合併後 cue 結束時畫面＝其最後一組事件的預期，且 op 群組順序沒被打亂；並斷言 op 內容與原骨架逐一相同。
- **(b) 旁白核對（擋幻覺）**：
  1. 旁白／cap 中「變數 是／變成／等於 值」與「變數 從 X 變成 Y」逐句抽出，對該 cue（含併入者各步）的 trace 值比對。
  2. 旁白／cap 中**所有數字**（阿拉伯或中文）必須落在該 cue 的事實集合：事件變動的值與索引、畫面上指標／純量目前值、`about` 陣列的內容與索引範圍、（開場／輸出 cue 才可用）範例輸入輸出數字；否則報錯，常數用 `allow_numbers`。「N 行」必須是本 cue／本場高亮行。
  3. 大寫字母須為：本 cue 字元變數／陣列值、事件變動的整數 k 對應的 A+k、開場／輸出 cue 的輸入輸出字母，或明確放行。
  4. `claims` 逐條比對。
  未涵蓋：定性說法是否為真、沒寫數字的因果解釋、被慣用語遮蔽的「一」、數字恰好在事實集合內但語意張冠李戴 → 重要主張請加 claims，最後仍由人審稿。
- **(c) 規則**：字幕 chunk≤18、cap≤14 且不重複旁白、相鄰場景開頭不同、「這裡要注意」≤1、每場旁白 45–70 字、每場提到的程式名稱≤3、旁白不含 `[]=<>{}` 等符號。

### 寫旁白的風格規則
- 台灣講師口語：先講這場要達成什麼、再講「為什麼這一步」；不逐字念程式碼。
- 數字用中文口說，符號寫成字；變數名一場最多 2–3 個，其餘用中文角色名。
- 逐事件很多時：前幾個講清楚，重複的用 merge 併掉，快轉 cue 一句帶過並帶出結論狀態。
- cap 是短標註（結論／角色），不重複旁白。
- 殘值格畫面顯示「?」——旁白不要提殘值的真值。
- 結尾＝一句核心想法＋一個常見陷阱。

---

## 動畫元件目錄（comps.py）

autoanim 在 `plan_display` 後呼叫 `comps.select()`：**程式用法＋trace 形狀都符合才認領變數**，被認領的陣列改用圖形呈現，其餘變數照舊。沒符合就維持通用陣列版（並由缺元件警示告知）。`--no-comps` 全關、`--disable graph,seq,slots,tree,keyed` 個別關。

每個元件先對「每個事件」預先算好完整畫面 `frames[ei]`＋獨立由 trace 推導的預期 `expects[ei]`，autoanim 只輸出與上次差異的 op。驗證鍵（verifylib）：`eid`（文字）、`eid#`（副標）、`eid@x|y|w|h`（位置）、`eid%color`、`set:前綴`（可見元素集合）、`seq:前綴:x|y`（可見卡片依座標排序的文字序列）。

| 元件 | 自動選用條件 | 畫面語意 | 驗證（trace 對拍） | 限制 |
|---|---|---|---|---|
| 圖 `graph` | `vector<int> g[N]`（arrv）、`vector<vector<int>>` 且有 push_back／逐鄰居走訪、或方陣且名稱像 g/adj/graph/mat/w；節點數符合上限 | 節點圓（編號＋副標＝dist／vis）＋邊線；有向帶箭頭；黃＝目前處理、綠＝已訪問、虛線＝在佇列／堆疊內 | 邊集合 `set:ge_`、節點文字／副標／顏色 | 版面自動（格狀／樹狀／環形）；過大退化；pair 型帶權圖 tracer 不支援 |
| 佇列／堆疊／優先佇列 `seq` | `queue/deque/stack/priority_queue<基本型別>` 且有變動（含手寫陣列＋head/tail／top） | 佇列水平卡片列（隊首黃）；堆疊右側直立欄（堆頂黃）；pq 依優先序；push／pop 動畫 | `seq:qc_<名>_:x|y`＝容器內容與順序 | 佇列 ≤12、堆疊 ≤8；pq 不畫堆的樹形 |
| 槽位列 `slots` | 長度 3–10 的整數陣列，最終為 0..n-1 的排列，且程式有 ≥2 處非初始化寫入；可伴隨 used／vis／計數陣列 | 上排人物卡片池、下排槽位；寫入時卡片移進槽位；used＝黃、放定綠 | 卡片 `@x|@y`、文字、副標、顏色 | 題目專屬虛線映射做不到；建議搭配 `--layout wide` |
| 樹 `tree` | 陣列表示：`lc/rc`、`left/right` 等成對＋寫入；可選 key、`root`；節點數符合上限 | 節點圓（編號＋key）＋父子連線；新節點綠、走訪中黃；中序 x＋深度 y | 邊集合 `set:te_`、節點文字 | 旋轉類只畫結果；struct＋指標型的樹 tracer 不支援 |
| map／set `keyed` | `map/unordered_map/set/multiset<基本型別>` 且有變動；≤2 列 | 依鍵排序的卡片列（key／value 副標）；新鍵綠、值變黃 | `seq:kc_<名>_:x`＝鍵序列、`kc_*#`＝值 | ≤12 個鍵；unordered 桶序不呈現；不支援 pair 鍵值 |

### 版面幾何
- 圖／樹佔左半（約 x 0–470），陣列區右移；堆疊佔右欄（約 x 1040–1196）；槽位列佔 chips 下方整條；佇列／map 各佔陣列區上方一列（約 66px）。
- 內容放不下時，陣列區自動「先扣固定高度再平分」，仍不夠才往舞台下方延伸（舞台框外沒有裁切）；`overlapcheck.py` 以 y≤585 為界。

### 指標▲
變數離開作用域、或未初始化殘值（第一次被改之前）時收起。黃＝本 cue 改變，綠＝本場先前已定案。

### 新增元件步驟
1. 在 `comps.py` 寫 Comp 子類（`prepare` 算 frames／expects）＋`select` 認領條件。
2. 補 `coverage.py` 的 `WITH_COMPONENT`（與 `COVERAGE`）。
3. `python3 sync_skill.py`（把覆蓋表寫回本檔的覆蓋表標記之間）。
4. 做一個本機樣本（`<名>.cpp/.in/.out`，不進 git）→ autoanim 對拍＋overlapcheck＋渲染抽影格＋`npx tsc --noEmit`＋舊樣本不退步。

---

## 缺元件偵測清單（detect.py）

圖（鄰接表／鄰接矩陣／pair 帶權）、演算法（BFS／DFS／Dijkstra／Floyd）、樹（left/right 陣列、struct Node＋指標）、槽位列（used 旗標＋位置陣列、next_permutation）、queue/stack/priority_queue、map/set、pair、struct/class、指標/new、字串處理（substr/find/getline）、遞迴、格子搜尋（dx/dy）、並查集、雜湊桶（% M）、超過顯示上限（trace 形狀）。

警示 status：支援／部分支援／退化／不支援。「不支援」項出片前一定要人工確認可接受。

### 元件覆蓋表（由 coverage.py 自動貼入，勿手改）
<!--COVERAGE-->
| 型態 | 無元件時 | 有元件時（autoanim 自動選用，條件符合才套用） | 仍缺什麼 | 補齊工時 |
|---|---|---|---|---|
| 圖（鄰接表 vector<int> g[N]／vector<vector<int>>） | 退化：以「列號＋不等長格子」文字列顯示（g: 0→1 2） | **部分支援**（元件 `graph`）：節點圓＋邊線＋當前節點（黃）／已訪問（綠，dist／vis 旗標）／在佇列（虛線）著色；節點 ≤20；版面自動：邊為 i±1／i±W 的格狀圖→格狀、無向樹→分層樹狀、其餘→環形 | pair 型態的邊權（vector<pair<int,int>> g[N]，tracer 未追蹤 pair）、>20 個節點、其他自訂佈局（座標輸入的平面圖） | pair 邊權約 1 天；>20 節點縮放約 1 天 |
| 圖（鄰接矩陣 int g[N][N]） | 退化：以 2D 格子顯示（≤8×10） | **部分支援**（元件 `graph`）：節點圓＋邊線（由 g[u][v]≠0 推得，有權則標在邊上並對拍邊權；Dijkstra 的 dist＋vis 以 dist 為副標、vis 為綠色），節點 ≤20；版面自動（格狀／樹狀／環形） | >20 個節點、座標輸入的自訂佈局、priority_queue<pair> 版 Dijkstra（需 pair 追蹤） | pair 追蹤約 1 天；大圖縮放約 1 天 |
| 帶權圖（vector<pair<int,int>> g[N]、struct Edge） | 不支援：pair／struct 未被追蹤，邊與權重完全不顯示 | —（未選用元件，維持左欄） | tracer 支援 pair、邊權標示 | 約 1 天（pair 追蹤＋邊權） |
| queue／deque | 退化：以陣列格近似（沒有 front／back、沒有移動） | **支援**（元件 `seq:queue`）：水平佇列卡片：push 從後面進、pop 從前面出，隊首黃色（≤12 項，超過不驗）；涵蓋 std::queue／deque 與手寫陣列 q[]＋head／tail（trace 轉移須為 push／pop，否則不認領） | — | — |
| stack | 退化：以陣列格近似（橫向） | **支援**（元件 `seq:stack`）：直立堆疊卡片：push 疊上、pop 取頂，堆頂黃色（≤8 項，超過不驗）；涵蓋 std::stack 與手寫陣列 st[]＋top（count／index 兩種慣例） | — | — |
| priority_queue | 退化：tracer 已支援（元素為 int 等基本型別），但沒有選用元件時畫面不顯示 | **部分支援**（元件 `seq:priority_queue`）：依優先序（頂→底）排列的卡片列，堆頂黃色（≤12 項） | 堆的內部樹形、pair／struct 元素（tracer 不支援） | 樹形堆約 1 天；pair 追蹤約 0.5 天 |
| 樹（以陣列表示：left[]／right[]／ch[][2]／parent[]） | 退化：以陣列格顯示（看不出樹形） | **部分支援**（元件 `tree`）：節點圓＋父子連線（left/right 陣列表示），新節點綠、走訪中節點黃；≤15 節點（節點直徑依深度／寬度自動縮） | 旋轉動畫（AVL／Splay）、>15 節點、struct＋指標型的樹 | 旋轉約 1 天；struct＋指標約 2–3 天 |
| 樹（struct Node＋指標／new） | 不支援：struct／指標未被追蹤，整棵樹不顯示 | —（未選用元件，維持左欄） | tracer 支援 struct 與指標（以位址對應節點編號） | 約 2–3 天 |
| 槽位列（排列／配置／信箱，如 res[] 為排列） | 退化：一般陣列格（沒有卡片移入槽位） | **部分支援**（元件 `slots`）：槽位列＋人物卡片移入槽位（自動條件：長度 3–10 的整數排列陣列且逐格寫入）；人員卡（字母＋個數）與空槽從計數階段就顯示，槽位標 最外／次外／中間（人員題）；伴隨陣列顯示在卡片副標；建議搭配 autoanim --layout wide（1.2 倍舞台） | 題目專屬的對應標示（如 rc 虛線映射、手工版的目標數量卡 tX）、不是排列型的配置／雜湊桶；卡片尺寸小於手工版 | 雜湊桶變體約 0.5 天 |
| 雜湊／桶（h[x % M]、bucket[]） | 退化：一般陣列格 | —（未選用元件，維持左欄） | 桶列＋元素落桶動畫 | 約 0.5 天（沿用槽位列） |
| map／unordered_map | 不支援：tracer 已支援（鍵值為基本型別），但沒有選用元件時畫面不顯示 | **部分支援**（元件 `keyed:map`）：依鍵排序的 key／value 卡片列（≤12 個鍵），新鍵綠、值變黃 | pair／struct 當鍵或值、>12 個鍵、unordered 的內部桶序 | 約 0.5 天 |
| set／unordered_set／multiset | 不支援：tracer 已支援（元素為基本型別），但沒有選用元件時畫面不顯示 | **部分支援**（元件 `keyed:set`）：依序排列的集合卡片列（≤12 個元素），新元素綠 | pair／struct 元素、>12 個元素 | 約 0.5 天 |
| pair／tuple | 不支援：含 pair 的變數／容器未被追蹤而不顯示 | —（未選用元件，維持左欄） | tracer 支援 pair（顯示成 a,b） | 約 0.5 天 |
| struct／class 物件 | 不支援：該類型變數不顯示 | —（未選用元件，維持左欄） | tracer 支援 struct 欄位展開＋卡片顯示 | 約 1.5 天 |
| 簡單 struct 的 vector（vector<P>，P 只有基本型別欄位） | 支援：每欄一列（p.s／p.i／p.j）＋索引 p[k] 的 ▲k | —（未選用元件，維持左欄） | — | — |
| 指標／new／鏈結串列 | 不支援：指標變數不顯示 | —（未選用元件，維持左欄） | tracer 支援指標＋節點鏈結圖 | 約 2–3 天 |
| 遞迴（呼叫堆疊／遞迴樹） | 退化：只顯示各次呼叫當下的參數變數（無堆疊、無遞迴樹） | —（未選用元件，維持左欄） | 呼叫堆疊或遞迴樹視圖 | 約 1.5 天 |
| 字串處理（string、逐字元） | 部分支援：字元以陣列格逐格顯示；不支援 substr 視窗／匹配標示 | —（未選用元件，維持左欄） | 字串視窗與匹配指示 | 約 0.5 天 |
| 格子搜尋／迷宮（2D 陣列＋dx/dy） | 部分支援：2D 格子（≤8×10）；無方向箭頭、無路徑著色 | —（未選用元件，維持左欄） | 路徑／訪問著色、方向指示 | 約 0.5 天 |
| 並查集（parent 陣列＋find/union） | 退化：parent 陣列格（看不出集合／樹） | —（未選用元件，維持左欄） | 森林（集合樹）視圖 | 約 1 天（沿用樹元件） |
| 動態規劃表（1D／2D dp） | 支援：陣列／2D 格子逐格著色 | —（未選用元件，維持左欄） | — | — |
| 一維／二維陣列、排序、雙指標、二分 | 支援：陣列格＋▲指標 | —（未選用元件，維持左欄） | — | — |
| 超過顯示上限（1D>16、2D>8×10、純量>8） | 部分支援：只顯示前段／左上 | —（未選用元件，維持左欄） | 縮放或分頁顯示 | 約 0.5 天 |
<!--/COVERAGE-->

> 這張表由 `python3 tools/cpe-tools/sync_skill.py` 從 `tools/cpe-tools/coverage.py` 產生並寫回本檔（`skill.md`）的標記之間。


---

## 附錄：舊版 steps[]／累加 cpp 模式（僅歷史參考）

舊流程用 `config.json`＋`code01.cpp`…累加切片、`npm run render`／`npm run gen-audio`；字幕整段貼、動畫手寫 from/to，易與旁白脫節。**新題一律走 Story 模式（上列）**；除非維護極舊資料夾，否則不要啟用累加四段式。

---

## 附錄 B：手動 config 流程（config.json＋累加 cpp）


### 何時用手動流程

當使用者想用手動切片方式從零建立一支教學影片時使用此流程，包括：

- 「建新影片」「從零開始做影片」
- 明確呼叫 `/cpe-video`
- 提供了程式碼並詢問如何製作成影片

### Project context

執行前先閱讀以下文件以了解專案結構與設定格式：

- `README.md` — 完整使用說明與 config.json 欄位定義、highlight 色表
- `public/example-bubble_sort/config.json` — 實際設定範例

---

### Phase 1：環境檢查

執行以下檢查，**任一失敗就停下來**告訴使用者如何修正，等修好再繼續：

1. 確認在專案根目錄執行（`public/` 目錄存在）
2. TTS 憑證已用環境變數提供：`TTS_PROVIDER=openai`（預設）需 `OPENAI_API_KEY`；`TTS_PROVIDER=google` 需 `GOOGLE_APPLICATION_CREDENTIALS` 指向存在的 JSON 金鑰檔

全部通過後回報：
```
✓ 環境檢查通過，開始建立影片。
```

---

### Phase 2：收集素材

**依序**詢問使用者（一次問一個）：

**問 1：資料夾名稱**

```
請輸入影片的資料夾名稱（英文、底線，例如 bubble_sort）：
```

- 確認 `public/<folder>/` 尚不存在
- 若已存在，警告使用者並詢問是否覆蓋；若使用者拒絕，回到本問重新詢問資料夾名稱

**問 2：題目說明**

```
請貼上題目說明或程式描述（OJ 題目、一段文字說明或自己寫的描述皆可）：
```

**問 3：完整 C++ 原始碼**

```
請貼上最終完整的 C++ 原始碼：
```

---

### Phase 3：AI 分析與切片

收到素材後進行分析，**不需要等使用者指示**，直接進行。

### 切片原則

標準結構為「題目 → 解法 → 程式碼逐步講解 → 結尾」四段式：

- **第 1 步：題目說明（code01.cpp）**：**只有題目說明的注解區塊，不含任何可執行程式碼**（連 `main()` 都不放）；`highlight` 指向注解行範圍
- **第 2 步：解法說明（沿用 code01.cpp）**：file 仍是 `code01.cpp`，**省略 `highlight`**，純粹用 `subtitle` 講解演算法策略與核心想法（為什麼這樣做、要枚舉/驗證/維護什麼），讓觀眾在看程式碼之前先掌握思路
- **中間步驟（code02.cpp … codeN-1.cpp）**：每步新增 1–12 行程式碼，每步都有清楚的教學重點；已出現的行不可再修改，每一行一出現就是最終解答的樣子
- **最後 1 步：結尾（沿用最後一個累加 cpp）**：file 用最後一個完整檔（例：`code09.cpp`），**省略 `highlight`**，`focusLine` 設為 `main` 函式起點（通常是 `#include` 之後的那一行），字幕做收尾總結——簡述演算法核心、視情況帶複雜度評估（例：「<輸入上限>，這個複雜度綽綽有餘」），最後以「感謝收看」收尾
- **合理步數**：通常 8–15 步（含題目、解法、結尾三個結構性步驟），依程式長度調整
- 辨識有意義的「里程碑」：引入標頭、函式定義、main 的各邏輯段落、輸入/處理/輸出

### 每步決定以下欄位

| 欄位 | 規則 |
|------|------|
| `label` | 簡短標題，顯示於時間軸 |
| `from` / `to` | 基礎 5 秒，每多 1 行**程式碼**加 0.8 秒，上限 12 秒；語音若超出會自動延伸，不用估太長 |
| `highlight`（選填）| 通常設定；**最後一步**展示完整程式碼時可省略，改用 `focusLine` 控制捲動位置 |
| `highlight.startLine` / `endLine` | 這步**新增**的行範圍（1-indexed，以該步累加後的 cpp 檔計算）|
| `highlight.color` | `blue` 一般宣告、`yellow` 迴圈/流程、`red` 條件判斷、`green` 輸出/關鍵操作、`lightblue` 函式宣告；該步有多種性質時取**主要**操作的顏色 |
| `focusLine`（選填）| 指定該行出現在畫面**頂部**；無 highlight 時用來控制捲動位置；最後一步通常設 1 讓程式碼從頭顯示 |
| `subtitle` | 引導式旁白（見下方規則）|

### Subtitle 寫法

- 以「接下來」「這裡」「我們」等引導詞開頭
- 說明「做什麼」與「為什麼」
- 長度 30–80 字，適合 5–15 秒語音（解法說明與結尾可放寬到 80–100 字）

依結構性步驟的不同寫法：

- **第 1 步（題目說明）**：將使用者提供的說明改寫為引導式介紹，例如：
  「這題給我們 <輸入描述>，目標是 <要求的輸出>。」
- **第 2 步（解法說明）**：用「解法很單純：」「核心想法是」「我們的做法是」等開頭，簡短交代「枚舉什麼 / 驗證什麼 / 為什麼可行」。例：
  「解法很單純：<枚舉什麼>，再 <驗證什麼>；<為什麼可行>。」
- **中間步驟**：常規引導式旁白
- **最後 1 步（結尾）**：用「總結一下：」「整體來說」等開頭，重述演算法核心，視情況帶上複雜度評估，最後以「感謝收看」收尾。例：
  「總結一下：<核心想法一句>。<複雜度評估一句>。這就是本題的完整解法，感謝收看。」

---

### Phase 4：確認步驟

### 模式選擇

Phase 3 分析完成後，**先詢問使用者偏好的確認方式**：

```
分析完成，共 <M> 步。請問你要：
  1. 逐步確認（預設）— 一步一步看，可即時修改
  2. 全部列出 — 一次看完所有步驟，再統一回報修改
```

依使用者選擇進入對應模式。

---

### 模式 A：逐步確認（預設）

**每次只展示一步**，等使用者回應後再顯示下一步。

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step N / M  —  <label>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
新增行：<startLine>–<endLine>
時長：<from>–<to> 秒
Highlight：<color>

新增的程式碼：
<只顯示這步新增的部分>

Subtitle：
「<subtitle 全文>」
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Enter] 確認  /  輸入修改要求
```

| 回應 | 動作 |
|------|------|
| Enter 或「OK」| 繼續下一步 |
| 修改 subtitle 的要求或直接給新文字 | 更新後重新顯示此步 |
| 調整 highlight 的要求 | 詢問新行範圍或顏色，更新後重新顯示 |
| 「重新切」或附說明 | 回到 Phase 3，AI 重新分析（可依使用者說明調整切法，例如「步數少一點」「把 swap 和排序合成一步」）|
| 「全部列出」| 切換到模式 B，從第一步開始列出所有剩餘步驟 |

---

### 模式 B：全部列出

一次顯示所有步驟，格式與模式 A 相同但連續排列，結尾加上：

```
以上共 <M> 步，有需要修改的地方請告訴我（例如：「第 3 步 subtitle 改成…」「第 5 步 highlight 改 red」），
沒問題就說「OK」。
```

| 回應 | 動作 |
|------|------|
| 「OK」或無修改意見 | 進入最終確認 |
| 指定步驟的修改要求（例如「第 3 步 subtitle 改成…」）| 套用修改後重新顯示**受影響的步驟**，再次確認 |
| 「逐步」或「回逐步模式」| 切換回模式 A，從第一步開始逐步確認 |
| 「重新切」或附說明 | 回到 Phase 3，AI 重新分析 |

---

### 最終確認（兩種模式共用）

```
✓ 全部 <M> 步確認完成。

即將產生：
  public/<folder>/code01.cpp … code<M>.cpp
  public/<folder>/config.json

確認產生檔案？[Y/n]
```

---

### Phase 5：產生檔案

建立 `public/<folder>/` 目錄，依序寫入：

### cpp 檔（累加式）

每個 cpp 檔是**完整累加**的版本，不是 diff：
- `code01.cpp`：只有第 1 步的內容
- `code02.cpp`：第 1 + 2 步的內容
- `codeN.cpp`：前 N 步所有內容（即完整程式）

保留原始縮排與格式。

### config.json

```json
{
  "steps": [
    {
      "label": "題目說明",
      "from": 0,
      "to": 7,
      "file": "code01.cpp",
      "subtitle": "這題給我們...",
      "highlight": {
        "startLine": 1,
        "endLine": 3,
        "color": "blue"
      }
    },
    {
      "label": "解法說明",
      "from": 7,
      "to": 15,
      "file": "code01.cpp",
      "subtitle": "解法很單純：..."
    },

    // ── 中間程式碼步驟（code02.cpp … codeN-1.cpp）省略 ──

    {
      "label": "結尾",
      "from": 90,
      "to": 100,
      "file": "codeN.cpp",
      "focusLine": 9,
      "subtitle": "總結一下：...感謝收看。"
    }
  ]
}
```

產生完成後顯示：

```
✓ 檔案產生完成！

  public/<folder>/
    config.json
    code01.cpp … code<M>.cpp

建議先預覽確認視覺效果：
  npm run dev

預覽沒問題後，告訴我「生成音檔」就開始產生語音。
```

---

### Phase 6：生成音檔

等使用者說「生成音檔」「OK 生成」或類似確認語後，執行：

```bash
npm run gen-audio <folder>
```

完成後：

```
✓ 音檔產生完成！

最後一步，輸出影片：
  npm run render <folder>
```

---

### 守則

- **不跳過環境檢查** — Phase 1 有問題就停，等使用者修好再繼續
- **四段式結構必備** — 切片時不能跳過「解法說明」與「結尾」這兩個結構性步驟；它們不對應任何程式碼新增、純粹用字幕承擔教學節奏
- **結構性步驟省略 highlight** — 解法說明與結尾步驟不要 `highlight`；行號維持 dim 色，焦點留給字幕
- **確認模式先問** — Phase 4 開始前詢問逐步或全部列出，兩種模式可互相切換
- **累加式 cpp** — 每個 cpp 檔包含所有前面步驟的程式碼，不是只有新增的部分
- **不主動 render** — render 讓使用者自己決定時機
- **gen-audio 等使用者確認** — 預覽後使用者說要才跑，不自動觸發
