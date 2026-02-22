"""
Centralized LLM helper — wraps Gemini, Anthropic, and OpenAI API calls.
All agents import `llm_generate` from here.
"""
import json
import logging
import time
from typing import Literal

logger = logging.getLogger(__name__)

Provider = Literal["gemini", "anthropic", "openai"]

# Simple retry with exponential backoff for rate limits
MAX_RETRIES = 5
BASE_DELAY = 4  # seconds


def llm_generate(prompt: str, provider: Provider = "gemini", max_tokens: int = 2000, temperature: float = 0.0) -> str:
    """
    Send a prompt to the selected LLM provider and return the raw text response.
    """
    from config import settings

    if provider == "gemini":
        return _generate_gemini(prompt, max_tokens, temperature)
    elif provider == "anthropic":
        return _generate_anthropic(prompt, max_tokens, temperature)
    elif provider == "openai":
        return _generate_openai(prompt, max_tokens, temperature)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def _generate_gemini(prompt: str, max_tokens: int, temperature: float) -> str:
    import google.generativeai as genai
    from config import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=max_tokens,
        temperature=temperature,
    )

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = model.generate_content(prompt, generation_config=generation_config)
            return response.text.strip()
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "429" in error_str or "Resource exhausted" in error_str or "500" in error_str:
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning(f"Gemini rate limited (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {delay}s...")
                time.sleep(delay)
            else:
                raise
    raise last_error


def _generate_anthropic(prompt: str, max_tokens: int, temperature: float) -> str:
    from anthropic import Anthropic
    from config import settings
    
    if settings.ANTHROPIC_API_KEY == "placeholder":
        raise ValueError("Anthropic API key not configured")

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.content[0].text.strip()


def _generate_openai(prompt: str, max_tokens: int, temperature: float) -> str:
    from openai import OpenAI
    from config import settings

    if settings.OPENAI_API_KEY == "placeholder":
        raise ValueError("OpenAI API key not configured")

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def llm_generate_json(prompt: str, provider: Provider = "gemini", max_tokens: int = 2000, temperature: float = 0.0) -> dict:
    """
    Send a prompt to the selected provider and parse the JSON response.
    Handles markdown code blocks in responses.
    """
    raw = llm_generate(prompt, provider, max_tokens, temperature)

    # Strip markdown code blocks if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
