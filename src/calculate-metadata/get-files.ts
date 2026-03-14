import { getStaticFiles } from "@remotion/studio";
import { VideoConfigJSON } from "../config-types";

export type PublicFolderFile = {
  filename: string;
  value: string;
};

/** 讀取 public/config.json */
export const getVideoConfig = async (): Promise<VideoConfigJSON> => {
  const files = getStaticFiles();
  const configFile = files.find((f) => f.name === "config.json");
  if (!configFile) throw new Error("找不到 public/config.json");
  const res = await fetch(configFile.src);
  return res.json() as Promise<VideoConfigJSON>;
};

/** 讀取 public/ 內指定的單一檔案 */
export const getFileByName = async (filename: string): Promise<string> => {
  const files = getStaticFiles();
  const file = files.find((f) => f.name === filename);
  if (!file) throw new Error(`找不到 public/${filename}`);
  const res = await fetch(file.src);
  return res.text();
};
