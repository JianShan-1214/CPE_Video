import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  ANIMATION_TRANSITION_FRAMES as T,
  getSegment,
  identityKeys,
  changedVars,
  gridCellSize,
  isValidAnimation,
  layoutArray,
  layoutGrid,
  layoutStacks,
  layoutVars,
  liftPath,
  varsTableLayout,
} from "./animation-layout.ts";

const byKey = (items) => Object.fromEntries(items.map((c) => [c.key, c]));

describe("getSegment", () => {
  it("splits duration evenly and eases each segment after the first", () => {
    assert.deepEqual(getSegment(0, 90, 3), { index: 0, progress: 1 });
    assert.deepEqual(getSegment(29, 90, 3), { index: 0, progress: 1 });
    assert.deepEqual(getSegment(30, 90, 3), { index: 1, progress: 0 });
    assert.equal(getSegment(30 + T / 2, 90, 3).progress, 0.5);
    assert.deepEqual(getSegment(30 + T, 90, 3), { index: 1, progress: 1 });
    assert.deepEqual(getSegment(89, 90, 3), { index: 2, progress: 1 });
  });

  it("clamps frames outside the step", () => {
    assert.equal(getSegment(-5, 90, 3).index, 0);
    assert.deepEqual(getSegment(500, 90, 3), { index: 2, progress: 1 });
  });

  it("handles a single-frame animation", () => {
    assert.deepEqual(getSegment(0, 90, 1), { index: 0, progress: 1 });
    assert.deepEqual(getSegment(89, 90, 1), { index: 0, progress: 1 });
  });
});

describe("identityKeys", () => {
  it("numbers duplicate values by occurrence", () => {
    assert.deepEqual(identityKeys([3, 1, 3, "3"]), ["3#0", "1#0", "3#1", "3#2"]);
  });
});

describe("layoutArray", () => {
  const swap = {
    type: "array",
    frames: [
      { values: [5, 2, 5], pointers: { i: 0, j: 1 }, caption: "before" },
      { values: [2, 5, 5], pointers: { i: 1, j: 2 }, mark: [0], caption: "after" },
    ],
  };

  it("moves swapped cells across each other, keeping duplicates stable", () => {
    const mid = byKey(layoutArray(swap, 30 + T / 2, 60).cells);
    assert.equal(mid["5#0"].x, 0.5);
    assert.equal(mid["2#0"].x, 0.5);
    assert.equal(mid["5#1"].x, 2);
    assert.ok(mid["5#0"].lift < 0 && mid["2#0"].lift > 0, "crossing cells arc apart");
    assert.equal(mid["5#1"].lift, 0);
    assert.equal(mid["2#0"].mark, 0.5);

    const end = byKey(layoutArray(swap, 59, 60).cells);
    assert.deepEqual([end["2#0"].x, end["5#0"].x, end["5#1"].x], [0, 1, 2]);
    assert.equal(end["2#0"].mark, 1);
  });

  it("tweens pointers between indices and crossfades captions", () => {
    const mid = layoutArray(swap, 30 + T / 2, 60);
    assert.deepEqual(
      mid.pointers.map((p) => [p.name, p.x, p.opacity]),
      [["i", 0.5, 1], ["j", 1.5, 1]],
    );
    assert.equal(mid.caption, "after");
    assert.equal(mid.captionOpacity, 0);
    assert.equal(mid.prevCaptionOpacity, 0);
    assert.equal(layoutArray(swap, 59, 60).captionOpacity, 1);
    assert.equal(mid.prevCaption, "before");
  });

  it("fades in new cells and pointers, fades out removed ones", () => {
    const anim = {
      type: "array",
      frames: [{ values: [1, 2], pointers: { i: 0 } }, { values: [2, 3], pointers: { k: 1 } }],
    };
    const mid = layoutArray(anim, 30 + T / 2, 60);
    const cells = byKey(mid.cells);
    assert.equal(cells["1#0"].opacity, 0.5);
    assert.equal(cells["3#0"].opacity, 0.5);
    assert.equal(cells["2#0"].x, 0.5);
    assert.deepEqual(byKey(mid.pointers.map((p) => ({ ...p, key: p.name }))).k.opacity, 0.5);
    assert.equal(mid.slotCount, 2);
  });

  it("drops pointers that are not integer indices inside that frame", () => {
    const anim = {
      type: "array",
      frames: [
        { values: [1, 2, 3], pointers: { neg: -3, far: 3, frac: 1.5, ok: 2 } },
        { values: [1, 2], pointers: { ok: 2, k: 1 } },
      ],
    };
    assert.deepEqual(layoutArray(anim, 0, 60).pointers.map((p) => p.name), ["ok"]);
    // ok 在第二格越界 → 淡出、停在原位，不會畫到 index 2 以外
    const mid = byKey(layoutArray(anim, 30 + T / 2, 60).pointers.map((p) => ({ ...p, key: p.name })));
    assert.deepEqual([mid.ok.x, mid.ok.opacity, mid.k.x], [2, 0.5, 1]);
  });

  it("renders a single-frame animation statically", () => {
    const out = layoutArray({ type: "array", frames: [{ values: [7] }] }, 40, 60);
    assert.deepEqual(out.cells.map((c) => [c.key, c.x, c.opacity, c.lift]), [["7#0", 0, 1, 0]]);
    assert.equal(out.caption, "");
  });
});

