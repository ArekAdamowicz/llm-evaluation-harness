"""Exceptions raised by provider implementations."""


class ProviderError(Exception):
    """Base exception for provider-related errors."""


class PromptHashMismatchError(ProviderError):
    """Raised when the supplied prompt does not match the fixture hash."""


class InvalidPromptError(ProviderError):
    """Raised when a prompt cannot be processed by a provider."""


class ResponseNotFoundError(ProviderError):
    """Raised when the requested response variant does not exist."""


class AmbiguousResponseError(ProviderError):
    """Raised when multiple response variants exist without an explicit choice."""


class InvalidFixtureError(ProviderError):
    """Raised when a provider fixture is invalid."""
