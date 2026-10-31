import json, logging, re
import httpx
from . import config

logger = logging.getLogger("skillme.llm")

def available():
    return bool(config.ANTHROPIC_KEY)

def status_info():
    """Returns safe status metadata for health checks without exposing API keys."""
    if not config.ANTHROPIC_KEY:
        return {"available": False, "status": "no_key", "model": config.MODEL, "message": "No Anthropic API key configured."}
    return {"available": True, "status": "configured", "model": config.MODEL, "message": "Anthropic API key configured."}

def complete_json(system, user, max_tokens=1200):
    """Ask Claude for JSON. Returns a dict, or None if there is no key or the call fails."""
    if not config.ANTHROPIC_KEY:
        return None
    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            timeout=40,
            headers={
                "x-api-key": config.ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": config.MODEL,
                "max_tokens": max_tokens,
                "system": system + " Reply with JSON only.",
                "messages": [{"role": "user", "content": user}]
            }
        )
        if r.status_code == 400 and "credit balance is too low" in r.text:
            logger.warning("Anthropic API credit balance is too low; falling back to heuristic scoring.")
            return None
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        return json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip())
    except Exception as e:
        logger.warning("LLM completion failed (%s); falling back to heuristic scoring.", type(e).__name__)
        return None