describe("layoutStacks", () => {
  const anim = {
    type: "stacks",
    labels: ["A", "B"],
    frames: [
      { stacks: [[1, 2], []] },
      { stacks: [[1], [2]] },
    ],
  };

  it("moves a block between stacks by id over the top lane", () => {
    // 2 從 (0,1) 到 (1,0)，lane = maxHeight = 2：上 1、橫 1、下 2，一半時剛好橫移完
    const mid = byKey(layoutStacks(anim, 30 + T / 2, 60).blocks);
    assert.deepEqual([mid["2#0"].stack, mid["2#0"].level], [1, 2]);
    assert.deepEqual([mid["1#0"].stack, mid["1#0"].level], [0, 0]);
    const end = byKey(layoutStacks(anim, 59, 60).blocks);
    assert.deepEqual([end["2#0"].stack, end["2#0"].level], [1, 0]);
  });

  it("reports stable layout bounds across frames", () => {
    const out = layoutStacks(anim, 0, 60);
    assert.equal(out.stackCount, 2);
    assert.equal(out.maxHeight, 2);
  });
});

describe("liftPath", () => {
  const from = { stack: 0, level: 1 };
  const to = { stack: 2, level: 0 };
  // lane 3：上 2、橫 2、下 3，總長 7
  it("goes up, across, then down", () => {
    assert.deepEqual(liftPath(from, to, 0, 3), from);
    assert.deepEqual(liftPath(from, to, 1 / 7, 3), { stack: 0, level: 2 });
    assert.deepEqual(liftPath(from, to, 2 / 7, 3), { stack: 0, level: 3 });
    assert.deepEqual(liftPath(from, to, 3 / 7, 3), { stack: 1, level: 3 });
    assert.deepEqual(liftPath(from, to, 4 / 7, 3), { stack: 2, level: 3 });
    assert.deepEqual(liftPath(from, to, 1, 3), to);
  });

  it("moves leftwards too, and straight within the same stack", () => {
    // 反向：上 3、橫 2、下 2
    assert.deepEqual(liftPath(to, from, 4 / 7, 3), { stack: 1, level: 3 });
    assert.deepEqual(liftPath({ stack: 1, level: 2 }, { stack: 1, level: 0 }, 0.5, 3), { stack: 1, level: 1 });
  });
});

describe("isValidAnimation", () => {
  it("accepts well-formed animations", () => {
    assert.ok(isValidAnimation({ type: "array", frames: [{ values: [1, "x"], pointers: { i: 0 }, mark: [0] }] }));
    assert.ok(isValidAnimation({ type: "stacks", labels: ["A"], frames: [{ stacks: [[1], []] }] }));
    // 上限剛好：16 格、8 堆 × 12 塊；指標越界只是不畫，不會整段拒絕
    assert.ok(isValidAnimation({ type: "array", frames: [{ values: Array(16).fill(0), pointers: { j: -1 } }] }));
    const full = Array.from({ length: 8 }, (_, s) => Array.from({ length: 12 }, (_, l) => s * 12 + l));
    assert.ok(isValidAnimation({ type: "stacks", frames: [{ stacks: full }] }));
  });

  it("rejects empty or malformed input", () => {
    for (const bad of [
      undefined,
      null,
      "array",
      {},
      { type: "array", frames: [] },
      { type: "array" },
      { type: "tree", frames: [{}] },
      { type: "array", frames: [{ values: "123" }] },
      { type: "array", frames: [{ values: [1], pointers: { i: "0" } }] },
      { type: "array", frames: [{ values: [1], mark: 0 }] },
      { type: "array", frames: [{ values: [{}] }] },
      { type: "stacks", frames: [{ stacks: [1, 2] }] },
      { type: "stacks", labels: "A", frames: [{ stacks: [[1]] }] },
      { type: "stacks", frames: [{ stacks: [[1]], caption: 3 }] },
      { type: "array", frames: [{ values: [1, Infinity] }] },
      { type: "array", frames: [{ values: [NaN] }] },
      { type: "array", frames: [{ values: [1], pointers: { i: Infinity } }] },
      { type: "array", frames: [{ values: [1], mark: [NaN] }] },
      { type: "stacks", frames: [{ stacks: [[-Infinity]] }] },
      { type: "array", frames: [{ values: Array.from({ length: 17 }, (_, i) => i) }] },
      { type: "stacks", frames: [{ stacks: Array.from({ length: 9 }, () => []) }] },
      { type: "stacks", labels: Array(9).fill("x"), frames: [{ stacks: [[1]] }] },
      { type: "stacks", frames: [{ stacks: [Array.from({ length: 13 }, (_, i) => i)] }] },
      { type: "stacks", frames: [{ stacks: [[1, 2], [1]] }] },
      { type: "stacks", frames: [{ stacks: [[1], ["1"]] }] },
    ]) {
      assert.equal(isValidAnimation(bad), false, JSON.stringify(bad));
    }
  });
});

