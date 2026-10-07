#!/usr/bin/env python3
"""把 coverage.py 的覆蓋表貼進 repo 內的 skill.md（<!--COVERAGE-->…<!--/COVERAGE--> 之間），保證文件＝程式偵測。
目標路徑以 repo 根目錄為基準（repo-relative），不依賴任何機器上的絕對路徑。"""
import subprocess, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SKILL_REL = "skill.md"           # repo 內唯一的 cpe-video skill
P = REPO / SKILL_REL
tbl = subprocess.run([sys.executable, str(HERE / "coverage.py"), "--md"], capture_output=True, text=True, check=True).stdout.strip()
s = P.read_text(encoding="utf-8")
new = f"<!--COVERAGE-->\n{tbl}\n<!--/COVERAGE-->"
pat = re.compile(r"^<!--COVERAGE-->$.*?^<!--/COVERAGE-->$", re.S | re.M)   # 只認行首獨立標記，避免內文提到標記時誤配
if pat.search(s):
    s = pat.sub(lambda m: new, s, count=1)
    P.write_text(s, encoding="utf-8"); print(f"updated {SKILL_REL}")
else:
    print(f"no marker in {SKILL_REL}"); sys.exit(1)
