"""Thin OpenAI-compatible chat-completions client.

The AI model is consulted in exactly two places: judging the ambiguous bucket
(SAME/DISTINCT) and proposing WSJF scoring factors. Both callers must also be
able to run with --no-llm, in which case this client is never invoked.
"""
from __future__ import annotations

import json
from typing import List, Dict

import requests

from .config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL


class LLMError(RuntimeError):
    """Raised when the model call fails or returns an unusable response."""


def chat(messages: List[Dict], *, temperature: float = 0.0,
         max_tokens: int = 512, timeout: int = 60) -> str:
    """Call the chat-completions endpoint and return the message content.

    Deterministic by default (temperature 0). Raises LLMError on any failure.
    """
    if not LLM_API_KEY:
        raise LLMError("OPENROUTER_API_KEY is not set")
    if not LLM_MODEL:
        raise LLMError("LLM_MODEL is not set")

    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=timeout)
    except requests.RequestException as exc:  # network failure
        raise LLMError(f"request failed: {exc}") from exc

    if resp.status_code != 200:
        raise LLMError(f"HTTP {resp.status_code}: {resp.text[:400]}")

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError) as exc:
        raise LLMError(f"bad response shape: {exc}") from exc

    if content is None:
        raise LLMError("model returned null content")
    return content.strip()


def extract_json(text: str) -> Dict:
    """Best-effort extraction of a single JSON object from model text."""
    text = text.strip()
    # Strip common markdown code fences.
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first fence line and any trailing fence
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    # Fall back to the first {...} span.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise LLMError(f"could not parse JSON from model output: {text[:200]}")
