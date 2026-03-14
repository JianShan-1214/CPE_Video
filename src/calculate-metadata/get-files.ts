import { getStaticFiles } from "@remotion/studio";
import { VideoConfigJSON } from "../config-types";

export type PublicFolderFile = {
  filename: string;
  value: string;
};

/** 讀取 public/<folder>/config.json */
export const getVideoConfig = async (folder: string): Promise<VideoConfigJSON> => {
  const target = `${folder}/config.json`;
  const files = getStaticFiles();
  const configFile = files.find((f) => f.name === target);
  if (!configFile) throw new Error(`找不到 public/${target}`);
  const res = await fetch(configFile.src);
  return res.json() as Promise<VideoConfigJSON>;
};

/** 讀取 public/<folder>/<filename> */
export const getFileByName = async (folder: string, filename: string): Promise<string> => {
  const target = `${folder}/${filename}`;
  const files = getStaticFiles();
  const file = files.find((f) => f.name === target);
  if (!file) throw new Error(`找不到 public/${target}`);
  const res = await fetch(file.src);
  return res.text();
};
