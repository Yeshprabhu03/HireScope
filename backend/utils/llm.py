"""
Centralized LLM helper — wraps Gemini, Anthropic, and OpenAI API calls.
All agents import `llm_generate` from here.
"""
import json
import logging
import time
from typing import Literal

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

Provider = Literal["gemini", "anthropic", "openai"]


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True,
    # Optional: we can be specific about which exceptions to retry on if we want,
    # but retrying on all general exceptions is safe for LLM calls.
)
async def llm_generate(prompt: str, provider: Provider = "gemini", max_tokens: int = 2000, temperature: float = 0.0) -> str:
    """
    Send a prompt to the selected LLM provider and return the raw text response.
    Retries automatically on failures (e.g. rate limits, 500s) with exponential backoff.
    """
    if provider == "gemini":
        return await _generate_gemini(prompt, max_tokens, temperature)
    elif provider == "anthropic":
        return await _generate_anthropic(prompt, max_tokens, temperature)
    elif provider == "openai":
        return await _generate_openai(prompt, max_tokens, temperature)
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def _generate_gemini(prompt: str, max_tokens: int, temperature: float) -> str:
    import google.generativeai as genai
    from config import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    generation_config = genai.types.GenerationConfig(
        max_output_tokens=max_tokens,
        temperature=temperature,
    )

    response = await model.generate_content_async(prompt, generation_config=generation_config)
    if not response or not response.text:
        raise ValueError("Gemini returned empty response")
    return response.text.strip()


async def _generate_anthropic(prompt: str, max_tokens: int, temperature: float) -> str:
    from anthropic import AsyncAnthropic
    from config import settings

    if settings.ANTHROPIC_API_KEY == "placeholder":
        raise ValueError("Anthropic API key not configured")

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-3-5-sonnet-20240620",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.content[0].text.strip()


async def _generate_openai(prompt: str, max_tokens: int, temperature: float) -> str:
    from openai import AsyncOpenAI
    import httpx
    from config import settings
    http_client = httpx.AsyncClient()
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, http_client=http_client)
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


async def llm_generate_json(prompt: str, provider: Provider = "gemini", max_tokens: int = 4000, temperature: float = 0.0) -> dict:
    """
    Send a prompt to the selected provider and parse the JSON response.
    Handles markdown code blocks and potential truncation.
    """
    raw = await llm_generate(prompt, provider, max_tokens, temperature)

    # Strip markdown code blocks if present
    processed = raw.strip()
    if processed.startswith("```"):
        # Find the first { and last } to be sure
        first_brace = processed.find("{")
        last_brace = processed.rfind("}")
        if first_brace != -1 and last_brace != -1:
            processed = processed[first_brace : last_brace + 1]
        else:
            # Fallback to old splitting logic if braces not found within blocks
            processed = processed.split("```")[1]
            if processed.startswith("json"):
                processed = processed[4:]
            processed = processed.strip()

    # Final cleanup: ensure it starts/ends with braces
    # We try to find the first '{' and then find the corresponding matching '}'
    # to handle cases where there is extra text AFTER the JSON.
    first_brace = processed.find("{")
    if first_brace != -1:
        # Simple brace counting to find the end of the first object
        brace_count = 0
        in_string = False
        escape = False
        for i in range(first_brace, len(processed)):
            char = processed[i]
            if char == '"' and not escape:
                in_string = not in_string
            if not in_string:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        processed = processed[first_brace : i + 1]
                        break
            if char == "\\":
                escape = not escape
            else:
                escape = False

    try:
        return json.loads(processed)
    except json.JSONDecodeError as e:
        logger.error(f"JSON Parsing failed for provider {provider}. Error: {e}")
        logger.error(f"Raw response: {raw}")
        # If it's still failing with extra data, we can try to trim strictly to the error position
        if "Extra data" in str(e):
             try:
                 return json.loads(processed[:e.pos])
             except:
                 pass

        # Another common case: raw newlines in strings
        try:
            # This is a bit aggressive but can help with multiline text that was not escaped
            lines = processed.splitlines()
            fixed_lines = []
            for line in lines:
                fixed_lines.append(line.strip())
            joined = " ".join(fixed_lines)
            return json.loads(joined)
        except:
            pass

        raise
