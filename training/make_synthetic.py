"""Makes a SMALL synthetic dataset so you can check the training pipeline runs.
It is NOT real data. Never quote its scores as real accuracy."""
import json, random, sys
sys.path.insert(0, "..")
from backend.taxonomy import SKILLS
T = ["Built a project using {a} and {b}.", "Experience with {a}, {b} in a team setting.", "Responsible for {a} work and some {b}.",
     "Strong knowledge of {a} is required.", "Familiar with {a}; {b} is a plus.", "Used {a} to deliver a working feature.", "Led a team meeting about quarterly planning.",
     "Wrote documentation and attended daily stand-ups."]
random.seed(1)
names = list(SKILLS)
rows = []
for _ in range(1500):
    a, b = random.sample(names, 2)
    sa = random.choice([a] + SKILLS[a]["aliases"])
    sb = random.choice([b] + SKILLS[b]["aliases"])
    t = random.choice(T)
    labels = [a] * ("{a}" in t) + [b] * ("{b}" in t)
    rows.append({"text": t.format(a=sa, b=sb), "skills": labels})
with open("synthetic.jsonl", "w", encoding="utf-8") as f:
    f.write("\n".join(json.dumps(r) for r in rows))
print("wrote synthetic.jsonl", len(rows))
