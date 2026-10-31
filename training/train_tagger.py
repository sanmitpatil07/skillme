"""Train the multi-label skill tagger (TF-IDF + logistic regression, one classifier per skill).

Data (pick one):
  --data labelled.jsonl   lines like {"text": "...", "skills": ["Python", "SQL"]}   <- best: human-labelled
  --weak folder/          a folder of .txt job descriptions or resumes. Labels come from the
                          taxonomy matcher (weak supervision). This teaches the model the taxonomy
                          and its context, but it cannot beat the labels it learns from. Hand-check a sample.
Always evaluate on a separate, human-labelled file with evaluate.py before trusting the model."""
import argparse, json, random, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import MultiLabelBinarizer
from backend.taxonomy import find_skills

def load(a):
    rows = []
    if a.data:
        rows = [json.loads(l) for l in open(a.data, encoding="utf-8") if l.strip()]
    if a.weak:
        for p in Path(a.weak).rglob("*.txt"):
            for l in re.split(r"\n|(?<=[.!?])\s+", p.read_text(encoding="utf-8", errors="ignore")):
                l = l.strip()
                if 15 < len(l) < 400:
                    rows.append({"text": l, "skills": find_skills(l)})
    if not rows:
        sys.exit("No training data. Use --data or --weak.")
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--weak"); ap.add_argument("--out", default="../models/tagger.joblib")
    a = ap.parse_args()
    rows = load(a)
    random.seed(7); random.shuffle(rows)
    cut = int(len(rows) * 0.8)
    tr, te = rows[:cut], rows[cut:]
    mlb = MultiLabelBinarizer()
    Y = mlb.fit_transform([r["skills"] for r in tr])
    keep = [i for i in range(Y.shape[1]) if Y[:, i].sum() >= 3]          # need a few positives per skill
    classes = [mlb.classes_[i] for i in keep]
    Ytr = Y[:, keep]
    pipe = Pipeline([
        ("tf", FeatureUnion([("w", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)),
                             ("c", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=2))])),
        ("clf", OneVsRestClassifier(LogisticRegression(C=4, max_iter=2000, class_weight="balanced"))),
    ])
    pipe.fit([r["text"] for r in tr], Ytr)
    P = pipe.predict_proba([r["text"] for r in te])
    pred = (P >= 0.7).astype(int)
    gold = mlb.transform([[s for s in r["skills"] if s in classes] for r in te])[:, [list(mlb.classes_).index(c) for c in classes]]
    p, r_, f, _ = precision_recall_fscore_support(gold, pred, average="micro", zero_division=0)
    print(f"held-out (same distribution as training) micro precision={p:.3f} recall={r_:.3f} f1={f:.3f}  skills={len(classes)} train={len(tr)} test={len(te)}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipe": pipe, "classes": classes}, a.out)
    print("saved", a.out)

if __name__ == "__main__":
    main()
