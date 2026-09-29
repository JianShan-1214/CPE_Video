import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  ANIMATION_TRANSITION_FRAMES as T,
  getSegment,
  identityKeys,
  isValidAnimation,
  layoutArray,
  layoutStacks,
  liftPath,
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
