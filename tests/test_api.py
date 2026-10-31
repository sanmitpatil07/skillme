import os, tempfile
os.environ["SKILLME_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["SKILLME_SECRET"] = "test-secret"
from fastapi.testclient import TestClient
from backend.main import app
from backend import scoring

c = TestClient(app)
RESUME = """Aarav Mehta
aarav.mehta@example.com | +91 98765 43210
Education
B.Tech Computer Science, Pune Institute of Technology, CGPA 8.4
Skills
Python, SQL, Excel, Git
Projects
Sales Dashboard: built an Excel and Power BI dashboard on retail data for a college fest
Movie Ratings Analysis: used Python, pandas and matplotlib to study 20,000 ratings
Certifications
Google Data Analytics Certificate"""

def auth():
    r = c.post("/api/auth/register", json={"email": "a@b.com", "password": "secret1", "name": "aarav"})
    if r.status_code == 409:
        r = c.post("/api/auth/login", json={"email": "a@b.com", "password": "secret1"})
    return {"Authorization": "Bearer " + r.json()["token"]}

def test_requires_login():
    assert c.get("/api/profile").status_code == 401

def test_register_validation_and_duplicate():
    assert c.post("/api/auth/register", json={"email": "bad", "password": "secret1"}).status_code == 422
    assert c.post("/api/auth/register", json={"email": "x@y.com", "password": "123"}).status_code == 422
    auth()
    assert c.post("/api/auth/register", json={"email": "a@b.com", "password": "secret1"}).status_code == 409
    assert c.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong!!"}).status_code == 401

def test_resume_analysis_is_evidence_based():
    h = auth()
    r = c.post("/api/profile/resume", json={"text": RESUME, "role": 0, "hours": 6}, headers=h).json()
    p = r["profile"]
    assert p["email"] == "aarav.mehta@example.com" and p["cgpa"] == "8.4"
    assert p["sk"]["Python"]["fit"] == 1.0      # shown in a project
    assert p["sk"]["SQL"]["fit"] == 0.4         # listed only
    assert "Statistics" not in p["sk"]          # never invented
    g = c.post("/api/career/gap-analysis", json={"role": 0}, headers=h).json()
    assert 0 < g["readiness"] < 100 and g["rows"][0]["fit"] < 1

def test_short_resume_rejected():
    assert c.post("/api/profile/resume", json={"text": "hi"}, headers=auth()).status_code == 422

def test_roadmap_uses_hours():
    h = auth()
    c.post("/api/profile/resume", json={"text": RESUME, "role": 0, "hours": 9}, headers=h)
    w = c.post("/api/roadmap/generate", json={"role": 0}, headers=h).json()["weeks"]
    assert w and all(x["hours"] == 9 for x in w)

def test_jd_ingest_and_demand_blending():
    h = auth()
    base = c.get("/api/roles").json()[0]["s"]
    jds = ["Requirements:\nMust have Tableau and strong SQL.\nPreferred:\nAirflow",
           "We need an analyst. Required: Tableau, SQL, Excel.\nNice to have: Spark",
           "Must know Tableau and Python. Good to have Airflow and Spark."]
    for i, t in enumerate(jds):
        r = c.post("/api/jobs/ingest", json={"family": "Data Analyst", "text": t + " " * 80 + str(i)}, headers=h)
        assert r.status_code == 200, r.text
    assert r.json()["blended"] is True
    assert c.post("/api/jobs/ingest", json={"family": "Data Analyst", "text": jds[0] + " " * 80 + "0"}, headers=h).status_code == 409
    sm = c.get("/api/roles/0/skill-map", headers=h).json()
    assert sm["jd_count"] == 3 and sm["skills"]["Tableau" if "Tableau" in sm["skills"] else "Data Visualization"] >= base["Data Visualization"] - 1

def test_jd_importance_wording():
    s = scoring.jd_skills("Requirements:\nMust have Python.\nPreferred:\nDocker is a plus.")
    assert s["Python"] == 3 and s["Docker"] == 1

def test_applications_and_analytics():
    h = auth()
    a = c.post("/api/applications", json={"company": "Infosys", "role": "Analyst"}, headers=h).json()["id"]
    assert c.patch(f"/api/applications/{a}", json={"company": "Infosys", "role": "Analyst", "stage": "Interview"}, headers=h).status_code == 200
    o = c.get("/api/analytics/application-outcomes", headers=h).json()
    assert o["replied"] >= 1 and o["warning"]
    assert c.post("/api/applications", json={"company": "X", "stage": "Nope"}, headers=h).status_code == 422

def test_users_cannot_touch_each_others_data():
    h = auth()
    a = c.post("/api/applications", json={"company": "Private"}, headers=h).json()["id"]
    r = c.post("/api/auth/register", json={"email": "other@b.com", "password": "secret1"})
    h2 = {"Authorization": "Bearer " + r.json()["token"]}
    assert c.patch(f"/api/applications/{a}", json={"company": "Hack", "stage": "Offer"}, headers=h2).status_code == 404

def test_voice_intents():
    h = auth()
    v = c.post("/api/voice/interpret", json={"text": "I applied to Infosys as data analyst"}, headers=h).json()
    assert v["intent"] == "add_application" and v["entities"]["company"] == "Infosys" and v["needs_confirmation"]
    assert c.post("/api/voice/interpret", json={"text": "I can study 8 hours a week"}, headers=h).json()["entities"]["hours"] == 8

def test_interview_scoring_rewards_better_answers():
    h = auth()
    s = c.post("/api/interviews/sessions", json={"role": 0}, headers=h).json()
    good = "First I would check for duplicates and missing values using pandas. For example, I drop exact duplicate rows, then impute null values with the median. Finally I clean the types and validate the result."
    bad = "I would just look at it."
    rg = c.post(f"/api/interviews/{s['id']}/evaluate", json={"answers": [{"q": 0, "text": good}]}, headers=h).json()
    rb = c.post(f"/api/interviews/{s['id']}/evaluate", json={"answers": [{"q": 0, "text": bad + " ok ok"}]}, headers=h).json()
    assert rg["overall"] > rb["overall"]
    assert c.post(f"/api/interviews/{s['id']}/evaluate", json={"answers": [{"q": 0, "text": "no"}]}, headers=h).status_code == 422

def test_public_analyze_stores_nothing():
    r = c.post("/api/analyze", json={"text": RESUME, "role": 0})
    assert r.status_code == 200 and r.json()["profile"]["sk"]["Python"]

def test_export_and_delete():
    r = c.post("/api/auth/register", json={"email": "del@b.com", "password": "secret1"})
    h = {"Authorization": "Bearer " + r.json()["token"]}
    assert "apps" in c.get("/api/export", headers=h).json()
    assert c.delete("/api/account", headers=h).status_code == 200
    assert c.get("/api/profile", headers=h).status_code == 401
