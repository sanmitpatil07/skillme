"""Grow backend/data/skills.json from the free ESCO skills CSV (https://esco.ec.europa.eu/en/use-esco/download).
Usage: python build_taxonomy_from_esco.py skills_en.csv wanted_labels.txt
wanted_labels.txt = one ESCO preferredLabel per line that you want to add (you choose; ESCO has ~13,000).
Adds each as a new skill with its altLabels as aliases. Review the result by hand before using it."""
import csv, json, sys
from pathlib import Path
p = Path(__file__).resolve().parent.parent / "backend" / "data" / "skills.json"
skills = json.loads(p.read_text(encoding="utf-8"))
want = {l.strip().lower() for l in open(sys.argv[2], encoding="utf-8") if l.strip()}
added = 0
for r in csv.DictReader(open(sys.argv[1], encoding="utf-8")):
    lab = r["preferredLabel"].strip()
    if lab.lower() in want and lab not in skills:
        alts = [a.strip() for a in r.get("altLabels", "").split("\n") if a.strip()]
        skills[lab] = {"cat": "esco", "aliases": alts}
        added += 1
p.write_text(json.dumps(skills, indent=1, ensure_ascii=False), encoding="utf-8")
print("added", added, "skills")
