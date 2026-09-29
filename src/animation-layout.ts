// 演算法動畫的純運算層：frame → 每個元素的位置／透明度。無 React、無 remotion 依賴，可直接測試。
import type {
  AnimationVars,
  ArrayAnimation,
  GridAnimation,
  StacksAnimation,
  StepAnimation,
  VarValue,
} from "./config-types";

export const ANIMATION_TRANSITION_FRAMES = 12;

type Value = number | string;

/** 面板放得下的上限；超過就整段不畫（寧可沒動畫也不要擠爆） */
export const MAX_ARRAY_VALUES = 16;
export const MAX_STACKS = 8;
export const MAX_STACK_HEIGHT = 12;

const isNum = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);

const isValue = (v: unknown): v is Value => isNum(v) || typeof v === "string";

// null 視同未填（Python json.dumps / LLM 輸出常見）
const isIndexList = (v: unknown) =>
  v == null || (Array.isArray(v) && v.every(isNum));

const isCaption = (v: unknown) => v == null || typeof v === "string";

const hasDuplicates = (vs: Value[]) =>
  new Set(vs.map(String)).size !== vs.length;

export const MAX_GRID = 12;
export const MAX_VARS = 8;

const isScalar = (v: unknown): v is VarValue =>
  v === null || typeof v === "boolean" || isValue(v);

const isVars = (v: unknown) =>
  v == null ||
  (typeof v === "object" &&
    !Array.isArray(v) &&
    Object.keys(v).length <= MAX_VARS &&
    Object.values(v).every(isScalar));

const isCellList = (v: unknown) =>
  v == null ||
  (Array.isArray(v) &&
    v.every((m) => Array.isArray(m) && m.length === 2 && m.every(isNum)));

/** grid 格子與變數值的顯示文字；null 畫成空白 */
export const formatScalar = (v: VarValue | undefined) =>
  v == null ? "" : String(v);

/** 輕量驗證：不合法就回 false，呼叫方改成不畫動畫，絕不讓 render 崩潰 */
export const isValidAnimation = (a: unknown): a is StepAnimation => {
  if (typeof a !== "object" || a === null) return false;
  const { type, frames } = a as { type?: unknown; frames?: unknown };
  if (!Array.isArray(frames) || frames.length === 0) return false;
  const okFrame = (
    f: unknown,
    check: (f: Record<string, unknown>) => boolean,
  ) =>
    typeof f === "object" &&
    f !== null &&
    isCaption((f as { caption?: unknown }).caption) &&
    isVars((f as { vars?: unknown }).vars) &&
    check(f as Record<string, unknown>);
  if (type === "array") {
    return frames.every((f) =>
      okFrame(
        f,
        ({ values, pointers, mark }) =>
          Array.isArray(values) &&
          values.length <= MAX_ARRAY_VALUES &&
          values.every(isValue) &&
          isIndexList(mark) &&
          (pointers == null ||
            (typeof pointers === "object" &&
              Object.values(pointers).every(isNum))),
      ),
    );
  }
  if (type === "stacks") {
    const { labels } = a as { labels?: unknown };
    if (
      labels != null &&
      !(
        Array.isArray(labels) &&
        labels.length <= MAX_STACKS &&
        labels.every((l) => typeof l === "string")
      )
    )
      return false;
    return frames.every((f) =>
      okFrame(
        f,
        ({ stacks }) =>
          Array.isArray(stacks) &&
          stacks.length <= MAX_STACKS &&
          stacks.every(
            (s) =>
              Array.isArray(s) &&
              s.length <= MAX_STACK_HEIGHT &&
              s.every(isValue),
          ) &&
          // block id 在同一格內必須唯一，否則移動時無法判斷是哪一塊
          !hasDuplicates((stacks as Value[][]).flat()),
      ),
    );
  }
  if (type === "grid") {
    return frames.every((f) =>
      okFrame(
        f,
        ({ cells, mark }) =>
          Array.isArray(cells) &&
          cells.length >= 1 &&
          cells.length <= MAX_GRID &&
          cells.every(
            (row) =>
              Array.isArray(row) &&
              row.length <= MAX_GRID &&
              row.every(isScalar),
          ) &&
          isCellList(mark),
      ),
    );
  }
  if (type === "vars") {
    return frames.every((f) => okFrame(f, ({ vars }) => vars != null));
  }
  return false;
};

