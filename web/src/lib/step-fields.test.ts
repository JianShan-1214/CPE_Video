import assert from "node:assert/strict";
import test from "node:test";
import { parseAnimationJson, parseTraceJson, toLine, toOptionalLine, toSeconds } from "./step-fields.ts";

test("line inputs never store 0, fractions or NaN", () => {
  assert.equal(toLine(""), 1);
  assert.equal(toLine("0"), 1);
  assert.equal(toLine("-3"), 1);
  assert.equal(toLine("1.5"), 1);
  assert.equal(toLine("7"), 7);
  assert.equal(toOptionalLine(""), undefined);
  assert.equal(toOptionalLine("0"), 1);
  assert.equal(toOptionalLine("12"), 12);
});

test("seconds inputs skip empty / half-typed values", () => {
  assert.equal(toSeconds(""), null);
  assert.equal(toSeconds("-"), null);
  assert.equal(toSeconds("2.5"), 2.5);
  assert.equal(toSeconds("-1", 0), 0);
});

test("animation JSON: empty clears, valid shapes pass through", () => {
  assert.deepEqual(parseAnimationJson("  "), { ok: true, value: undefined });
  const array = {
    type: "array",
    frames: [{ values: [3, "x"], pointers: { i: 0 }, mark: [1], caption: "開始" }],
  };
  assert.deepEqual(parseAnimationJson(JSON.stringify(array)), { ok: true, value: array });
  const stacks = { type: "stacks", labels: ["A"], frames: [{ stacks: [[1, 2], []] }] };
  assert.deepEqual(parseAnimationJson(JSON.stringify(stacks)), { ok: true, value: stacks });
});

test("animation JSON: bad input is rejected with a message", () => {
  const bad: [string, RegExp][] = [
    ["{", /JSON 格式錯誤/],
    ["[]", /物件/],
    ['{"type":"tree","frames":[{}]}', /type/],
    ['{"type":"array","frames":[]}', /frames/],
    ['{"type":"array","frames":[{"values":[1,null]}]}', /values/],
    ['{"type":"array","frames":[{"values":[1],"pointers":{"i":1.5}}]}', /pointers/],
    ['{"type":"array","frames":[{"values":[1],"mark":null}]}', /mark/],
    ['{"type":"array","frames":[{"values":[1],"caption":3}]}', /caption/],
    ['{"type":"stacks","frames":[{"stacks":[1]}]}', /stacks/],
    ['{"type":"stacks","labels":[1],"frames":[{"stacks":[]}]}', /labels/],
    ['{"type":"array","frames":[{"values":[1],"vars":[1]}]}', /vars/],
    ['{"type":"array","frames":[{"values":[1],"vars":{"i":[1]}}]}', /vars/],
    ['{"type":"stacks","frames":[{"stacks":[],"vars":null}]}', /vars/],
    ['{"type":"grid","frames":[{"cells":[]}]}', /cells/],
    ['{"type":"grid","frames":[{"cells":[1]}]}', /cells/],
    ['{"type":"grid","frames":[{"cells":[[{}]]}]}', /cells/],
    ['{"type":"grid","frames":[{"cells":[[1]],"mark":[[0]]}]}', /mark/],
    ['{"type":"grid","frames":[{"cells":[[1]],"mark":[0,0]}]}', /mark/],
    ['{"type":"vars","frames":[{"caption":"x"}]}', /vars/],
  ];
  for (const [text, message] of bad) {
    const result = parseAnimationJson(text);
    assert.equal(result.ok, false, text);
    if (!result.ok) assert.match(result.error, message, text);
  }
});

test("animation JSON: grid, vars and frame vars pass through", () => {
  const shapes = [
    { type: "array", frames: [{ values: [1], vars: { i: 0, ok: true, s: "a", none: null } }] },
    { type: "stacks", frames: [{ stacks: [[1]], vars: { n: 1 } }] },
    { type: "grid", frames: [{ cells: [[1, null], ["#", true, 2.5]], mark: [[0, 1]], caption: "c", vars: { i: 1 } }] },
    { type: "vars", frames: [{ vars: { sum: 3 } }, { vars: {}, caption: "空" }] },
  ];
  for (const a of shapes) assert.deepEqual(parseAnimationJson(JSON.stringify(a)), { ok: true, value: a });
});

test("trace JSON: empty → null, valid plan passes, bad plan names the field", () => {
  assert.deepEqual(parseTraceJson(" "), { ok: true, value: null });
  const plan = {
    line: 7,
    show: { as: "array", expr: "a", length: null },
    pointers: ["i", "j"],
    vars: [],
    maxFrames: 8,
    caption: null,
  };
  assert.deepEqual(parseTraceJson(JSON.stringify(plan)), { ok: true, value: plan });
  for (const when of ["before", "after"]) {
    assert.deepEqual(parseTraceJson(JSON.stringify({ ...plan, when })), { ok: true, value: { ...plan, when } });
  }
  const bad: [unknown, RegExp][] = [
    [[], /物件/],
    [{ ...plan, line: 0 }, /line/],
    [{ ...plan, show: { as: "tree" } }, /show\.as/],
    [{ ...plan, show: { as: "array", expr: 1 } }, /show\.expr/],
    [{ ...plan, pointers: "i" }, /pointers/],
    [{ ...plan, vars: undefined }, /vars/],
    [{ ...plan, maxFrames: 13 }, /maxFrames/],
    [{ ...plan, caption: 1 }, /caption/],
    [{ ...plan, when: "during" }, /when/],
    [{ ...plan, when: null }, /when/],
  ];
  for (const [t, message] of bad) {
    const result = parseTraceJson(JSON.stringify(t));
    assert.equal(result.ok, false, JSON.stringify(t));
    if (!result.ok) assert.match(result.error, message, JSON.stringify(t));
  }
  assert.equal(parseTraceJson("{").ok, false);
});
