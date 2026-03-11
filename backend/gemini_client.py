"""
Vertex AI Gemini HTTP Client

Calls the Vertex AI REST endpoint using the API key from Vertex AI Studio.
Matches the curl pattern shown by Google Cloud Console:

  POST https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent?key={API_KEY}

Using :generateContent (non-streaming) instead of :streamGenerateContent
so we get a single complete response — simpler to parse in the pipeline.
"""

import httpx

from config import settings

_BASE_URL = "https://aiplatform.googleapis.com/v1/publishers/google/models"
_TIMEOUT = 60.0


def generate_content(
    prompt: str,
    model: str,
    system_instruction: str | None = None,
    temperature: float = 0.5,
    max_output_tokens: int = 1024,
    response_mime_type: str | None = None,
    response_schema: dict | None = None,
) -> str:
    """
    Synchronous call to Vertex AI Gemini endpoint using API key.
    Intended to be called via asyncio.run_in_executor from async agent methods.

    Args:
        prompt:              User message / augmented prompt.
        model:               Model name, e.g. "gemini-2.5-flash-lite".
        system_instruction:  Agent system prompt (optional).
        temperature:         Sampling temperature (0.0 – 1.0).
        max_output_tokens:   Maximum tokens in the response.
        response_mime_type:  Set "application/json" to enable JSON mode.
        response_schema:     OpenAPI-style JSON schema for controlled output.

    Returns:
        Response text string from the model.

    Raises:
        httpx.HTTPStatusError: If the API returns a non-2xx status.
    """
    url = f"{_BASE_URL}/{model}:generateContent?key={settings.google_api_key}"

    payload: dict = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ]
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}]
        }

    generation_config: dict = {
        "temperature": temperature,
        "maxOutputTokens": max_output_tokens,
    }
    if response_mime_type:
        generation_config["responseMimeType"] = response_mime_type
    if response_schema:
        generation_config["responseSchema"] = response_schema

    payload["generationConfig"] = generation_config

    with httpx.Client(timeout=_TIMEOUT) as client:
        response = client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]