const easeInOut = (t: number) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/**
 * keyframes 平均分配在 duration 內；每段開頭用 ANIMATION_TRANSITION_FRAMES 從上一格過渡。
 * 第 0 段沒有上一格，progress 固定為 1（面板本身的淡入負責進場）。
 */
export const getSegment = (
  frame: number,
  duration: number,
  frameCount: number,
) => {
  const segLen = duration / frameCount;
  const index = Math.min(
    frameCount - 1,
    Math.max(0, Math.floor(frame / segLen)),
  );
  if (index === 0) return { index, progress: 1 };
  const t = Math.min(
    1,
    Math.max(0, (frame - index * segLen) / ANIMATION_TRANSITION_FRAMES),
  );
  return { index, progress: easeInOut(t) };
};

/** 以 `${value}#${第幾次出現}` 當 identity，重複值也能正確配對（swap 時兩格交錯移動）*/
export const identityKeys = (values: Value[]) => {
  const seen = new Map<string, number>();
  return values.map((v) => {
    const k = String(v);
    const n = seen.get(k) ?? 0;
    seen.set(k, n + 1);
    return `${k}#${n}`;
  });
};

type Tweened = { key: string; value: Value; opacity: number };

/** 元素依 key 從舊位置補間到新位置；新增的淡入、消失的淡出 */
const tweenByKey = <P extends Record<string, number>>(
  prev: Map<string, { value: Value; pos: P }>,
  cur: Map<string, { value: Value; pos: P }>,
  p: number,
): (Tweened & { from: P; to: P; pos: P })[] => {
  const out: (Tweened & { from: P; to: P; pos: P })[] = [];
  for (const [key, c] of cur) {
    const from = prev.get(key)?.pos ?? c.pos;
    const pos = Object.fromEntries(
      Object.keys(c.pos).map((k) => [k, lerp(from[k], c.pos[k], p)]),
    ) as P;
    out.push({
      key,
      value: c.value,
      opacity: prev.has(key) ? 1 : p,
      from,
      to: c.pos,
      pos,
    });
  }
  for (const [key, o] of prev) {
    if (!cur.has(key))
      out.push({
        key,
        value: o.value,
        opacity: 1 - p,
        from: o.pos,
        to: o.pos,
        pos: o.pos,
      });
  }
  return out;
};

/** 先淡出舊文字再淡入新文字，避免兩段文字疊在一起（字幕、grid 格子、變數值共用）*/
export const crossfade = (prev: string, cur: string, p: number) =>
  prev === cur
    ? { text: cur, textOpacity: 1, prevText: "", prevTextOpacity: 0 }
    : {
        text: cur,
        textOpacity: Math.max(0, 2 * p - 1),
        prevText: prev,
        prevTextOpacity: Math.max(0, 1 - 2 * p),
      };

export const captionState = (
  prev: string | null | undefined,
  cur: string | null | undefined,
  p: number,
) => {
  const c = crossfade(prev ?? "", cur ?? "", p);
  return {
    caption: c.text,
    captionOpacity: c.textOpacity,
    prevCaption: c.prevText,
    prevCaptionOpacity: c.prevTextOpacity,
  };
};

/** cur 相對 prev 新出現或值不同的變數名；沒有上一格（step 第一格）視為都沒變 */
export const changedVars = (
  prev: AnimationVars | null | undefined,
  cur: AnimationVars | null | undefined,
  hasPrev: boolean,
) =>
  new Set(
    hasPrev
      ? Object.keys(cur ?? {}).filter(
          (k) => !prev || !(k in prev) || prev[k] !== cur![k],
        )
      : [],
  );