describe("null optional fields", () => {
  const arr = {
    type: "array",
    frames: [
      { values: [2, 1], pointers: null, mark: null, caption: null },
      { values: [1, 2], pointers: { i: 0 }, mark: [0], caption: null },
    ],
  };
  const stk = {
    type: "stacks",
    labels: null,
    frames: [
      { stacks: [[1], []], caption: null },
      { stacks: [[], [1]], caption: "move" },
    ],
  };

  it("validates null like undefined", () => {
    assert.equal(isValidAnimation(arr), true);
    assert.equal(isValidAnimation(stk), true);
  });

  it("lays out null fields without throwing", () => {
    for (const f of [0, 40, 89]) {
      const a = layoutArray(arr, f, 90);
      assert.equal(a.cells.length >= 2, true);
      assert.equal(typeof a.caption, "string");
      const s = layoutStacks(stk, f, 90);
      assert.equal(s.stackCount, 2);
      assert.equal(typeof s.caption, "string");
    }
    const a0 = layoutArray(arr, 0, 90);
    assert.deepEqual(a0.pointers, []);
    assert.equal(a0.caption, "");
    assert.equal(a0.captionOpacity, 1);
  });
});

describe("grid / vars validation", () => {
  const grid12 = Array.from({ length: 12 }, (_, r) => Array.from({ length: 12 }, (_, c) => r * 12 + c));
  const vars8 = Object.fromEntries(Array.from({ length: 8 }, (_, i) => [`v${i}`, i]));

  it("accepts grids up to 12x12, ragged rows, scalar cells, vars on any type", () => {
    assert.ok(isValidAnimation({ type: "grid", frames: [{ cells: grid12, mark: [[0, 0], [99, 99]], vars: vars8 }] }));
    assert.ok(isValidAnimation({ type: "grid", frames: [{ cells: [[1], [null, true, "x"], []], mark: null, vars: null }] }));
    assert.ok(isValidAnimation({ type: "vars", frames: [{ vars: { a: 1, s: "x", b: false, n: null } }, { vars: {}, caption: null }] }));
    assert.ok(isValidAnimation({ type: "array", frames: [{ values: [1], vars: { i: 0 } }] }));
    assert.ok(isValidAnimation({ type: "stacks", frames: [{ stacks: [[1]], vars: { top: 1 } }] }));
  });

  it("rejects oversize or malformed grid / vars", () => {
    for (const bad of [
      { type: "grid", frames: [{ cells: [...grid12, [1]] }] },
      { type: "grid", frames: [{ cells: [[...grid12[0], 1]] }] },
      { type: "grid", frames: [{ cells: [] }] },
      { type: "grid", frames: [{ cells: [1, 2] }] },
      { type: "grid", frames: [{ cells: [[{}]] }] },
      { type: "grid", frames: [{ cells: [[NaN]] }] },
      { type: "grid", frames: [{ cells: [[1]], mark: [0, 0] }] },
      { type: "grid", frames: [{ cells: [[1]], mark: [[0, Infinity]] }] },
      { type: "grid", frames: [{}] },
      { type: "vars", frames: [{}] },
      { type: "vars", frames: [{ vars: null }] },
      { type: "vars", frames: [{ vars: [1] }] },
      { type: "vars", frames: [{ vars: { ...vars8, x: 1 } }] },
      { type: "vars", frames: [{ vars: { a: Infinity } }] },
      { type: "vars", frames: [{ vars: { a: [1] } }] },
      { type: "array", frames: [{ values: [1], vars: { a: {} } }] },
      { type: "stacks", frames: [{ stacks: [[1]], vars: "i=0" }] },
    ]) {
      assert.equal(isValidAnimation(bad), false, JSON.stringify(bad));
    }
  });
});

