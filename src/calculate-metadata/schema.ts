import { getStaticFiles } from "remotion";
import { z } from "zod";
import { themeSchema } from "./theme";

// 動態讀取 public/ 底下有哪些子資料夾
const folders = [
  ...new Set(
    getStaticFiles()
      .map((f) => f.name.split("/")[0])
      .filter((name) => !!name && !name.includes(".")),
  ),
] as [string, ...string[]];

export const width = z.discriminatedUnion("type", [
  z.object({
    type: z.literal("auto"),
  }),
  z.object({
    type: z.literal("fixed"),
    value: z.number().multipleOf(1),
  }),
]);

export const schema = z.object({
  theme: themeSchema,
  width,
  /** public/ 底下的資料夾名稱，自動偵測 */
  folder: z.enum(folders),
});
