import { Player } from "@remotion/player";
import { useEffect, useState } from "react";
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
      <div className="aspect-video bg-neutral-900 rounded flex items-center justify-center text-neutral-500">
        新增第一個步驟即可預覽
      </div>
    );
  }
  if (state.kind === "loading") {
    return (
      <div className="aspect-video bg-neutral-900 rounded flex items-center justify-center text-neutral-500">
        處理中…
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div className="aspect-video bg-neutral-900 rounded flex items-center justify-center text-red-400 p-4 text-center">
        預覽錯誤：{state.message}
      </div>
    );
  }

  const { result } = state;
  return (
    <div className="bg-black rounded overflow-hidden">
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
  );
}
