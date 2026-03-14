import { AnnotationHandler, HighlightedCode, Pre } from "codehike/code";
import React, { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Easing, interpolate, useCurrentFrame, useDelayRender } from "remotion";

import {
  calculateTransitions,
  getStartingSnapshot,
  TokenTransitionsSnapshot,
} from "codehike/utils/token-transitions";
import { callout } from "./annotations/Callout";
import { applyStyle } from "./utils";

import { errorInline, errorMessage } from "./annotations/Error";
import { tokenTransitions } from "./annotations/InlineToken";
import { fontFamily, fontSize, tabSize } from "./font";

export function CodeTransition({
  oldCode,
  newCode,
  durationInFrames = 30,
}: {
  readonly oldCode: HighlightedCode | null;
  readonly newCode: HighlightedCode;
  readonly durationInFrames?: number;
}) {
  const frame = useCurrentFrame();

  const ref = React.useRef<HTMLPreElement>(null);
  const [oldSnapshot, setOldSnapshot] =
    useState<TokenTransitionsSnapshot | null>(null);
  const { delayRender, continueRender } = useDelayRender();
  const [handle] = React.useState(() => delayRender());

  const prevCode: HighlightedCode = useMemo(() => {
    return oldCode || { ...newCode, tokens: [], annotations: [] };
  }, [newCode, oldCode]);

  const code = useMemo(() => {
    return oldSnapshot ? newCode : prevCode;
  }, [newCode, prevCode, oldSnapshot]);

  useEffect(() => {
    if (!oldSnapshot) {
      setOldSnapshot(getStartingSnapshot(ref.current!));
    }
  }, [oldSnapshot]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    if (!oldSnapshot) {
      setOldSnapshot(getStartingSnapshot(ref.current!));
      return;
    }
    const allTransitions = calculateTransitions(ref.current!, oldSnapshot);

    // Separate entering tokens (new characters) for typewriter effect
    const entering = allTransitions.filter(
      (t) => t.keyframes.opacity?.[0] === 0,
    );
    const others = allTransitions.filter((t) => !(t.keyframes.opacity?.[0] === 0));

    // Sort entering tokens by DOM document order (top-to-bottom, left-to-right)
    entering.sort((a, b) => {
      const pos = a.element.compareDocumentPosition(b.element);
      if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
      if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
      return 0;
    });

    // Map each entering token to a sequential typewriter delay
    const typewriterMap = new Map<HTMLElement, { delay: number; duration: number }>();
    entering.forEach((t, i) => {
      const frac = entering.length > 1 ? i / (entering.length - 1) : 0;
      typewriterMap.set(t.element, {
        delay: frac * 0.82,   // spread typing over 82% of the transition window
        duration: 0.08,       // each token snaps in quickly
      });
    });

    // Apply transitions: typewriter ordering for entering, normal easing for others
    [...others, ...entering].forEach(({ element, keyframes, options }) => {
      const tw = typewriterMap.get(element);
      const effectiveDelay = tw ? tw.delay : options.delay;
      const effectiveDuration = tw ? tw.duration : options.duration;

      const delay = durationInFrames * effectiveDelay;
      const duration = durationInFrames * effectiveDuration;
      const linearProgress = interpolate(
        frame,
        [delay, delay + duration],
        [0, 1],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
      );
      const progress = tw
        ? linearProgress
        : interpolate(linearProgress, [0, 1], [0, 1], {
            easing: Easing.bezier(0.17, 0.67, 0.76, 0.91),
          });

      applyStyle({ element, keyframes, progress, linearProgress });
    });
    continueRender(handle);
  });

  const handlers: AnnotationHandler[] = useMemo(() => {
    return [tokenTransitions, callout, errorInline, errorMessage];
  }, []);

  const style: React.CSSProperties = useMemo(() => {
    return {
      position: "relative",
      fontSize,
      lineHeight: 1.5,
      fontFamily,
      tabSize,
      margin: 0,
    };
  }, []);

  return <Pre ref={ref} code={code} handlers={handlers} style={style} />;
}
