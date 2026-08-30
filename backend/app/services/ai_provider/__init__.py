"""AI provider package.

The factory here is the single place that maps a configured provider name to a
concrete implementation. The tailoring service only ever talks to
``BaseAIProvider``.
"""

import logging
from typing import TYPE_CHECKING

from app.services.ai_provider.base import (
    AIInvalidResponseError,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderUnavailableError,
    AIRateLimitError,
    AITimeoutError,
    BaseAIProvider,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.services.ai_provider.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

__all__ = [
    "AIInvalidResponseError",
    "AIProviderConfigurationError",
    "AIProviderError",
    "AIProviderUnavailableError",
    "AIRateLimitError",
    "AITimeoutError",
    "BaseAIProvider",
    "get_provider",
]


def get_provider(
    provider_name: str,
    api_key: str,
    model: str,
    base_url: str = "",
) -> BaseAIProvider:
    """Build a configured AI provider instance.

    Raises:
        AIProviderConfigurationError: when provider is not configured or the
            provider name is unknown.
    """
    name = (provider_name or "").strip().lower()

    if not name:
        raise AIProviderConfigurationError(
            "AI provider is not configured. Set AI_PROVIDER, AI_API_KEY and "
            "AI_MODEL in the environment."
        )
    if not (api_key or "").strip():
        raise AIProviderConfigurationError(
            "AI provider API key is not configured. Set AI_API_KEY."
        )

    if name == "openai":
        from app.services.ai_provider.openai_provider import OpenAIProvider

        if not (model or "").strip():
            raise AIProviderConfigurationError(
                "AI provider model is not configured. Set AI_MODEL."
            )
        return OpenAIProvider(api_key=api_key.strip(), model=model.strip(), base_url=(base_url or "").strip())

    logger.warning("Unknown AI provider requested: %s", name)
    raise AIProviderConfigurationError(
        f"Unsupported AI provider: '{provider_name}'. Supported: 'openai'."
    )