describe("layoutGrid", () => {
  const anim = {
    type: "grid",
    frames: [
      { cells: [[1, 2], [3]], mark: [[0, 0]], caption: "a" },
      { cells: [[1, 5], [null, 4]], mark: [[1, 1], [7, 7]], caption: "b" },
    ],
  };

  it("keeps cells in place, crossfades changed values, tweens marks", () => {
    const mid = byKey(layoutGrid(anim, 30 + T / 2, 60).cells);
    assert.deepEqual([mid["0,1"].r, mid["0,1"].c], [0, 1]);
    assert.deepEqual([mid["0,1"].prevText, mid["0,1"].text], ["2", "5"]);
    assert.deepEqual([mid["0,1"].prevTextOpacity, mid["0,1"].textOpacity, mid["0,1"].opacity], [0, 0, 1]);
    assert.equal(mid["0,0"].prevTextOpacity, 0);
    assert.equal(mid["0,0"].mark, 0.5);
    assert.equal(mid["1,1"].opacity, 0.5, "new cell fades in");
    assert.equal(mid["1,0"].text, "", "null renders empty");
    assert.equal(mid["7,7"], undefined, "out-of-range mark ignored");
  });

  it("reports stable bounds over ragged rows", () => {
    const out = layoutGrid(anim, 0, 60);
    assert.deepEqual([out.rows, out.cols, out.caption], [2, 2, "a"]);
  });
});

describe("gridCellSize", () => {
  it("caps at array size and shrinks to fit the tighter axis", () => {
    assert.deepEqual(gridCellSize(3, 4, 560, 500), { slotW: 80, slotH: 80, cellW: 72, cellH: 72 });
    const tall = gridCellSize(12, 12, 560, 420);
    assert.deepEqual([tall.slotH, tall.slotW], [35, 560 / 12], "widens past height when width allows");
    assert.equal(gridCellSize(12, 12, 400, 420).slotW, 400 / 12, "never wider than the panel");
    assert.equal(gridCellSize(2, 12, 560, 420).slotH, 560 / 12);
  });
});

describe("vars table", () => {
  it("detects new and changed values only after the first frame", () => {
    assert.deepEqual([...changedVars({ i: 1, s: "a", n: null }, { i: 2, s: "a", n: null, k: 0 }, true)], ["i", "k"]);
    assert.deepEqual([...changedVars(undefined, { i: 1 }, false)], []);
    assert.deepEqual([...changedVars(null, { i: 1 }, true)], ["i"]);
  });

  it("uses two columns below a main visual when > 4 entries", () => {
    assert.deepEqual(varsTableLayout(5, false), { columns: 2, rows: 3, rowH: 40, fontSize: 22, height: 120 });
    assert.equal(varsTableLayout(4, false).columns, 1);
    assert.equal(varsTableLayout(0, false).height, 0);
    assert.equal(varsTableLayout(8, true).columns, 1);
  });

  it("highlights changed values and crossfades them", () => {
    const frames = [{ vars: { i: 0, j: 1 } }, { vars: { i: 0, j: 2 } }, { vars: { i: 1, j: 2 } }];
    const f0 = byKey(layoutVars(frames, 0, 1, false).items.map((v) => ({ ...v, key: v.name })));
    assert.deepEqual([f0.i.mark, f0.j.mark], [0, 0]);
    const f1 = byKey(layoutVars(frames, 1, 0.5, false).items.map((v) => ({ ...v, key: v.name })));
    assert.deepEqual([f1.j.mark, f1.j.prevText, f1.j.text, f1.i.mark], [0.5, "1", "2", 0]);
    // 第 2 格：j 的高亮退掉、i 的高亮亮起
    const f2 = byKey(layoutVars(frames, 2, 1, false).items.map((v) => ({ ...v, key: v.name })));
    assert.deepEqual([f2.i.mark, f2.j.mark, f2.i.text], [1, 0, "1"]);
  });

  it("fades rows in and out when the variable set changes", () => {
    const frames = [{ vars: { i: 0 } }, { vars: { k: true } }, {}];
    const mid = byKey(layoutVars(frames, 1, 0.5, false).items.map((v) => ({ ...v, key: v.name })));
    assert.deepEqual([mid.i.opacity, mid.k.opacity, mid.k.text], [0.5, 0.5, "true"]);
    assert.deepEqual(layoutVars(frames, 2, 1, false).items.map((v) => [v.name, v.opacity]), [["k", 0]]);
  });
});
