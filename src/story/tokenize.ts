export type Tok = { t: string; c: string };

const C = {
  def: "#e6edf3",
  kw: "#ff7b72",
  str: "#a5d6ff",
  num: "#79c0ff",
  fn: "#d2a8ff",
  com: "#8b949e",
};
const KW =
  /^(int|char|void|for|while|if|else|return|using|namespace|vector|bool|const|auto|long|double|struct)$/;

export const tokenizeLine = (line: string): Tok[] => {
  const re =
    /(\/\/.*$)|(#include.*$)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\b\d+\b)|([A-Za-z_]\w*)(?=\()|([A-Za-z_]\w*)/g;
  const out: Tok[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line))) {
    if (m.index > last) out.push({ t: line.slice(last, m.index), c: C.def });
    if (m[1]) out.push({ t: m[0], c: C.com });
    else if (m[2]) out.push({ t: m[0], c: C.kw });
    else if (m[3]) out.push({ t: m[0], c: C.str });
    else if (m[4]) out.push({ t: m[0], c: C.num });
    else if (m[5]) out.push({ t: m[0], c: KW.test(m[0]) ? C.kw : C.fn });
    else out.push({ t: m[0], c: KW.test(m[0]) ? C.kw : C.def });
    last = m.index + m[0].length;
  }
  if (last < line.length) out.push({ t: line.slice(last), c: C.def });
  return out;
};
