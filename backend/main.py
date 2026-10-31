import hashlib, json, re, sqlite3
from typing import List
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import db, interview, parsing, scoring, security as sec
from .config import FRONT
from .taxonomy import ROLES

db.init()
app = FastAPI(title="SkillMe API", version="1.0")
STAGES = ["Applied", "Response received", "Interview", "Offer", "Rejected"]

class Reg(BaseModel):
    email: str
    password: str
    name: str = ""
class Login(BaseModel):
    email: str
    password: str
class ResumeIn(BaseModel):
    text: str
    role: int = 0
    hours: int = 6
class AnalyzeIn(BaseModel):
    text: str
    role: int = 0
class JDIn(BaseModel):
    family: str
    title: str = ""
    text: str
class AppIn(BaseModel):
    company: str
    role: str = ""
    stage: str = "Applied"
class StateIn(BaseModel):
    role: int = 0
    hours: int = 6
    apps: List[AppIn] = []
class VoiceIn(BaseModel):
    text: str
class SessionIn(BaseModel):
    role: int = 0
class Ans(BaseModel):
    q: int
    text: str
class EvalIn(BaseModel):
    answers: List[Ans]

def audit(c, uid, event, detail=""):
    c.execute("INSERT INTO audit(user_id,event,detail) VALUES(?,?,?)", (uid, event, detail[:200]))

def check_role(i):
    if not 0 <= i < len(ROLES):
        raise HTTPException(422, "Unknown role.")

def clean_text(t):
    t = t.strip()
    if len(t) < 80:
        raise HTTPException(422, "Add a resume with at least a few lines of text.")
    return t[:parsing.MAX_CHARS]

def bundle(c, uid):
    u = c.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
    p = c.execute("SELECT * FROM profiles WHERE user_id=?", (uid,)).fetchone()
    apps = [{"id": a["id"], "company": a["company"], "role": a["role"], "stage": a["stage"]}
            for a in c.execute("SELECT * FROM applications WHERE user_id=? ORDER BY id", (uid,))]
    out = {"user": u["name"], "roles": scoring.roles_with_demand(c, uid), "apps": apps,
           "role": p["role"] if p else 0, "hrs": p["hours"] if p else 6, "profile": None, "text": "",
           "latest_interview": None}
    if p and p["text"]:
        out["profile"] = parsing.extract_profile(p["text"])
        out["text"] = p["text"]
    iv = c.execute("SELECT id, role, result_json, created FROM interviews WHERE user_id=? AND result_json IS NOT NULL ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    if iv and iv["result_json"]:
        try:
            out["latest_interview"] = {"id": iv["id"], "role": iv["role"], "result": json.loads(iv["result_json"]), "created": iv["created"]}
        except Exception:
            pass
    return out

# ---------- auth ----------
@app.post("/api/auth/register")
def register(b: Reg):
    if not re.match(r"^\S+@\S+\.\S+$", b.email):
        raise HTTPException(422, "Enter a valid email address.")
    if len(b.password) < 6:
        raise HTTPException(422, "Password needs at least 6 characters.")
    name = (b.name.strip() or b.email.split("@")[0]).title()
    with db.connect() as c:
        try:
            cur = c.execute("INSERT INTO users(email,name,pw) VALUES(?,?,?)", (b.email.lower(), name, sec.hash_pw(b.password)))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "An account with this email already exists.")
        audit(c, cur.lastrowid, "register")
        return {"token": sec.make_token(cur.lastrowid), "name": name}

@app.post("/api/auth/login")
def login(b: Login):
    with db.connect() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (b.email.lower(),)).fetchone()
        if not u or not sec.check_pw(b.password, u["pw"]):
            raise HTTPException(401, "Wrong email or password.")
        audit(c, u["id"], "login")
        return {"token": sec.make_token(u["id"]), "name": u["name"]}

# ---------- profile ----------
@app.get("/api/roles")
def roles():
    with db.connect() as c:
        return scoring.roles_with_demand(c)

@app.post("/api/analyze")
def analyze_public(b: AnalyzeIn):
    """No login, nothing stored. Used by demo mode."""
    check_role(b.role)
    with db.connect() as c:
        return {"profile": parsing.extract_profile(clean_text(b.text)), "roles": scoring.roles_with_demand(c), "role": b.role}

@app.post("/api/profile/parse-file")
async def parse_file(file: UploadFile = File(...), uid: int = Depends(sec.current_user)):
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "File is larger than 5 MB.")
    try:
        return {"text": parsing.file_to_text(file.filename or "", data)}
    except Exception:
        raise HTTPException(422, "Could not read this file. Paste your resume text instead.")

