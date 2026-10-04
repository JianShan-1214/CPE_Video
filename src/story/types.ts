export type ColorName = "neutral" | "yellow" | "green" | "gray" | "red";

/** 舞台上一個元素（卡片、信箱、備忘數字…）的外觀；座標在 1200×460 的虛擬舞台內 */
export type ElProps = {
  x: number;
  y: number;
  w: number;
  h: number;
  text: string;
  sub: string;
  color: ColorName;
  dashed: boolean;
  opacity: number;
  scale: number;
  fs: number;
  sfs: number;
  plain: boolean;
  /** rect＝圓角方塊（預設）、circle＝圓（圖節點）、line＝線段（x,y 為起點，w,h 為 dx,dy，可為負） */
  shape: "rect" | "circle" | "line";
  /** shape=line 時：終點畫箭頭（有向邊） */
  arrow: boolean;
};

export type Op = {
  /** 綁旁白：0~1 為這句旁白念到的位置比例（依實際語音長度換算）。有 at 時 dt 是再加減的偏移秒數 */
  at?: number;
  /** 相對 cue 起點的秒數（沒有 at 時使用） */
  dt?: number;
  /** 這次變化的轉場秒數，預設 0.5 */
  dur?: number;
  set: Record<string, Partial<ElProps>>;
};

/** fullcode（D-020 E1）：整份程式雙欄一次秀出（不捲動、不截斷、不顯示動畫舞台與 cap）；給片尾「完整程式碼」用 */
export type LayoutName = "concept" | "code" | "split" | "wide" | "fullcode";
export type FocusName = "anim" | "code" | "both";

export type Cue = {
  id: string;
  /** 旁白（也是逐句字幕的來源） */
  text: string;
  /** TTS 專用讀法（例如把符號寫成中文）；沒寫就念 text */
  say?: string;
  /** 動畫上方的極短重點，≤14 字；沒寫就沿用前一句 */
  cap?: string;
  /** 這句開始時高亮的程式行（1-based）；[] 表示不高亮；沒寫沿用前一句 */
  lines?: number[];
  layout?: LayoutName;
  focus?: FocusName;
  ops?: Op[];
  /** 這句念完後額外停頓秒數 */
  pauseAfter?: number;
};

export type Scene = {
  id: string;
  label: string;
  layout: LayoutName;
  focus: FocusName;
  cues: Cue[];
};

export type Story = {
  title: string;
  /** true＝程式一開始就整份顯示（自動基礎版用） */
  revealAll?: boolean;
  /** "auto"＝舞台依內容自適應（CPE-003）：依各版面內實際出現過的元素外框決定 stageScale 與位置，輸出列依文字寬度收縮。省略＝沿用固定 RECTS（舊行為） */
  stageFit?: "auto";
  /** 版面修訂（D-020 E4）：≥2 時字幕下移到 top=1003，與 wide 程式列（底 y=998）0px 重疊；省略（舊 story）＝字幕 top=985，與以前逐值相同 */
  layoutRev?: number;
  code: string;
  scenes: Scene[];
};

export type TimelineCue = {
  id: string;
  start: number;
  dur: number;
  lead: number;
  audioDur: number;
  audio: string | null;
};

export type Timeline = {
  fps: number;
  total: number;
  mode: "audio" | "estimate";
  cues: TimelineCue[];
};

export type StoryProps = {
  folder: string;
  story: Story | null;
  timeline: Timeline | null;
  code: string;
};
