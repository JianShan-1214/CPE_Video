import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  computeStepScroll,
  getLineNumberAppearance,
} from "./step-visual-elements.ts";

describe("computeStepScroll", () => {
  it("keeps the previous scroll when both focusLine and highlight are absent", () => {
    assert.equal(
      computeStepScroll({
        focusLine: null,
        highlight: null,
        totalLines: 40,
        prevScroll: 180,
      }),
      180,
    );
  });

  it("keeps highlight-based scrolling monotonic", () => {
    assert.equal(
      computeStepScroll({
        focusLine: null,
        highlight: {
          startLine: 2,
          endLine: 4,
          bgColor: "rgba(88,166,255,0.18)",
          borderColor: "#58a6ff",
        },
        totalLines: 80,
        prevScroll: 220,
      }),
      220,
    );
  });

  it("lets focusLine override monotonic scrolling", () => {
    assert.equal(
      computeStepScroll({
        focusLine: 3,
        highlight: {
          startLine: 40,
          endLine: 44,
          bgColor: "rgba(88,166,255,0.18)",
          borderColor: "#58a6ff",
        },
        totalLines: 80,
        prevScroll: 260,
      }),
      132,
    );
  });
});

describe("getLineNumberAppearance", () => {
  it("renders dimmed line numbers uniformly when highlight is absent", () => {
    assert.deepEqual(getLineNumberAppearance(6, undefined, 0.75), {
      color: "#4a5568",
      fontWeight: "400",
      opacity: 0.5,
    });
  });

  it("highlights line numbers inside the highlight range", () => {
    assert.deepEqual(
      getLineNumberAppearance(
        8,
        {
          startLine: 6,
          endLine: 9,
          bgColor: "rgba(88,166,255,0.18)",
          borderColor: "#58a6ff",
        },
        0.5,
      ),
      {
        color: "#58a6ff",
        fontWeight: "700",
        opacity: 0.7,
      },
    );
  });
});
