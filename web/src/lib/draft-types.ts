import type {
  AnnotationJSON,
  HighlightConfigJSON,
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
};

export type Job = {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  theme: Theme;
  width: WidthConfig;
  steps: DraftStep[];
};
