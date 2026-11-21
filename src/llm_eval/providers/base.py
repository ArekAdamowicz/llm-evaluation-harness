"""Base protocol for model providers."""

from typing import Protocol

from llm_eval.providers.models import ModelResponse


class Provider(Protocol):
    """Interface implemented by model providers.

    A provider accepts a prompt and returns one raw model response.

    Implementations are responsible for:
    - processing or retrieving a response for the supplied prompt,
    - returning the response together with model information and metrics,
    - raising ProviderError subclasses for provider-specific failures.

    Providers do not evaluate responses, execute generated code, or persist
    evaluation results. Response persistence belongs to a separate component.

    Implementations should document their own state and thread-safety
    guarantees.
    """

    def generate_response(self, prompt: str) -> ModelResponse:
        """Generate or retrieve a response for the supplied prompt.

        Args:
            prompt: Exact prompt text to process.

        Returns:
            A ModelResponse containing the raw response and associated metadata.

        Raises:
            TypeError: If prompt is not a string.
            ProviderError: If the provider cannot process or retrieve the response.
        """
        ...
