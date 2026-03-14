/*
 * Dominos 骨牌問題
 *
 * 骨牌可以排成長列，推倒一張會連鎖推倒下一張。但有時某張不會被前一張推倒，
 * 需要用手推；給定「用手推的骨牌」集合，求總共會倒幾張。
 *
 * 輸入：
 *   - 第一行：測資數 t
 *   - 每筆測資第一行：n, m, l（骨牌編號 1..n、推倒關係數 m、手推數量 l）
 *   - 接下來 m 行：x y 表示「x 倒會讓 y 倒」
 *   - 接下來 l 行：z 表示用手推的骨牌編號
 *
 * 輸出：每筆測資輸出一整數，為總共倒下的骨牌數。
 *
 * 範例：n=3，關係 1→2、2→3，手推 2 → 會倒 2 和 3，輸出 2。
 */

#include <iostream>
#include <vector>
#include <stack>

using namespace std;

void dfs(int node, vector<vector<int>>& graph, vector<bool>& visited, int& count) {
	stack<int> s;
	s.push(node);
	while (!s.empty()) {
		int current = s.top();
		s.pop();
		if (!visited[current]) {
			visited[current] = true;
			count++;
			for (int neighbor : graph[current]) {
				if (!visited[neighbor]) {
					s.push(neighbor);
				}
			}
		}
	}
}
