# SkillMe – full-stack (FastAPI + SQLite + web UI)

## Quick Start

### 1. Configure Environment
Copy `.env.example` to `.env` and set your configuration:
```bash
cp .env.example .env
```
Inside `.env`:
* `SKILLME_SECRET`: A long random secret string used for signing JWT tokens.
* `ANTHROPIC_API_KEY`: Your Anthropic Claude API key to enable AI mock interview evaluation.
* `ANTHROPIC_MODEL`: Model identifier (default: `claude-3-5-sonnet-20241022` or `claude-3-5-haiku-20241022`).

> **Security Note:** `.env` is listed in `.gitignore` and is loaded strictly on the backend. The API key is **never** exposed to the browser, client-side code, or API responses.

### 2. Install Dependencies
```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Application
`python-dotenv` loads `.env` automatically:
```bash
uvicorn backend.main:app --reload --port 8000
```
Open [http://localhost:8000](http://localhost:8000) for the web application and [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger API docs.

Run tests:
```bash
python -m pytest
```

---

## What is real
* **Auth & Security:** Hashed passwords (PBKDF2/SHA-256), JWT session tokens, and strict per-user authorization boundaries.
* **Resume Parsing:** Upload PDF, DOCX, or TXT (or paste text); extracts candidate profile, education, CGPA, projects, and evidence-weighted skills.
* **Evidence-Weighted Scoring:** Skills proven in projects receive higher weight than skills merely listed in bullet points.
* **Real Job Demand Blending:** Ingest 3+ real job descriptions per role to automatically re-weight market demand.
* **Weekly Roadmap:** Generates tailored, gap-focused learning plans sized to your weekly study hours.
* **Application Tracker & Analytics:** Job application pipeline tracking with reply-rate analytics (Wilson confidence interval with small-sample indicators).
* **Voice Intent API:** Speech-to-text / voice command parser with pre-save confirmation dialogs.
* **AI Mock Interviews:** 
  * Connects to Anthropic Claude (`claude-3-5-sonnet-20241022`) for 5-dimension rubric scoring: Technical correctness, Problem solving, Communication, Depth, and Role alignment.
  * Provides actionable practice recommendations, evidence citations, and missing concept analysis.
  * Automatic graceful fallback to keyword heuristic evaluation if Anthropic credits are exhausted or no key is present.
* **Privacy & Data Portability:** Download full data export (`GET /api/export`) or permanently delete account (`DELETE /api/account`).

---

## API Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Service health, LLM connectivity status, and model metadata (keys never exposed) |
| `POST` | `/api/auth/register` | Create an account and receive JWT token |
| `POST` | `/api/auth/login` | Authenticate and receive JWT token |
| `GET` | `/api/profile` | Retrieve user profile, applications, roles, and latest interview score |
| `POST` | `/api/profile/resume` | Save and parse resume text |
| `POST` | `/api/profile/parse-file` | Parse uploaded PDF or DOCX file |
| `POST` | `/api/interviews/sessions` | Create a new mock interview session for target role |
| `POST` | `/api/interviews/{id}/evaluate` | Score interview answers with Claude AI rubric or heuristic |
| `GET` | `/api/interviews/latest` | Retrieve user's most recent interview session and scores |
| `POST` | `/api/jobs/ingest` | Ingest real job description to blend market skill weights |
| `GET` | `/api/export` | Download full personal data export in JSON format |
| `DELETE` | `/api/account` | Permanently wipe account and data |

---

## Training (honest version)
No model can be trained on "the whole internet" from this repo, and more data does not help without labels.
1. Collect job descriptions you are allowed to use in a folder.
2. Hand-label ~300 sentences into `gold.jsonl` (`{"text": "...", "skills": [...]}`) and keep them OUT of training.
3. `cd training && python train_tagger.py --weak ../my_jds/` (or `--data labelled.jsonl`) -> `models/tagger.joblib`
4. `python evaluate.py gold.jsonl` compares matcher vs matcher+tagger. Keep the model only if it wins there.
5. Grow the taxonomy with `build_taxonomy_from_esco.py` (free ESCO CSV). The API loads the tagger automatically.
`make_synthetic.py` only smoke-tests the pipeline. Its scores are meaningless.

---

## Limits
Salaries are indicative. Interview heuristic is not a hiring predictor. SQLite is for demos; use Postgres for production.
