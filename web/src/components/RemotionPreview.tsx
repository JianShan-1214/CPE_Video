import { Player } from "@remotion/player";
import { AlertTriangle, Clapperboard, Loader2 } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { Main } from "@remotion-src/Main";
import {
  expandProps,
  type ExpandPropsOutput,
} from "@remotion-src/calculate-metadata/expand-props";
import type { Job } from "@/lib/draft-types";

type State =
  | { kind: "empty" }
  | { kind: "loading" }
  | { kind: "ready"; result: ExpandPropsOutput }
  | { kind: "error"; message: string };

export function RemotionPreview({ job }: { job: Job }) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    if (job.steps.length === 0) {
      setState({ kind: "empty" });
      return;
    }

    let cancelled = false;
    setState({ kind: "loading" });

    expandProps({
      steps: job.steps.map((s) => ({
        label: s.label,
        from: s.from,
        to: s.to,
        file: s.fileLabel,
        fileContent: s.fileContent,
        subtitle: s.subtitle,
        focusLine: s.focusLine,
        highlight: s.highlight,
        annotations: s.annotations,
      })),
      theme: job.theme,
      width: job.width,
      folder: job.id,
    })
      .then((result) => {
        if (!cancelled) setState({ kind: "ready", result });
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          const message = e instanceof Error ? e.message : String(e);
          setState({ kind: "error", message });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [job]);

  if (state.kind === "empty") {
    return (
      <PreviewFrame>
        <div className="aspect-video flex flex-col items-center justify-center gap-4 text-center px-6">
          <Clapperboard className="text-faint" size={36} strokeWidth={1.4} />
          <p className="text-mist text-sm">新增第一個步驟即可預覽</p>
        </div>
      </PreviewFrame>
    );
  }
  if (state.kind === "loading") {
    return (
      <PreviewFrame>
        <div className="aspect-video flex flex-col items-center justify-center gap-4 text-center px-6">
          <Loader2 className="text-accent animate-spin" size={32} strokeWidth={1.6} />
          <p className="meta-mono text-xs uppercase tracking-[0.24em]">Rendering</p>
        </div>
      </PreviewFrame>
    );
  }
  if (state.kind === "error") {
    return (
      <PreviewFrame>
        <div className="aspect-video flex flex-col items-center justify-center gap-3 text-center px-6 py-4">
          <AlertTriangle className="text-danger" size={32} strokeWidth={1.6} />
          <p className="text-danger text-sm max-w-md break-words">
            預覽錯誤：{state.message}
          </p>
        </div>
      </PreviewFrame>
    );
  }

  const { result } = state;
  return (
    <PreviewFrame>
      <div className="overflow-hidden rounded-[0.625rem] bg-ink-950">
        <Player
          component={Main}
          inputProps={result.props}
          durationInFrames={Math.max(1, result.durationInFrames)}
          compositionWidth={result.width}
          compositionHeight={1080}
          fps={30}
          controls
          style={{ width: "100%", aspectRatio: `${result.width} / 1080` }}
        />
      </div>
    </PreviewFrame>
  );
}

function PreviewFrame({ children }: { children: ReactNode }) {
  return (
    <div className="panel p-3">
      <div className="flex items-center gap-2 px-1 pb-3">
        <span className="size-1.5 rounded-full bg-accent shadow-[0_0_8px_var(--color-accent)]" />
        <span className="eyebrow">Preview</span>
      </div>
      {children}
    </div>
  );
}
