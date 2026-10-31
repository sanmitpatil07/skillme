"""Optional trained sentence-level skill tagger. Loaded only if models/tagger.joblib exists."""
import logging
from .config import TAGGER
_model = None
_tried = False

def _load():
    global _model, _tried
    if _tried:
        return _model
    _tried = True
    if TAGGER.exists():
        try:
            import joblib
            _model = joblib.load(TAGGER)
        except Exception as e:  # sklearn missing or file corrupt
            logging.warning("Tagger not loaded: %s", e)
    return _model

def predict(sentence, threshold=0.7):
    m = _load()
    if not m:
        return []
    probs = m["pipe"].predict_proba([sentence])[0]
    return [c for c, p in zip(m["classes"], probs) if p >= threshold]
