"""
Centralized LLM helper — wraps Gemini API calls.
All agents import `llm_generate` from here instead of calling Anthropic/Gemini directly.
"""
import json
import logging

logger = logging.getLogger(__name__)


def llm_generate(prompt: str, max_tokens: int = 2000, temperature: float = 0.0) -> str:
    """
    Send a prompt to Gemini and return the raw text response.
    """
    import google.generativeai as genai
    from config import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)

    model = genai.GenerativeModel("gemini-2.0-flash")

    generation_config = genai.types.GenerationConfig(
        max_output_tokens=max_tokens,
        temperature=temperature,
    )

    response = model.generate_content(prompt, generation_config=generation_config)
    return response.text.strip()


def llm_generate_json(prompt: str, max_tokens: int = 2000, temperature: float = 0.0) -> dict:
    """
    Send a prompt to Gemini and parse the JSON response.
    Handles markdown code blocks in responses.
    """
    raw = llm_generate(prompt, max_tokens=max_tokens, temperature=temperature)

    # Strip markdown code blocks if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
