"""Optional live smoke test for the OpenAI Responses API.

Keep network-dependent checks opt-in so the normal test suite can run in CI
without exposing API keys or making paid requests.
"""
from __future__ import annotations

import json
import os

import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_OPENAI_TESTS") != "1",
    reason="Set RUN_LIVE_OPENAI_TESTS=1 to run the live OpenAI API smoke test.",
)
def test_openai_responses_api_returns_json() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.fail("RUN_LIVE_OPENAI_TESTS=1 but OPENAI_API_KEY is not configured.")

    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-5-nano")
    client = OpenAI(api_key=api_key, timeout=60.0, max_retries=2)
    response = client.responses.create(
        model=model,
        instructions=(
            "You are an API connection tester. Return only a valid JSON object "
            'with keys "status" and "answer". Set status to "ok" and answer to 2.'
        ),
        input="Return the requested JSON object.",
        text={"format": {"type": "json_object"}},
    )
    assert response.output_text, "The model returned an empty response."
    result = json.loads(response.output_text)
    assert result.get("status") == "ok", result
    assert result.get("answer") == 2, result
