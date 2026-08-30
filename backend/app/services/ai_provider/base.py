"""AI provider abstraction for the AI resume tailoring backend (Phase 3A).

The rest of the application depends only on this small interface, never on a
specific vendor SDK. New providers can be added behind the same contract
without rewriting the tailoring service.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class AIProviderError(Exception):
    """Base class for all AI provider errors."""


class AIProviderConfigurationError(AIProviderError):
    """Raised when the AI provider is not configured (e.g. missing API key)."""


class AIProviderUnavailableError(AIProviderError):
    """Raised when the provider cannot be reached (network / server failure)."""


class AITimeoutError(AIProviderError):
    """Raised when an external AI request exceeds its timeout."""


class AIRateLimitError(AIProviderError):
    """Raised when the provider returns a rate-limit response."""


class AIInvalidResponseError(AIProviderError):
    """Raised when the provider returns unparsable/invalid content."""


class BaseAIProvider(ABC):
    """Minimal provider contract: produce one structured JSON object per call.

    Implementations must never raise raw vendor exceptions; they translate them
    into the error types above. They must not log sensitive prompt content.
    """

    @abstractmethod
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Dict[str, Any],
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        """Return a validated (as JSON) dictionary matching ``schema``.

        The provider is responsible for parsing the model's structured output
        into a plain dict and raising AIInvalidResponseError if it cannot.
        It is NOT responsible for Pydantic validation of semantics (that is
        the caller's job); it must only return a JSON object.
        """
        raise NotImplementedError
