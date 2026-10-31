"""Compare the plain matcher with matcher + trained tagger on a HUMAN-LABELLED file.
Usage: python evaluate.py gold.jsonl     (lines: {"text": "...", "skills": [...]})
Only trust a model that beats the matcher here, on data it never saw."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.taxonomy import find_skills
from backend import tagger

def prf(pairs):
    tp = sum(len(set(p) & set(g)) for p, g in pairs); fp = sum(len(set(p) - set(g)) for p, g in pairs); fn = sum(len(set(g) - set(p)) for p, g in pairs)
    P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
    return P, R, (2 * P * R / (P + R) if P + R else 0)

gold = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
base = [(find_skills(g["text"]), g["skills"]) for g in gold]
comb = [(sorted(set(find_skills(g["text"])) | set(tagger.predict(g["text"]))), g["skills"]) for g in gold]
for name, pairs in [("matcher only", base), ("matcher + tagger", comb)]:
    P, R, F = prf(pairs)
    print(f"{name:18s} precision={P:.3f} recall={R:.3f} f1={F:.3f}")
