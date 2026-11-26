"""Configuration and implementation for the Ollama provider."""

import json
import math
import urllib.request
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

from llm_eval.providers.exceptions import (
    ProviderConnectionError,
    ProviderHTTPError,
    ProviderTimeoutError,
)
from llm_eval.providers.models import ModelResponse


def _validate_finite_number(
    value: object,
    field_name: str,
) -> None:
    """Validate that a value is a finite integer or float, excluding bool."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number")

    try:
        is_finite = math.isfinite(value)
    except OverflowError:
        is_finite = False

    if not is_finite:
        raise ValueError(f"{field_name} must be finite")


def _validate_base_url(value: object) -> str:
    """Validate and normalize an HTTP(S) base URL."""

    if not isinstance(value, str):
        raise TypeError("base_url must be a string")

    if not value or any(char.isspace() for char in value):
        raise ValueError("base_url must be a valid HTTP(S) URL")

    try:
        parsed = urlsplit(value)

        if parsed.scheme not in ("http", "https"):
            raise ValueError("base_url must use HTTP or HTTPS")

        if not parsed.hostname:
            raise ValueError("base_url must include a hostname")

        port = parsed.port

        if port == 0:
            raise ValueError("base_url port must be between 1 and 65535")

        if parsed.username is not None or parsed.password is not None:
            raise ValueError("base_url must not contain credentials")

        if "?" in value or "#" in value:
            raise ValueError("base_url must not contain a query or fragment")

    except ValueError as error:
        raise ValueError(f"Invalid base_url: {error}") from error

    return value.rstrip("/")


@dataclass(frozen=True)
class OllamaProviderConfig:
    """Immutable configuration for a local Ollama provider."""

    model: str
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 300.0
    temperature: float | None = None
    top_p: float | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        """Validate configuration values."""

        if not isinstance(self.model, str):
            raise TypeError("model must be a string")

        if not self.model or any(char.isspace() for char in self.model):
            raise ValueError("model must be a non-empty string without whitespace")

        normalized_base_url = _validate_base_url(self.base_url)
        object.__setattr__(self, "base_url", normalized_base_url)

        _validate_finite_number(
            self.timeout_seconds,
            "timeout_seconds",
        )

        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        if self.temperature is not None:
            _validate_finite_number(
                self.temperature,
                "temperature",
            )

            if self.temperature < 0:
                raise ValueError("temperature must be non-negative")

        if self.top_p is not None:
            _validate_finite_number(
                self.top_p,
                "top_p",
            )

            if not 0 <= self.top_p <= 1:
                raise ValueError("top_p must be between 0 and 1")

        if self.seed is not None and (
            isinstance(self.seed, bool) or not isinstance(self.seed, int)
        ):
            raise TypeError("seed must be an integer or None")


class OllamaProvider:
    """Provider implementation for local Ollama models."""

    def __init__(self, config: OllamaProviderConfig) -> None:
        """Initialize the provider with its configuration."""

        self.config = config

    def generate_response(self, prompt: str) -> ModelResponse:
        """Generate a response using the configured Ollama model."""

        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
        }

        options = {
            key: value
            for key, value in {
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
                "seed": self.config.seed,
            }.items()
            if value is not None
        }

        if options:
            payload["options"] = options

        request = urllib.request.Request(
            url=f"{self.config.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds,
            ) as response:
                response.read()
        except HTTPError as exc:
            raise ProviderHTTPError(
                str(exc),
                status_code=exc.code,
            ) from exc
        except TimeoutError as exc:
            raise ProviderTimeoutError(str(exc)) from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ProviderTimeoutError(str(exc)) from exc

            raise ProviderConnectionError(str(exc)) from exc
        except OSError as exc:
            raise ProviderConnectionError(str(exc)) from exc

        raise NotImplementedError
