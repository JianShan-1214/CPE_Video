import type { DraftStep, Job } from "./draft-types";

export type GeneratedStep = DraftStep;

export type GeneratedVideoDraft = {
  jobName: string;
  steps: GeneratedStep[];
};

export type GenerateMockVideoDraftInput = {
  name?: string;
  problemStatement: string;
  solutionCode: string;
};

export function generateMockVideoDraft(
  input: GenerateMockVideoDraftInput,
): GeneratedVideoDraft {
  const problemStatement = normalizeText(input.problemStatement);
  const solutionCode = normalizeCode(input.solutionCode);
  const jobName = normalizeJobName(input.name);
  const problemComment = buildProblemComment(problemStatement);
  const codeLines = solutionCode.trimEnd().split("\n");
  const middleCount = Math.min(5, Math.max(3, Math.ceil(codeLines.length / 6)));
  const steps: GeneratedStep[] = [
    {
      label: "題目說明",
      from: 0,
      to: 7,
      fileLabel: "code01.cpp",
      fileContent: problemComment,
      subtitle: `這題的重點是：${shorten(problemStatement, 56)}`,
      highlight: {
        startLine: 1,
        endLine: problemComment.trimEnd().split("\n").length,
        color: "blue",
      },
    },
    {
      label: "解法說明",
      from: 7,
      to: 15,
      fileLabel: "code01.cpp",
      fileContent: problemComment,
      subtitle:
        "解法先假裝由 GPT 分析完成：我們會依照題意拆解輸入、核心處理與輸出，再逐段建立完整 C++ 程式。",
    },
  ];

  for (let i = 1; i <= middleCount; i++) {
    const end = Math.max(1, Math.ceil((codeLines.length * i) / middleCount));
    const fileContent = ensureTrailingNewline(codeLines.slice(0, end).join("\n"));
    const startLine = Math.max(1, Math.ceil((codeLines.length * (i - 1)) / middleCount) + 1);
    const fileLabel = `code${String(i + 1).padStart(2, "0")}.cpp`;

    steps.push({
      label: codeStepLabel(i, middleCount),
      from: steps.at(-1)?.to ?? 15,
      to: (steps.at(-1)?.to ?? 15) + 7,
      fileLabel,
      fileContent,
      subtitle: codeStepSubtitle(i, middleCount),
      highlight: {
        startLine,
        endLine: end,
        color: highlightColorForStep(i, middleCount),
      },
    });
  }

  steps.push({
    label: "結尾",
    from: steps.at(-1)?.to ?? 0,
    to: (steps.at(-1)?.to ?? 0) + 9,
    fileLabel: `code${String(middleCount + 2).padStart(2, "0")}.cpp`,
    fileContent: solutionCode,
    subtitle:
      "總結一下：這份草稿已經把題目、解法思路與完整程式串成影片步驟。接下來可以在編輯器微調字幕、高亮與標注，再匯出成可 render 的檔案。",
    focusLine: 1,
  });

  return { jobName, steps };
}

export function generatedDraftToJob(draft: GeneratedVideoDraft): Job {
  const now = Date.now();
  return {
    id: crypto.randomUUID(),
    name: draft.jobName,
    createdAt: now,
    updatedAt: now,
    theme: "github-dark",
    width: { type: "fixed", value: 1920 },
    steps: draft.steps,
  };
}

function normalizeText(value: string): string {
  const trimmed = value.trim();
  return trimmed || "使用者尚未提供題目內容。";
}

function normalizeCode(value: string): string {
  const trimmed = value.trim();
  return ensureTrailingNewline(trimmed || "// TODO: paste the final C++ answer here");
}

function normalizeJobName(value: string | undefined): string {
  const trimmed = value?.trim();
  return trimmed || "GPT Mock Draft";
}

function buildProblemComment(problemStatement: string): string {
  const lines = problemStatement.split("\n").map((line) => ` * ${line}`);
  return ["/*", ...lines, " */", ""].join("\n");
}

function ensureTrailingNewline(value: string): string {
  return value.endsWith("\n") ? value : `${value}\n`;
}

function shorten(value: string, maxLength: number): string {
  const compact = value.replace(/\s+/g, " ").trim();
  return compact.length <= maxLength
    ? compact
    : `${compact.slice(0, maxLength - 1)}…`;
}

function codeStepLabel(index: number, total: number): string {
  if (index === 1) return "建立程式骨架";
  if (index === total) return "完成完整程式";
  return `程式碼講解 ${index}`;
}

function codeStepSubtitle(index: number, total: number): string {
  if (index === 1) {
    return "接下來先放入程式的前段內容，建立標頭、變數或主要函式骨架，讓後續邏輯有清楚的起點。";
  }
  if (index === total) {
    return "最後補上剩餘程式碼，讓整份 C++ 答案成為可以編譯執行的完整版本。";
  }
  return "這一段延續前面的程式碼，逐步補上核心處理邏輯，讓觀眾能跟著理解每個區塊的用途。";
}

function highlightColorForStep(
  index: number,
  total: number,
): "blue" | "yellow" | "green" | "lightblue" {
  if (index === 1) return "lightblue";
  if (index === total) return "green";
  return index % 2 === 0 ? "yellow" : "blue";
}
