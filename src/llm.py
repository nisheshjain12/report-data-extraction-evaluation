"""
Single integration point for the Gemini model.

Isolating all model calls here keeps the extraction logic independent of the
provider, and centralizes concerns like retries and the API key. `ask` returns
text; `ask_structured` returns a schema-validated object.
"""

import os
import time
from dotenv import load_dotenv
from google import genai

import config

# Read GEMINI_API_KEY from the .env file in the project root.
load_dotenv(config.ROOT / ".env")
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def ask(prompt: str) -> str:
    """Send a plain-text prompt to Gemini and return the text reply.

    Retries with backoff so a free-tier rate limit (429) doesn't abort a run.
    """
    last_error = None
    for attempt in range(5):
        try:
            response = _client.models.generate_content(
                model=config.MODEL,
                contents=prompt,
            )
            return response.text
        except Exception as e:  # transient rate-limit (429) or overload (503)
            last_error = e
            time.sleep(min(60, 15 * (attempt + 1)))  # 15s, 30s, 45s, 60s, 60s
    raise last_error


def ask_structured(prompt: str, schema):
    """Send a prompt and get back a parsed Pydantic object (used by v3).

    Passes Gemini's `response_schema` so the API GUARANTEES valid JSON matching `schema`
    — no manual parsing, no parse failures. Same retry/backoff as ask().
    """
    last_error = None
    for attempt in range(5):
        try:
            response = _client.models.generate_content(
                model=config.MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
            if response.parsed is not None:
                return response.parsed
            return schema.model_validate_json(response.text)  # fallback
        except Exception as e:
            last_error = e
            time.sleep(min(60, 15 * (attempt + 1)))
    raise last_error


if __name__ == "__main__":
    # Smoke test: verify the API key and model with a trivial request.
    print("Model:", config.MODEL)
    print("Reply:", ask("Reply with exactly the word: OK"))
