import { Composition } from "remotion";
import { Main } from "./Main";
import { Story } from "./story/Story";
import { StoryProps } from "./story/types";

import { calculateMetadata } from "./calculate-metadata/calculate-metadata";
import { schema } from "./calculate-metadata/schema";

export const RemotionRoot = () => {
  return (
    <>
    <Composition
      id="Story"
      component={Story}
      defaultProps={{ folder: "", story: null, timeline: null, code: "" } as StoryProps}
      fps={30}
      width={1920}
      height={1080}
      durationInFrames={30}
      calculateMetadata={async ({ props }) => ({
        durationInFrames: Math.max(30, Math.ceil(((props as StoryProps).timeline?.total ?? 1) * 30)),
      })}
    />
    <Composition
      id="Main"
      component={Main}
      defaultProps={{
        steps: null,
        themeColors: null,
        theme: "github-dark" as const,
        codeWidth: null,
        charWidth: null,
        folder: "example-bubble_sort" as const,
        width: {
          type: "fixed",
          value: 1920,
        },
      }}
      fps={30}
      height={1080}
      calculateMetadata={calculateMetadata}
      schema={schema}
    />
    </>
  );
};
