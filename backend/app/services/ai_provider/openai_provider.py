"""OpenAI Chat Completions provider.

Uses the OpenAI Chat Completions API over plain HTTPS (httpx is already a
project dependency, so no extra SDK is required) with structured JSON output
enabled via ``response_format`` and the function-call ``json_schema`` strict
mode. This yields a reliably schema-shaped JSON object.

No credentials are hardcoded here; the API key is injected at construction
time (from settings in the factory).
"""

import json
import logging
from typing import Any, Dict

import httpx

from app.services.ai_provider.base import (
    AIInvalidResponseError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
    BaseAIProvider,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(BaseAIProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
    ):
        if not api_key:
            raise ValueError("OpenAI API key is required")
        if not model:
            raise ValueError("OpenAI model is required")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, system_prompt, user_prompt, schema, structured=True):
        # json_schema strict mode guarantees the response conforms to the
        # user-provided schema (structured output). When a model/endpoint does
        # not support strict structured output, ``json_object`` basic JSON mode
        # is used as a fallback instead.
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if structured:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "tailored_resume",
                    "strict": True,
                    "schema": schema,
                },
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        # Routers like OpenRouter route to the best provider unless asked to
        # only honor endpoints that support the required parameters. Only add
        # this for non-OpenAI endpoints so direct OpenAI calls are unchanged.
        if self.base_url != DEFAULT_BASE_URL:
            payload["provider"] = {"require_parameters": True}
        return payload

    def _post(self, payload: Dict[str, Any], timeout_seconds: float) -> httpx.Response:
        """POST to the chat completions endpoint, translating HTTP errors into
        controlled provider exceptions (never leaking credentials/internals)."""
        timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds)
        try:
            return httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=timeout,
            )
        except httpx.TimeoutException as exc:
            raise AITimeoutError("AI request timed out") from exc
        except httpx.HTTPError as exc:
            logger.warning("AI provider connection failed: %s", type(exc).__name__)
            raise AIProviderUnavailableError("AI provider is unavailable") from exc

    def _parse_content(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("AI provider response missing choices/content")
            raise AIInvalidResponseError("AI provider returned an unexpected structure") from exc
        if not content or not content.strip():
            raise AIInvalidResponseError("AI provider returned empty content")
        try:
            parsed = json.loads(content)
        except (ValueError, TypeError) as exc:
            logger.warning("AI provider returned non-JSON content")
            raise AIInvalidResponseError("AI provider returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise AIInvalidResponseError("AI provider returned a non-object response")
        return parsed

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        logger.info("AI request provider=openai model=%s (payload bytes omitted)", self.model)

        # Free/under-loaded OpenAI-compatible endpoints (e.g. some OpenRouter
        # :free models) intermittently return HTTP 200 with empty content.
        # Retry a bounded number of times to smooth over this flakiness.
        max_attempts = 3
        last_error = None

        for attempt in range(1, max_attempts + 1):
            # 1) Try strict structured output (json_schema) first.
            resp = self._post(self._build_payload(system_prompt, user_prompt, schema, structured=True), timeout_seconds)

            # 429 / auth / server errors are fatal and mapped as-is.
            if resp.status_code == 429:
                raise AIRateLimitError("AI provider rate limit exceeded")
            if resp.status_code in (401, 403):
                logger.warning("AI provider authentication failed (status=%s)", resp.status_code)
                raise AIProviderUnavailableError("AI provider configuration error")
            if resp.status_code >= 500:
                logger.warning("AI provider server error (status=%s)", resp.status_code)
                raise AIProviderUnavailableError("AI provider is unavailable")

            # 2) If the endpoint rejects strict structured output (400/422) and a
            #    router/other base URL is configured, retry once in basic JSON mode.
            if resp.status_code in (400, 422) and self.base_url != DEFAULT_BASE_URL:
                logger.info("AI provider does not support strict structured output; retrying in JSON mode")
                resp = self._post(
                    self._build_payload(system_prompt, user_prompt, schema, structured=False),
                    timeout_seconds,
                )
                if resp.status_code == 429:
                    raise AIRateLimitError("AI provider rate limit exceeded")
                if resp.status_code in (401, 403):
                    raise AIProviderUnavailableError("AI provider configuration error")
                if resp.status_code >= 500:
                    raise AIProviderUnavailableError("AI provider is unavailable")

            if resp.status_code != 200:
                logger.warning("AI provider unexpected status (status=%s)", resp.status_code)
                raise AIProviderUnavailableError("AI provider request failed")

            try:
                data = resp.json()
            except ValueError as exc:
                raise AIInvalidResponseError("AI provider returned an invalid response") from exc

            try:
                return self._parse_content(data)
            except AIInvalidResponseError as exc:
                last_error = exc
                if attempt < max_attempts:
                    logger.warning(
                        "AI provider returned unusable content (attempt %d/%d); retrying",
                        attempt,
                        max_attempts,
                    )

        raise last_error if last_error else AIInvalidResponseError("AI provider returned an invalid response")
