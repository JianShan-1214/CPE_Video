# 氣泡排序法教學影片設計

**日期：** 2026-03-14
**專案：** CPE_Video (Remotion)
**狀態：** 已核准

---

## 目標

製作一支以 C++ 示範氣泡排序法（Bubble Sort）的程式碼教學影片，採線性逐步建構方式，配合注解說明每個關鍵步驟的邏輯。

---

## 規格

| 項目 | 值 |
|------|----|
| 語言 | C++ |
| 教學風格 | 逐步建構 + 注解說明 |
| 每步時長 | 3 秒（90 frames @ 30fps） |
| 步驟數 | 8 |
| 總時長 | 約 24 秒 |
| 主題 | github-dark |
| 解析度 | 1080p（高度固定，寬度自動） |

---

## 影片步驟設計

每個步驟對應 `public/` 資料夾中的一個 `.cpp` 檔案，系統會依檔名排序自動載入。

### Step 1 — `code1.cpp`：引入標頭與命名空間
```cpp
// 氣泡排序法 (Bubble Sort)
// 原理：反覆比較相鄰元素，將較大的值往後推
#include <iostream>
using namespace std;
```

### Step 2 — `code2.cpp`：main() 與陣列宣告
新增 `main()` 函式，宣告一個未排序的整數陣列。

### Step 3 — `code3.cpp`：bubbleSort() 函式骨架
新增空的 `bubbleSort(int arr[], int n)` 函式，說明參數意義。

### Step 4 — `code4.cpp`：外層 for 迴圈
在 `bubbleSort` 中加入外層迴圈 `for (int i = 0; i < n - 1; i++)`，說明共需 n-1 輪。

### Step 5 — `code5.cpp`：內層 for 迴圈
加入內層迴圈 `for (int j = 0; j < n - i - 1; j++)`，說明每輪比較範圍會縮小。

### Step 6 — `code6.cpp`：比較與交換（核心邏輯）
加入 `if (arr[j] > arr[j+1])` 判斷與 `temp` 變數交換，這是氣泡排序的核心。

### Step 7 — `code7.cpp`：printArray() 輸出函式
新增輔助函式 `printArray(int arr[], int n)`，用於顯示陣列內容。

### Step 8 — `code8.cpp`：完整 main() 呼叫
在 `main()` 中呼叫 `printArray`（排序前）、`bubbleSort`、再 `printArray`（排序後）。

---

## 實作方式

- 在 `public/` 資料夾建立 `code1.cpp` 到 `code8.cpp`
- 移除原有的 `code1.tsx`～`code4.tsx`（或保留，視需求而定）
- 系統會自動依檔名字母排序載入所有 `code*` 開頭的檔案
- 每個步驟的程式碼是**累積的**（前一步的內容在後一步中保留，只新增部分）

---

## 注意事項

- C++ 檔案不會經過 Twoslash 處理，只有純語法高亮
- 注解使用繁體中文說明，幫助學習者理解每行邏輯
- 縮排使用 tab，與現有專案風格一致
