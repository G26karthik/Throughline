"""AI analyst assistant: a natural-language presentation layer over
already-resolved, already-audited data. The resolution engine and
analytics stay fully deterministic and rule-based -- this module only
interprets natural language against their already-computed JSON output,
after the fact. Zero LLM involvement in identity-resolution decisions.
"""
import json
import os

from google import genai

MODEL = "gemini-3.5-flash-lite"

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def summarize_journey(customer_id: str, timeline_data: dict) -> str:
    prompt = (
        "You are an analyst assistant. Write a short (3-5 sentence) plain-English "
        "narrative summary of this customer's cross-channel journey, using only the "
        "structured data below. Do not invent events, channels, or facts not present "
        "in the data.\n\n"
        f"customer_id: {customer_id}\n"
        f"data: {json.dumps(timeline_data)}"
    )
    response = _get_client().models.generate_content(model=MODEL, contents=prompt)
    return (response.text or "").strip()


def query_aggregate(question: str, customers: list[dict], friction_detail: dict[str, dict]) -> dict:
    prompt = (
        "You are an analyst assistant answering a natural-language question over "
        "already-resolved, already-computed customer journey data. Use only the "
        "structured data below -- never invent customer_ids or facts not present in "
        'it. Return strict JSON: {"matches": [{"customer_id": str, "reason": str}], '
        '"answer": str} where answer is a one-sentence plain-English summary of the '
        "result. If nothing matches, return an empty matches list and say so in answer.\n\n"
        f"question: {question}\n"
        f"customers: {json.dumps(customers)}\n"
        f"friction_detail: {json.dumps(friction_detail)}"
    )
    response = _get_client().models.generate_content(
        model=MODEL, contents=prompt, config={"response_mime_type": "application/json"},
    )
    return json.loads(response.text or "{}")
