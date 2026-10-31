import json, math, re
from .taxonomy import ROLES, find_skills

REQ = re.compile(r"\b(required|requirements?|must|mandatory|minimum|should have|proficien\w+|strong)\b", re.I)
PREF = re.compile(r"\b(preferred|nice to have|good to have|bonus|plus|desirable|an advantage)\b", re.I)

def jd_skills(text):
    """Skill -> importance (3 must-have, 2 normal, 1 preferred), from the wording around it."""
    out, mode = {}, None
    for raw in text.splitlines():
        l = raw.strip()
        if not l:
            continue
        found = find_skills(l)
        if not found and len(l) < 45:
            if PREF.search(l):
                mode = 1
            elif REQ.search(l):
                mode = 3
            elif re.search(r"responsibilit|about|benefit", l, re.I):
                mode = None
            continue
        imp = 1 if PREF.search(l) else 3 if REQ.search(l) else (mode or 2)
        for s in found:
            out[s] = max(out.get(s, 0), imp)
    return out

def roles_with_demand(conn, uid=None):
    """Seed role skill weights, blended with the user's ingested job descriptions (3+ per role)."""
    res = []
    for r in ROLES:
        q, args = "SELECT skills_json FROM jobs WHERE family=?", [r["n"]]
        if uid is not None:
            q += " AND user_id=?"
            args.append(uid)
        rows = conn.execute(q, args).fetchall()
        s = dict(r["s"])
        n = len(rows)
        if n >= 3:
            agg = {}
            for row in rows:
                for k, imp in json.loads(row[0]).items():
                    a = agg.setdefault(k, [0, 0])
                    a[0] += 1
                    a[1] += imp
            for k, (c, tot) in agg.items():
                freq = c / n
                if freq < 0.4 and k not in s:
                    continue
                wjd = (tot / c) * (0.5 + 0.5 * freq)
                s[k] = round(0.5 * s[k] + 0.5 * wjd, 2) if k in s else round(wjd, 2)
        res.append({"n": r["n"], "sal": r["sal"], "up": r["up"], "s": s, "jd_count": n})
    return res

def score(profile, role):
    tot = got = cov = 0
    rows = []
    for k, w in role["s"].items():
        f = profile["sk"].get(k, {}).get("fit", 0)
        tot += w
        got += w * f
        cov += 1 if f else 0
        rows.append({"skill": k, "weight": w, "fit": f})
    rows.sort(key=lambda x: x["weight"] * (1 - x["fit"]), reverse=True)
    n = len(role["s"])
    return {"readiness": round(got / tot * 100), "coverage": round(cov / n * 100), "rows": rows}

def roadmap(profile, role, hours, weeks=4):
    gaps = [r for r in score(profile, role)["rows"] if r["fit"] < 1][:weeks]
    out = []
    for i, g in enumerate(gaps, 1):
        missing = g["fit"] == 0
        out.append({
            "week": i, "skill": g["skill"], "hours": hours,
            "task": ("Learn the basics of " if missing else "Turn your listed knowledge of ") + g["skill"] + (", then build one small project." if missing else " into a project with visible results."),
            "acceptance": f"A public repo or demo using {g['skill']}, a README, and one line on your resume under Projects.",
        })
    return out

def wilson(k, n, z=1.96):
    if n == 0:
        return [0, 0]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - m), 2), round(min(1, c + m), 2)]

def outcomes(apps):
    n = len(apps)
    stages = {}
    for a in apps:
        stages[a["stage"]] = stages.get(a["stage"], 0) + 1
    replied = sum(1 for a in apps if a["stage"] != "Applied")
    return {"total": n, "by_stage": stages, "replied": replied,
            "reply_rate": round(replied / n, 2) if n else 0, "reply_rate_95ci": wilson(replied, n),
            "warning": "Too few applications to see patterns. Treat this as descriptive only." if n < 10 else ""}