/**
 * 變數表的格局。附在主圖下方時 > 4 項改成兩欄以省高度；standalone（vars 型別）單欄大字。
 * 高度取整段動畫的最多項數，換格時主圖不會跳動。
 */
export const varsTableLayout = (count: number, standalone: boolean) => {
  const columns = !standalone && count > 4 ? 2 : 1;
  const rowH = standalone ? 64 : 40;
  const rows = Math.ceil(count / columns);
  return {
    columns,
    rows,
    rowH,
    fontSize: standalone ? 30 : 22,
    height: rows * rowH,
  };
};

export const layoutVars = (
  frames: { vars?: AnimationVars | null }[],
  index: number,
  p: number,
  standalone: boolean,
) => {
  const table = varsTableLayout(
    Math.max(0, ...frames.map((f) => Object.keys(f.vars ?? {}).length)),
    standalone,
  );
  const rowMap = (i: number) => {
    const vars = frames[i].vars ?? {};
    const changed = changedVars(frames[i - 1]?.vars, vars, i > 0);
    return new Map(
      Object.keys(vars).map((name, k) => [
        name,
        {
          value: formatScalar(vars[name]),
          pos: {
            col: Math.floor(k / table.rows),
            row: k % table.rows,
            mark: changed.has(name) ? 1 : 0,
          },
        },
      ]),
    );
  };
  const prev = rowMap(Math.max(0, index - 1));
  const items = tweenByKey(prev, rowMap(index), p).map(
    ({ key, value, opacity, pos }) => ({
      name: key,
      opacity,
      ...pos,
      ...crossfade(String(prev.get(key)?.value ?? value), String(value), p),
    }),
  );
  return { table, items };
};

/**
 * grid 每格的 slot 與方塊大小：塞進 w×h，方格上限同 array 的 72px。
 * 高度吃緊（列多、下方有變數表）時橫向放寬到 48px，三位數仍放得下。
 */
export const gridCellSize = (
  rows: number,
  cols: number,
  w: number,
  h: number,
) => {
  const slotH = Math.min(80, w / Math.max(1, cols), h / Math.max(1, rows));
  const slotW = Math.min(w / Math.max(1, cols), Math.max(slotH, 48));
  return { slotW, slotH, cellW: slotW * 0.9, cellH: slotH * 0.9 };
};

export const layoutGrid = (
  anim: GridAnimation,
  frame: number,
  duration: number,
) => {
  const { index, progress: p } = getSegment(
    frame,
    duration,
    anim.frames.length,
  );
  const cur = anim.frames[index];
  const prev = anim.frames[Math.max(0, index - 1)];
  const cellMap = (f: GridAnimation["frames"][number]) => {
    const marks = new Set((f.mark ?? []).map(([r, c]) => `${r},${c}`));
    return new Map(
      f.cells.flatMap((row, r) =>
        row.map((v, c) => [
          `${r},${c}`,
          {
            value: formatScalar(v),
            pos: { r, c, mark: marks.has(`${r},${c}`) ? 1 : 0 },
          },
        ]),
      ),
    );
  };
  const prevCells = cellMap(prev);
  // 格子不移動：key 就是座標，只補間 mark、值用 crossfade
  const cells = tweenByKey(prevCells, cellMap(cur), p).map(
    ({ key, value, opacity, pos }) => ({
      key,
      opacity,
      ...pos,
      ...crossfade(String(prevCells.get(key)?.value ?? value), String(value), p),
    }),
  );
  return {
    rows: Math.max(...anim.frames.map((f) => f.cells.length)),
    cols: Math.max(1, ...anim.frames.flatMap((f) => f.cells.map((r) => r.length))),
    cells,
    ...captionState(prev.caption, cur.caption, p),
  };
};

/** 指標只畫在該格範圍內的整數 index；越界（例如 j = -1 的迴圈終止狀態）直接不畫 */
export const isValidIndex = (i: number, length: number) =>
  Number.isInteger(i) && i >= 0 && i < length;

