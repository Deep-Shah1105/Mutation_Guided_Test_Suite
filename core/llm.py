"""OpenAI Responses API wrapper for GPT-5 nano.

The public ask_json interface is intentionally provider-specific only here, so all
agents can keep calling ask_json(system, prompt, max_tokens=...).
"""
from __future__ import annotations

import json
import os
from typing import Any


def ask_json(
    system: str,
    prompt: str,
    max_tokens: int = 1800,
) -> dict[str, Any] | None:
    """Return a JSON object from GPT-5 nano, None when no key is configured.

    API and parsing failures are returned as a dictionary containing _llm_error;
    agent nodes can log the error and use their existing fallback behavior.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            timeout=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "60")),
            max_retries=2,
        )
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-nano"),
            instructions=(
                system.strip()
                + "\nReturn exactly one valid JSON object. Do not use Markdown fences. "
                + "Do not include any text before or after the JSON object."
            ),
            input=(
                "Respond to the task below with a JSON object only. "
                "The word JSON refers to the required output format.\n\n"
                + prompt
            ),
            text={"format": {"type": "json_object"}},
            max_output_tokens=max(256, int(max_tokens)),
            reasoning={"effort": "low"},
        )

        # Responses can be incomplete (for example, if the output token limit is hit).
        if getattr(response, "status", None) == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", None) or "unknown reason"
            return {"_llm_error": f"OpenAI response was incomplete: {reason}. Increase max_tokens if needed."}

        content = getattr(response, "output_text", None)
        if not content or not content.strip():
            return {"_llm_error": "OpenAI returned an empty response."}

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            preview = content[:300].replace("\n", " ")
            return {
                "_llm_error": (
                    f"OpenAI returned invalid JSON ({exc.msg} at character {exc.pos}). "
                    f"Response preview: {preview!r}"
                )
            }

        if not isinstance(parsed, dict):
            return {"_llm_error": "OpenAI returned JSON, but the top-level value was not an object."}
        return parsed

    except Exception as exc:
        # Do not hide provider errors; agents log these and can replan/fall back.
        return {"_llm_error": f"{type(exc).__name__}: {exc}"}
