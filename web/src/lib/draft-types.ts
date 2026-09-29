import type {
  AnnotationJSON,
  HighlightConfigJSON,
  StepAnimation,
} from "@remotion-src/config-types";
import type { Theme } from "@remotion-src/calculate-metadata/theme";

export type WidthConfig =
  | { type: "fixed"; value: number }
  | { type: "auto" };

export type DraftStep = {
  label: string;
  from: number;
  to: number;
  fileLabel: string;
  fileContent: string;
  subtitle: string;
  focusLine?: number;
  highlight?: HighlightConfigJSON;
  annotations?: AnnotationJSON[];
  animation?: StepAnimation;
  /** 追蹤計畫：後端實際執行程式，依此產生 animation（見 backend StepTrace） */
  trace?: StepTrace | null;
};

export type StepTrace = {
  line: number;
  /** 快照在第 line 行執行前或執行後（省略 = before） */
  when?: "before" | "after";
  show: {
    as: "array" | "grid" | "stacks" | "queue" | "vars";
    expr?: string | null;
    length?: string | null;
  };
  pointers: string[];
  vars: string[];
  maxFrames: number;
  caption?: string | null;
};

export type Job = {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  theme: Theme;
  width: WidthConfig;
  steps: DraftStep[];
  sampleInput?: string;
  sampleOutput?: string;
};