@app.get("/api/profile")
def get_profile(uid: int = Depends(sec.current_user)):
    with db.connect() as c:
        return bundle(c, uid)

@app.post("/api/profile/resume")
def save_resume(b: ResumeIn, uid: int = Depends(sec.current_user)):
    check_role(b.role)
    text = clean_text(b.text)
    with db.connect() as c:
        c.execute("INSERT INTO profiles(user_id,text,role,hours) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET text=excluded.text, role=excluded.role, hours=excluded.hours, updated=CURRENT_TIMESTAMP",
                  (uid, text, b.role, max(1, min(60, b.hours))))
        audit(c, uid, "resume_saved", f"{len(text)} chars")
        return bundle(c, uid)

@app.put("/api/state")
def put_state(b: StateIn, uid: int = Depends(sec.current_user)):
    check_role(b.role)
    with db.connect() as c:
        c.execute("INSERT INTO profiles(user_id,role,hours) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role, hours=excluded.hours",
                  (uid, b.role, max(1, min(60, b.hours))))
        c.execute("DELETE FROM applications WHERE user_id=?", (uid,))
        for a in b.apps[:500]:
            c.execute("INSERT INTO applications(user_id,company,role,stage) VALUES(?,?,?,?)",
                      (uid, a.company[:120], a.role[:120], a.stage if a.stage in STAGES else "Applied"))
        return {"ok": True}

# ---------- jobs, gaps, roadmap ----------
@app.post("/api/jobs/ingest")
def ingest(b: JDIn, uid: int = Depends(sec.current_user)):
    if b.family not in [r["n"] for r in ROLES]:
        raise HTTPException(422, "Pick one of the listed roles.")
    text = b.text.strip()[:20000]
    if len(text) < 80:
        raise HTTPException(422, "Paste the full job description.")
    skills = scoring.jd_skills(text)
    h = hashlib.sha256(re.sub(r"\s+", " ", text.lower()).encode()).hexdigest()
    with db.connect() as c:
        try:
            c.execute("INSERT INTO jobs(user_id,family,title,text,hash,skills_json) VALUES(?,?,?,?,?,?)",
                      (uid, b.family, b.title[:120], text, h, json.dumps(skills)))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "You already added this job description.")
        n = c.execute("SELECT COUNT(*) FROM jobs WHERE user_id=? AND family=?", (uid, b.family)).fetchone()[0]
        return {"skills": skills, "jd_count": n, "blended": n >= 3}

@app.get("/api/roles/{i}/skill-map")
def skill_map(i: int, uid: int = Depends(sec.current_user)):
    check_role(i)
    with db.connect() as c:
        r = scoring.roles_with_demand(c, uid)[i]
        return {"role": r["n"], "jd_count": r["jd_count"], "skills": r["s"]}

@app.post("/api/career/gap-analysis")
def gap(b: SessionIn, uid: int = Depends(sec.current_user)):
    check_role(b.role)
    with db.connect() as c:
        d = bundle(c, uid)
        if not d["profile"]:
            raise HTTPException(409, "Add your resume first.")
        return scoring.score(d["profile"], d["roles"][b.role])

@app.post("/api/roadmap/generate")
def road(b: SessionIn, uid: int = Depends(sec.current_user)):
    check_role(b.role)
    with db.connect() as c:
        d = bundle(c, uid)
        if not d["profile"]:
            raise HTTPException(409, "Add your resume first.")
        return {"weeks": scoring.roadmap(d["profile"], d["roles"][b.role], d["hrs"])}

# ---------- applications ----------
@app.get("/api/applications")
def list_apps(uid: int = Depends(sec.current_user)):
    with db.connect() as c:
        return bundle(c, uid)["apps"]

@app.post("/api/applications")
def add_app(b: AppIn, uid: int = Depends(sec.current_user)):
    if b.stage not in STAGES:
        raise HTTPException(422, "Unknown stage.")
    with db.connect() as c:
        cur = c.execute("INSERT INTO applications(user_id,company,role,stage) VALUES(?,?,?,?)", (uid, b.company[:120], b.role[:120], b.stage))
        return {"id": cur.lastrowid}

@app.patch("/api/applications/{aid}")
def patch_app(aid: int, b: AppIn, uid: int = Depends(sec.current_user)):
    if b.stage not in STAGES:
        raise HTTPException(422, "Unknown stage.")
    with db.connect() as c:
        cur = c.execute("UPDATE applications SET company=?, role=?, stage=? WHERE id=? AND user_id=?", (b.company[:120], b.role[:120], b.stage, aid, uid))
        if not cur.rowcount:
            raise HTTPException(404, "Application not found.")
        return {"ok": True}

