import re
from .taxonomy import ROLES
from . import llm

DIMS = ["Technical correctness", "Problem solving", "Communication", "Depth", "Role alignment"]

def questions(role_idx):
    return [{"id": i, "q": q["q"]} for i, q in enumerate(ROLES[role_idx]["questions"])]

def _band(x):
    return max(1, min(5, round(x)))

def heuristic(q, answer, role_skills):
    words = re.findall(r"[a-z0-9\-/]+", answer.lower())
    sents = [s.strip() for s in re.split(r"[.!?]\s+", answer) if s.strip()]
    hit = [k for k in q["keys"] if k in answer.lower()]
    cover = len(hit) / len(q["keys"])
    ev = next((s for s in sents if any(k in s.lower() for k in hit)), sents[0] if sents else "")
    steps = len(re.findall(r"\b(first|then|next|finally|because|so that|for example|e\.g\.)\b", answer.lower()))
    has_ex = bool(re.search(r"for example|e\.g\.|such as|\d", answer.lower()))
    mentioned = [s for s in role_skills if s.lower() in answer.lower()]
    return {
        "Technical correctness": _band(1 + 4 * cover),
        "Problem solving": _band(1 + steps * 1.2 + cover * 2),
        "Communication": _band(1 + min(len(sents), 5) * 0.6 + (1 if 40 <= len(words) <= 220 else 0)),
        "Depth": _band(1 + min(len(words) / 50, 2) + (1.5 if has_ex else 0) + cover),
        "Role alignment": _band(1 + len(mentioned) * 1.3 + cover * 1.5),
    }, ev[:200], [k for k in q["keys"] if k not in hit]

def evaluate(role_idx, answers):
    role = ROLES[role_idx]
    out = []
    for a in answers:
        q = role["questions"][a["q"]]
        text = a["text"].strip()
        res = llm.complete_json(
            "You are a strict, fair interview evaluator. Score only job-related content. Ignore accent, grammar slips and personal traits.",
            f'Role: {role["n"]}\nQuestion: {q["q"]}\nAnswer: {text}\nReturn {{"scores":{{{", ".join(chr(34)+d+chr(34)+":1-5" for d in DIMS)}}},"evidence":"short quote from the answer","missing":["concepts missing"],"practice":"one practice task"}}')
        if res and "scores" in res:
            out.append({"q": a["q"], "method": "llm", **res})
            continue
        scores, ev, missing = heuristic(q, text, role["s"])
        weakest = min(scores, key=scores.get)
        out.append({"q": a["q"], "method": "heuristic", "scores": scores, "evidence": ev, "missing": missing[:4],
                    "practice": f"Re-answer this question in 4 sentences, adding a concrete example. Focus on: {weakest}."})
    avg = round(sum(sum(o["scores"].values()) / len(o["scores"]) for o in out) / max(len(out), 1), 1)
    return {"overall": avg, "results": out}
