import assert from "node:assert/strict";
import test from "node:test";
import { parseAnimationJson, toLine, toOptionalLine, toSeconds } from "./step-fields.ts";

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
  ];
  for (const [text, message] of bad) {
    const result = parseAnimationJson(text);
    assert.equal(result.ok, false, text);
    if (!result.ok) assert.match(result.error, message, text);
  }
});