@app.delete("/api/applications/{aid}")
def del_app(aid: int, uid: int = Depends(sec.current_user)):
    with db.connect() as c:
        c.execute("DELETE FROM applications WHERE id=? AND user_id=?", (aid, uid))
        return {"ok": True}

@app.get("/api/analytics/application-outcomes")
def analytics(uid: int = Depends(sec.current_user)):
    with db.connect() as c:
        return scoring.outcomes(bundle(c, uid)["apps"])

# ---------- voice ----------
@app.post("/api/voice/interpret")
def voice(b: VoiceIn, uid: int = Depends(sec.current_user)):
    t = b.text.strip()
    low = t.lower()
    ent = {}
    if re.search(r"\bappl", low):
        m = re.search(r"appl(?:ied|y)?\s*(?:to|at)?\s+(.+?)(?:\s+(?:as|for)\s+(?:an?\s+)?(.+))?$", t, re.I)
        ent = {"company": m.group(1).strip() if m else "Unknown", "role": (m.group(2) or "").strip() if m else ""}
        return {"intent": "add_application", "label": "Add application", "entities": ent, "needs_confirmation": True}
    h = re.search(r"(\d+)\s*(?:hours?|hrs?)", low)
    if h:
        return {"intent": "update_hours", "label": "Update weekly hours", "entities": {"hours": int(h.group(1))}, "needs_confirmation": True}
    for i, r in enumerate(ROLES):
        if re.search(r"target|want to (?:be|become)|aim", low) and r["n"].lower().split()[0] in low:
            return {"intent": "set_target_role", "label": "Set target role", "entities": {"role": i}, "needs_confirmation": True}
    return {"intent": "ask_question", "label": "Ask a question", "entities": {}, "needs_confirmation": False}

# ---------- interviews ----------
@app.post("/api/interviews/sessions")
def new_session(b: SessionIn, uid: int = Depends(sec.current_user)):
    check_role(b.role)
    qs = interview.questions(b.role)
    with db.connect() as c:
        cur = c.execute("INSERT INTO interviews(user_id,role,questions_json) VALUES(?,?,?)", (uid, b.role, json.dumps(qs)))
        return {"id": cur.lastrowid, "role": ROLES[b.role]["n"], "questions": qs}

@app.post("/api/interviews/{sid}/evaluate")
def evaluate(sid: int, b: EvalIn, uid: int = Depends(sec.current_user)):
    with db.connect() as c:
        s = c.execute("SELECT * FROM interviews WHERE id=? AND user_id=?", (sid, uid)).fetchone()
        if not s:
            raise HTTPException(404, "Interview session not found.")
        n = len(ROLES[s["role"]]["questions"])
        if not b.answers or any(not 0 <= a.q < n or len(a.text.strip()) < 10 for a in b.answers):
            raise HTTPException(422, "Give an answer of at least a sentence for each question.")
        res = interview.evaluate(s["role"], [a.model_dump() for a in b.answers])
        c.execute("UPDATE interviews SET result_json=? WHERE id=?", (json.dumps(res), sid))
        return res

@app.get("/api/interviews/latest")
def latest_interview(uid: int = Depends(sec.current_user)):
    with db.connect() as c:
        row = c.execute("SELECT id, role, questions_json, result_json, created FROM interviews WHERE user_id=? AND result_json IS NOT NULL ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
        if not row:
            return {"interview": None}
        return {
            "interview": {
                "id": row["id"],
                "role": row["role"],
                "questions": json.loads(row["questions_json"]) if row["questions_json"] else [],
                "result": json.loads(row["result_json"]) if row["result_json"] else None,
                "created": row["created"]
            }
        }

# ---------- privacy ----------
@app.get("/api/export")
def export(uid: int = Depends(sec.current_user)):
    with db.connect() as c:
        d = bundle(c, uid)
        d.pop("roles")
        d["jobs"] = [dict(r) for r in c.execute("SELECT family,title,skills_json,created FROM jobs WHERE user_id=?", (uid,))]
        d["interviews"] = [dict(r) for r in c.execute("SELECT role,result_json,created FROM interviews WHERE user_id=?", (uid,))]
        return d

@app.delete("/api/account")
def delete_account(uid: int = Depends(sec.current_user)):
    with db.connect() as c:
        audit(c, uid, "account_deleted")
        c.execute("DELETE FROM users WHERE id=?", (uid,))
    return {"ok": True}

@app.get("/api/health")
def health():
    from . import llm, tagger
    return {
        "ok": True,
        "llm": llm.available(),
        "llm_info": llm.status_info(),
        "trained_tagger": tagger._load() is not None
    }

if FRONT.exists():
    app.mount("/", StaticFiles(directory=str(FRONT), html=True), name="ui")
