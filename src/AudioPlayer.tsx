import React from "react";
import { Audio } from "remotion";

/**
 * Thin wrapper around Remotion <Audio />.
 * Must be rendered inside a Series.Sequence — Remotion scopes
 * audio playback to the sequence's time range automatically.
 */
export const AudioPlayer: React.FC<{ src: string }> = ({ src }) => (
  <Audio src={src} startFrom={0} />
);
