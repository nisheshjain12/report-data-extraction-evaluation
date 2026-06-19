"""
The ONLY place we talk to the Gemini model.

Why isolate it: extraction logic shouldn't care which model/provider we use.
Swap models, add retries, or move to Ollama later -> change only this file.
"""

import os
from dotenv import load_dotenv
from google import genai

import config

# Read GEMINI_API_KEY from the .env file in the project root.
load_dotenv(config.ROOT / ".env")
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def ask(prompt: str) -> str:
    """Send a plain-text prompt to Gemini and return the text reply."""
    response = _client.models.generate_content(
        model=config.MODEL,
        contents=prompt,
    )
    return response.text


if __name__ == "__main__":
    # Smoke test: prove the key + model work on a trivial call,
    # BEFORE we spend effort pointing it at PDFs.
    print("Model:", config.MODEL)
    print("Reply:", ask("Reply with exactly the word: OK"))
