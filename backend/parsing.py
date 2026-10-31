import io, re
from .taxonomy import find_skills
from . import tagger

SEC = re.compile(r"^(academic projects|projects?|work experience|experience|internships?|technical skills|skills|education|certifications?|achievements)\b", re.I)
EDU = re.compile(r"b\.?\s?tech|\bb\.?e\.?\b|bachelor|m\.?\s?tech|\bbca\b|b\.?sc|diploma|university|college|institute", re.I)
MAX_CHARS = 30_000

def file_to_text(name, data):
    n = name.lower()
    if n.endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)[:MAX_CHARS]
    if n.endswith(".docx"):
        from docx import Document
        d = Document(io.BytesIO(data))
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for r in t.rows:
                parts.append(" | ".join(c.text for c in r.cells))
        return "\n".join(parts)[:MAX_CHARS]
    return data.decode("utf-8", errors="ignore")[:MAX_CHARS]

def extract_profile(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    sec, sk, pr, ed = "", {}, [], []
    email = (re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text) or [""])[0]
    ph = (re.search(r"(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}", text) or [""])[0]
    cg = re.search(r"(?:cgpa|gpa)\s*[:\-]?\s*(\d\.\d+)", text, re.I)
    name = lines[0] if lines and len(lines[0]) < 40 and "@" not in lines[0] else ""
    for l in lines:
        h = SEC.match(l)
        if h and len(l) < 40:
            sec = h.group(1).lower()
            continue
        w = 1.0 if re.search(r"project|experience|intern|work", sec) else 0.6 if "cert" in sec else 0.4
        if "project" in sec and len(l) > 12 and len(pr) < 6:
            pr.append(l[:100])
        if EDU.search(l) and len(ed) < 2:
            ed.append(l[:110])
        found = find_skills(l)
        for k in found + [s for s in tagger.predict(l) if s not in found]:
            if k not in sk or sk[k]["fit"] < w:
                sk[k] = {"fit": w, "line": l[:110]}
    return {"name": name, "email": email, "phone": ph, "cgpa": cg.group(1) if cg else "", "edu": ed, "pr": pr, "sk": sk}
