import { getAudioDurationInSeconds } from "@remotion/media-utils";
import { CalculateMetadataFunction, staticFile } from "remotion";
import { z } from "zod";
import { Props } from "../Main";
import { expandProps, RawStepInput } from "./expand-props";
import { getFileByName, getVideoConfig } from "./get-files";
import { schema } from "./schema";

export const calculateMetadata: CalculateMetadataFunction<
  Props & z.infer<typeof schema>
> = async ({ props }) => {
  const folder = props.folder;

  // 讀取 public/<folder>/config.json
  const config = await getVideoConfig(folder);
  const { steps: stepConfigs } = config;

  // 讀取各步驟的 cpp 內容與音訊長度（IO 層職責）
  const rawSteps: RawStepInput[] = await Promise.all(
    stepConfigs.map(async (stepConfig, i) => {
      const fileContent = await getFileByName(folder, stepConfig.file);

      const paddedIndex = String(i + 1).padStart(2, "0");
      const audioSrcUrl = staticFile(
        `${folder}/audio/step_${paddedIndex}.mp3`,
      );

      let audioDurationSeconds: number | undefined;
      let audioSrc: string | undefined;
      try {
        audioDurationSeconds = await getAudioDurationInSeconds(audioSrcUrl);
        audioSrc = audioSrcUrl;
      } catch {
        // 音訊檔不存在 — 使用 config 時長
      }

      return {
        ...stepConfig,
        fileContent,
        audioDurationSeconds,
        audioSrc,
      };
    }),
  );

  // 純運算層
  return expandProps({
    steps: rawSteps,
    theme: props.theme,
    width: props.width,
    folder,
  });
};