export const layoutArray = (
  anim: ArrayAnimation,
  frame: number,
  duration: number,
) => {
  const { index, progress: p } = getSegment(
    frame,
    duration,
    anim.frames.length,
  );
  const cur = anim.frames[index];
  const prev = anim.frames[Math.max(0, index - 1)];
  const slotMap = (f: ArrayAnimation["frames"][number]) => {
    const marks = new Set(f.mark ?? []);
    return new Map(
      identityKeys(f.values).map((key, i) => [
        key,
        { value: f.values[i], pos: { x: i, mark: marks.has(i) ? 1 : 0 } },
      ]),
    );
  };
  const cells = tweenByKey(slotMap(prev), slotMap(cur), p).map(
    ({ key, value, opacity, from, pos }) => {
      const dx = pos.x - from.x;
      return {
        key,
        value,
        opacity,
        x: pos.x,
        mark: pos.mark,
        // 往右移的往上拱、往左移的往下拱，swap 時兩格不會疊在一起
        lift: dx === 0 ? 0 : -Math.sign(dx) * Math.sin(Math.PI * p),
      };
    },
  );
  const ptrMap = (f: ArrayAnimation["frames"][number]) =>
    new Map(
      Object.entries(f.pointers ?? {})
        .filter(([, i]) => isValidIndex(i, f.values.length))
        .map(([name, i]) => [name, { value: name, pos: { x: i } }]),
    );
  const pointers = tweenByKey(ptrMap(prev), ptrMap(cur), p).map(
    ({ key, opacity, pos }) => ({
      name: key,
      opacity,
      x: pos.x,
    }),
  );
  return {
    slotCount: Math.max(1, ...anim.frames.map((f) => f.values.length)),
    cells,
    pointers,
    ...captionState(prev.caption, cur.caption, p),
  };
};

export const layoutStacks = (
  anim: StacksAnimation,
  frame: number,
  duration: number,
) => {
  const { index, progress: p } = getSegment(
    frame,
    duration,
    anim.frames.length,
  );
  const cur = anim.frames[index];
  const prev = anim.frames[Math.max(0, index - 1)];
  const blockMap = (f: StacksAnimation["frames"][number]) => {
    const all = f.stacks.flat();
    const keys = identityKeys(all);
    const pos: { stack: number; level: number }[] = f.stacks.flatMap(
      (s, stack) => s.map((_, level) => ({ stack, level })),
    );
    return new Map(keys.map((key, i) => [key, { value: all[i], pos: pos[i] }]));
  };
  const maxHeight = Math.max(
    1,
    ...anim.frames.flatMap((f) => f.stacks.map((s) => s.length)),
  );
  const blocks = tweenByKey(blockMap(prev), blockMap(cur), p).map(
    ({ key, value, opacity, from, to }) => ({
      key,
      value,
      opacity,
      ...liftPath(from, to, p, maxHeight),
    }),
  );
  return {
    stackCount: Math.max(
      1,
      anim.labels?.length ?? 0,
      ...anim.frames.map((f) => f.stacks.length),
    ),
    maxHeight,
    blocks,
    ...captionState(prev.caption, cur.caption, p),
  };
};

type StackPos = { stack: number; level: number };

/**
 * 換堆的 block 走「往上 → 橫移 → 往下」，lane 是所有堆之上的空層，不會穿過旁邊的 block。
 * 同一堆內只是上下移動就直線補間。p 依路徑長度等速分配。
 */
export const liftPath = (
  from: StackPos,
  to: StackPos,
  p: number,
  lane: number,
): StackPos => {
  if (from.stack === to.stack)
    return { stack: from.stack, level: lerp(from.level, to.level, p) };
  const up = lane - from.level;
  const across = Math.abs(to.stack - from.stack);
  const down = lane - to.level;
  let d = p * (up + across + down);
  if (d <= up) return { stack: from.stack, level: from.level + d };
  d -= up;
  if (d <= across)
    return {
      stack: from.stack + Math.sign(to.stack - from.stack) * d,
      level: lane,
    };
  return { stack: to.stack, level: lane - (d - across) };
};
