import json, re
from pathlib import Path
D = Path(__file__).parent / "data"
SKILLS = json.loads((D / "skills.json").read_text(encoding="utf-8"))
ROLES = json.loads((D / "roles.json").read_text(encoding="utf-8"))

def _pat(a):
    return re.compile(r"(?<![A-Za-z0-9+#])" + re.escape(a.lower()) + r"(?![A-Za-z0-9+#])")

PATS = {n: [_pat(a) for a in [n] + v["aliases"]] for n, v in SKILLS.items()}

def find_skills(text):
    t = text.lower()
    return [n for n, ps in PATS.items() if any(p.search(t) for p in ps)]
