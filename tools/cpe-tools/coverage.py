"""元件覆蓋表：偵測（detect.py）與 SKILL.md 共用同一份。status：supported／partial／degraded／unsupported
now＝目前實際呈現；missing＝缺什麼；eta＝補齊預估工時（人時，含驗證）。改元件狀態時只改這裡，再用 `python3 coverage.py --md` 重貼 SKILL。"""
COVERAGE = {
    "graph_adj": dict(name="圖（鄰接表 vector<int> g[N]／vector<vector<int>>）", status="degraded",
        now="以「列號＋不等長格子」文字列顯示（g: 0→1 2）", missing="節點圓＋邊連線、當前節點／已訪問著色", eta="約 1 天（圖元件）"),
    "graph_matrix": dict(name="圖（鄰接矩陣 int g[N][N]）", status="degraded",
        now="以 2D 格子顯示（≤8×10）", missing="節點圓＋邊連線、邊權標示", eta="約 0.5 天（沿用圖元件）"),
    "graph_weighted": dict(name="帶權圖（vector<pair<int,int>> g[N]、struct Edge）", status="unsupported",
        now="pair／struct 未被追蹤，邊與權重完全不顯示", missing="tracer 支援 pair、邊權標示", eta="約 1 天（pair 追蹤＋邊權）"),
    "queue": dict(name="queue／deque", status="degraded", now="以陣列格近似（沒有 front／back、沒有移動）", missing="水平佇列、push／pop 移動動畫", eta="約 0.5 天"),
    "stack": dict(name="stack", status="degraded", now="以陣列格近似（橫向）", missing="直立堆疊、push／pop 動畫", eta="約 0.5 天"),
    "priority_queue": dict(name="priority_queue", status="degraded", now="tracer 已支援（元素為 int 等基本型別），但沒有選用元件時畫面不顯示", missing="優先序卡片列（SeqComp）", eta="已完成（自動選用）"),
    "tree_array": dict(name="樹（以陣列表示：left[]／right[]／ch[][2]／parent[]）", status="degraded",
        now="以陣列格顯示（看不出樹形）", missing="節點連線樹狀圖", eta="約 1 天（樹元件）"),
    "tree_struct": dict(name="樹（struct Node＋指標／new）", status="unsupported", now="struct／指標未被追蹤，整棵樹不顯示",
        missing="tracer 支援 struct 與指標（以位址對應節點編號）", eta="約 2–3 天"),
    "slots": dict(name="槽位列（排列／配置／信箱，如 res[] 為排列）", status="degraded", now="一般陣列格（沒有卡片移入槽位）", missing="槽位列＋卡片移動", eta="約 1 天"),
    "hash": dict(name="雜湊／桶（h[x % M]、bucket[]）", status="degraded", now="一般陣列格", missing="桶列＋元素落桶動畫", eta="約 0.5 天（沿用槽位列）"),
    "map": dict(name="map／unordered_map", status="unsupported", now="tracer 已支援（鍵值為基本型別），但沒有選用元件時畫面不顯示", missing="鍵值卡片列（KeyedComp）", eta="已完成（自動選用）"),
    "set": dict(name="set／unordered_set／multiset", status="unsupported", now="tracer 已支援（元素為基本型別），但沒有選用元件時畫面不顯示", missing="集合卡片列（KeyedComp）", eta="已完成（自動選用）"),
    "pair": dict(name="pair／tuple", status="unsupported", now="含 pair 的變數／容器未被追蹤而不顯示", missing="tracer 支援 pair（顯示成 a,b）", eta="約 0.5 天"),
    "struct": dict(name="struct／class 物件", status="unsupported", now="該類型變數不顯示", missing="tracer 支援 struct 欄位展開＋卡片顯示", eta="約 1.5 天"),
    "struct_simple": dict(name="簡單 struct 的 vector（vector<P>，P 只有基本型別欄位）", status="supported",
        now="每欄一列（p.s／p.i／p.j）＋索引 p[k] 的 ▲k", missing="—", eta="—"),
    "pointer": dict(name="指標／new／鏈結串列", status="unsupported", now="指標變數不顯示", missing="tracer 支援指標＋節點鏈結圖", eta="約 2–3 天"),
    "recursion": dict(name="遞迴（呼叫堆疊／遞迴樹）", status="degraded", now="只顯示各次呼叫當下的參數變數（無堆疊、無遞迴樹）", missing="呼叫堆疊或遞迴樹視圖", eta="約 1.5 天"),
    "string": dict(name="字串處理（string、逐字元）", status="partial", now="字元以陣列格逐格顯示；不支援 substr 視窗／匹配標示", missing="字串視窗與匹配指示", eta="約 0.5 天"),
    "grid": dict(name="格子搜尋／迷宮（2D 陣列＋dx/dy）", status="partial", now="2D 格子（≤8×10）；無方向箭頭、無路徑著色", missing="路徑／訪問著色、方向指示", eta="約 0.5 天"),
    "union_find": dict(name="並查集（parent 陣列＋find/union）", status="degraded", now="parent 陣列格（看不出集合／樹）", missing="森林（集合樹）視圖", eta="約 1 天（沿用樹元件）"),
    "dp_table": dict(name="動態規劃表（1D／2D dp）", status="supported", now="陣列／2D 格子逐格著色", missing="—", eta="—"),
    "array": dict(name="一維／二維陣列、排序、雙指標、二分", status="supported", now="陣列格＋▲指標", missing="—", eta="—"),
    "truncated": dict(name="超過顯示上限（1D>16、2D>8×10、純量>8）", status="partial", now="只顯示前段／左上", missing="縮放或分頁顯示", eta="約 0.5 天"),
}
STATUS_ZH = dict(supported="支援", partial="部分支援", degraded="退化", unsupported="不支援")

