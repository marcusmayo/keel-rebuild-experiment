"""OpenAI-compatible chat-completions helper.

Reads LLM_BASE_URL (default https://openrouter.ai/api/v1),
OPENROUTER_API_KEY and LLM_MODEL from the environment (falling back to
the .env file). The ONLY places the model is called are the semantic
pass and the scoring factor proposal.
"""
import json
import os
import re
import time

import requests

from common import load_env


def chat(messages, max_tokens=4000, timeout=120):
    load_env()
    base = os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")
    if not key or not model:
        raise RuntimeError("OPENROUTER_API_KEY and LLM_MODEL must be set")
    last_exc = None
    for attempt in range(6):
        try:
            resp = requests.post(
                base.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"model": model, "messages": messages,
                      "max_tokens": max_tokens, "temperature": 0},
                timeout=timeout,
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"{resp.status_code} from API",
                                         response=resp)
            resp.raise_for_status()
            break
        except (requests.HTTPError, requests.ConnectionError,
                requests.Timeout) as e:
            last_exc = e
            time.sleep(min(2 ** attempt * 5, 60))
    else:
        raise last_exc
    content = resp.json()["choices"][0]["message"].get("content")
    if not content:
        raise RuntimeError("model returned empty content "
                           "(reasoning token budget exhausted?)")
    return content


def extract_json(text):
    """Pull the first JSON object out of a model response."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON object in response: {text!r}")
    return json.loads(m.group(0))
