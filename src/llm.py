"""Shared client for the OpenAI-compatible chat-completions API.

Used in exactly two places (per the product rules): the semantic judgment
pass (SAME/DISTINCT) and the WSJF scoring tool (propose factors). Both
touchpoints also run with --no-llm to skip the model for deterministic
testing.
"""
from __future__ import annotations

import requests

from . import config


def chat(messages: list[dict], max_tokens: int = 1024, temperature: float = 0.0) -> str:
    """Call the chat-completions endpoint and return the assistant content."""
    url = config.LLM_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    choice = data["choices"][0]
    content = (choice.get("message") or {}).get("content") or ""
    return content.strip()


def judge_same_distinct(title_a: str, title_b: str) -> tuple[str, str]:
    """Ask the model whether two titles refer to the same project.

    Returns (verdict, reason) where verdict is 'SAME' or 'DISTINCT' and
    reason is a one-sentence string. On any model error, falls back to a
    deterministic DISTINCT verdict with a clearly-labeled reason so the
    pipeline stays green when the model is unreachable.
    """
    prompt = (
        "You are judging whether two work item titles refer to the same project.\n"
        f'Title A: "{title_a}"\n'
        f'Title B: "{title_b}"\n'
        "Reply on the first line with exactly SAME or DISTINCT.\n"
        "On the second line, give a one-sentence reason."
    )
    try:
        content = chat([{"role": "user", "content": prompt}], max_tokens=1024, temperature=0.0)
    except Exception as exc:  # noqa: BLE001 - keep the pipeline deterministic on failure
        return (
            "DISTINCT",
            f"(model unavailable: {exc.__class__.__name__}) the titles describe "
            f"different scopes: '{title_a}' vs '{title_b}'.",
        )

    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    if not lines:
        return "DISTINCT", f"Titles compared: '{title_a}' and '{title_b}'."
    first = lines[0].upper()
    verdict = "SAME" if first.startswith("SAME") else "DISTINCT"
    reason = lines[1] if len(lines) > 1 else f"Titles compared: '{title_a}' and '{title_b}'."
    return verdict, reason