# 元件被「實際選用」時的狀態：{偵測型別: (元件名, 狀態, 現況說明)}。元件名＝autoanim 的 plan["components"] 內的名稱。
WITH_COMPONENT = {
    "graph_adj": ("graph", "partial", "節點圓＋邊線＋當前節點（黃）／已訪問（綠，dist／vis 旗標）／在佇列（虛線）著色；節點 ≤20；版面自動：邊為 i±1／i±W 的格狀圖→格狀、無向樹→分層樹狀、其餘→環形",
                  "pair 型態的邊權（vector<pair<int,int>> g[N]，tracer 未追蹤 pair）、>20 個節點、其他自訂佈局（座標輸入的平面圖）", "pair 邊權約 1 天；>20 節點縮放約 1 天"),
    "graph_matrix": ("graph", "partial", "節點圓＋邊線（由 g[u][v]≠0 推得，有權則標在邊上並對拍邊權；Dijkstra 的 dist＋vis 以 dist 為副標、vis 為綠色），節點 ≤20；版面自動（格狀／樹狀／環形）",
                     ">20 個節點、座標輸入的自訂佈局、priority_queue<pair> 版 Dijkstra（需 pair 追蹤）", "pair 追蹤約 1 天；大圖縮放約 1 天"),
    "queue": ("seq:queue", "supported", "水平佇列卡片：push 從後面進、pop 從前面出，隊首黃色（≤12 項，超過不驗）；涵蓋 std::queue／deque 與手寫陣列 q[]＋head／tail（trace 轉移須為 push／pop，否則不認領）", "—", "—"),
    "stack": ("seq:stack", "supported", "直立堆疊卡片：push 疊上、pop 取頂，堆頂黃色（≤8 項，超過不驗）；涵蓋 std::stack 與手寫陣列 st[]＋top（count／index 兩種慣例）", "—", "—"),
    "priority_queue": ("seq:priority_queue", "partial", "依優先序（頂→底）排列的卡片列，堆頂黃色（≤12 項）",
                       "堆的內部樹形、pair／struct 元素（tracer 不支援）", "樹形堆約 1 天；pair 追蹤約 0.5 天"),
    "slots": ("slots", "partial", "槽位列＋人物卡片移入槽位（自動條件：長度 3–10 的整數排列陣列且逐格寫入）；人員卡（字母＋個數）與空槽從計數階段就顯示，槽位標 最外／次外／中間（人員題）；伴隨陣列顯示在卡片副標；建議搭配 autoanim --layout wide（1.2 倍舞台）",
              "題目專屬的對應標示（如 rc 虛線映射、手工版的目標數量卡 tX）、不是排列型的配置／雜湊桶；卡片尺寸小於手工版", "雜湊桶變體約 0.5 天"),
    "tree_array": ("tree", "partial", "節點圓＋父子連線（left/right 陣列表示），新節點綠、走訪中節點黃；≤15 節點（節點直徑依深度／寬度自動縮）",
                   "旋轉動畫（AVL／Splay）、>15 節點、struct＋指標型的樹", "旋轉約 1 天；struct＋指標約 2–3 天"),
    "map": ("keyed:map", "partial", "依鍵排序的 key／value 卡片列（≤12 個鍵），新鍵綠、值變黃",
            "pair／struct 當鍵或值、>12 個鍵、unordered 的內部桶序", "約 0.5 天"),
    "set": ("keyed:set", "partial", "依序排列的集合卡片列（≤12 個元素），新元素綠", "pair／struct 元素、>12 個元素", "約 0.5 天"),
}


def md():
    out = ["| 型態 | 無元件時 | 有元件時（autoanim 自動選用，條件符合才套用） | 仍缺什麼 | 補齊工時 |", "|---|---|---|---|---|"]
    for k, v in COVERAGE.items():
        w = WITH_COMPONENT.get(k)
        base = f"{STATUS_ZH[v['status']]}：{v['now']}"
        if w:
            out.append(f"| {v['name']} | {base} | **{STATUS_ZH[w[1]]}**（元件 `{w[0]}`）：{w[2]} | {w[3] if len(w) > 3 else v['missing']} | {w[4] if len(w) > 4 else v['eta']} |")
        else:
            out.append(f"| {v['name']} | {base} | —（未選用元件，維持左欄） | {v['missing']} | {v['eta']} |")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    if "--md" in sys.argv: print(md())
