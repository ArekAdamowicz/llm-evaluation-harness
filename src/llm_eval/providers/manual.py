"""Manual provider for testing with pre-prepared responses."""

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_eval.providers.exceptions import (
    AmbiguousResponseError,
    InvalidFixtureError,
    InvalidPromptError,
    PromptHashMismatchError,
    ResponseNotFoundError,
)
from llm_eval.providers.models import ModelResponse
from llm_eval.results.models import Metrics, ModelInfo


def _reject_json_constant(value: str) -> None:
    """Reject non-standard JSON numeric constants."""

    raise ValueError(f"Invalid JSON numeric constant: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate keys in JSON objects."""

    result = {}

    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value

    return result


def _is_finite_number(value: float) -> bool:
    """Check numeric finiteness without leaking integer conversion overflow."""

    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _validate_optional_non_empty_string(
    value: Any,
    field_name: str,
    response_index: int,
) -> None:
    """Validate an optional string field."""

    if value is None:
        return

    if not isinstance(value, str) or not value.strip():
        raise InvalidFixtureError(
            f"Response variant {response_index} "
            f"{field_name} must be a non-empty string or null"
        )


@dataclass(frozen=True)
class ManualProviderConfig:
    """Configuration for the manual provider."""

    fixture_path: Path
    prompt_id: str
    response_id: str | None = None

    def __post_init__(self) -> None:
        """Validate provider configuration."""

        if not isinstance(self.fixture_path, Path):
            raise TypeError("fixture_path must be a Path")

        if not isinstance(self.prompt_id, str) or not self.prompt_id.strip():
            raise ValueError("prompt_id must be a non-empty string")

        if self.response_id is not None and (
            not isinstance(self.response_id, str) or not self.response_id.strip()
        ):
            raise ValueError("response_id must be a non-empty string")


class ManualProvider:
    """Provider that returns manually prepared responses."""

    def __init__(self, config: ManualProviderConfig) -> None:
        if not isinstance(config, ManualProviderConfig):
            raise TypeError("config must be ManualProviderConfig")

        self.config = config
        self._responses: dict[str, ModelResponse] = {}
        self._prompt_hash: str | None = None

        self._load_and_validate_fixture()

    def _load_and_validate_fixture(self) -> None:
        """Load, validate, and prepare the fixture."""

        if not self.config.fixture_path.is_file():
            raise InvalidFixtureError(
                f"Fixture file does not exist: {self.config.fixture_path}"
            )

        try:
            with self.config.fixture_path.open(
                "r",
                encoding="utf-8",
            ) as fixture_file:
                fixture_data = json.load(
                    fixture_file,
                    parse_constant=_reject_json_constant,
                    object_pairs_hook=_reject_duplicate_keys,
                )
        except (json.JSONDecodeError, ValueError) as error:
            raise InvalidFixtureError(
                f"Invalid JSON in fixture file: {error}"
            ) from error
        except UnicodeDecodeError as error:
            raise InvalidFixtureError(
                f"Fixture file is not valid UTF-8: {error}"
            ) from error
        except OSError as error:
            raise InvalidFixtureError(f"Cannot read fixture file: {error}") from error

        prompt_hash = self._validate_fixture_schema(fixture_data)

        self._prompt_hash = prompt_hash
        self._load_responses(fixture_data["responses"])

    def _validate_fixture_schema(self, fixture_data: Any) -> str:
        """Validate the top-level fixture structure and return its prompt hash."""

        if not isinstance(fixture_data, dict):
            raise InvalidFixtureError("Fixture root must be a JSON object")

        required_fields = (
            "schema_version",
            "prompt_id",
            "prompt_hash",
            "responses",
        )

        for field_name in required_fields:
            if field_name not in fixture_data:
                raise InvalidFixtureError(f"Missing required field: {field_name}")

        schema_version = fixture_data["schema_version"]

        if not isinstance(schema_version, str):
            raise InvalidFixtureError("schema_version must be a string")

        if schema_version != "1.0":
            raise InvalidFixtureError(f"Unsupported schema version: {schema_version}")

        fixture_prompt_id = fixture_data["prompt_id"]

        if not isinstance(fixture_prompt_id, str) or not fixture_prompt_id.strip():
            raise InvalidFixtureError("prompt_id must be a non-empty string")

        if fixture_prompt_id != self.config.prompt_id:
            raise InvalidFixtureError(
                f"Prompt ID mismatch. Expected: {self.config.prompt_id}, "
                f"got: {fixture_prompt_id}"
            )

        prompt_hash = fixture_data["prompt_hash"]

        if not isinstance(prompt_hash, str):
            raise InvalidFixtureError("prompt_hash must be a string")

        if re.fullmatch(r"[0-9a-f]{64}", prompt_hash) is None:
            raise InvalidFixtureError("prompt_hash must be a valid SHA-256 hash")

        responses = fixture_data["responses"]

        if not isinstance(responses, list):
            raise InvalidFixtureError("responses must be a list")

        if not responses:
            raise InvalidFixtureError("responses must be a non-empty list")

        response_ids = []

        for index, response in enumerate(responses):
            if not isinstance(response, dict):
                raise InvalidFixtureError(
                    f"Response variant {index} must be a JSON object"
                )

            response_id = self._validate_response_variant(response, index)
            response_ids.append(response_id)

        if len(response_ids) != len(set(response_ids)):
            raise InvalidFixtureError("response_id must be unique within fixture")

        return prompt_hash

    def _validate_response_variant(
        self,
        response: dict[str, Any],
        index: int,
    ) -> str:
        """Validate a single response variant."""

        required_fields = (
            "response_id",
            "model_name",
            "response_text",
            "created_at",
        )

        for field_name in required_fields:
            if field_name not in response:
                raise InvalidFixtureError(
                    f"Response variant {index} missing required field: {field_name}"
                )

        response_id = response["response_id"]

        if not isinstance(response_id, str) or not response_id.strip():
            raise InvalidFixtureError(
                f"Response variant {index} response_id must be a non-empty string"
            )

        model_name = response["model_name"]

        if not isinstance(model_name, str) or not model_name.strip():
            raise InvalidFixtureError(
                f"Response variant {index} model_name must be a non-empty string"
            )

        response_text = response["response_text"]

        if not isinstance(response_text, str) or not response_text.strip():
            raise InvalidFixtureError(
                f"Response variant {index} response_text must be a non-empty string"
            )

        created_at = response["created_at"]

        if not isinstance(created_at, str):
            raise InvalidFixtureError(
                f"Response variant {index} created_at must be a string"
            )

        try:
            timestamp = self._parse_timestamp(created_at)
        except ValueError as error:
            raise InvalidFixtureError(
                f"Response variant {index} has invalid created_at: {error}"
            ) from error

        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise InvalidFixtureError(
                f"Response variant {index} created_at must include timezone"
            )

        metadata = response.get("metadata", {})

        if not isinstance(metadata, dict):
            raise InvalidFixtureError(
                f"Response variant {index} metadata must be a JSON object"
            )

        for field_name in ("model_version", "cost_currency"):
            _validate_optional_non_empty_string(
                response.get(field_name),
                field_name,
                index,
            )

        for field_name in ("latency_ms", "estimated_cost"):
            if field_name not in response:
                continue

            value = response[field_name]

            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not _is_finite_number(value)
                or value < 0
            ):
                raise InvalidFixtureError(
                    f"Response variant {index} "
                    f"{field_name} must be a finite non-negative number"
                )

        return response_id

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        """Parse an ISO 8601 timestamp."""

        if value.endswith("Z"):
            value = f"{value[:-1]}+00:00"

        return datetime.fromisoformat(value)

    def _load_responses(self, response_variants: list[dict[str, Any]]) -> None:
        """Create ModelResponse objects from validated fixture variants."""

        for response_data in response_variants:
            response_id = response_data["response_id"]

            try:
                metrics = Metrics(
                    latency_ms=response_data.get("latency_ms"),
                    input_tokens=response_data.get("input_tokens"),
                    output_tokens=response_data.get("output_tokens"),
                    total_tokens=response_data.get("total_tokens"),
                    estimated_cost=response_data.get("estimated_cost", 0.0),
                    cost_currency=response_data.get("cost_currency"),
                )

                model_info = ModelInfo(
                    provider="manual",
                    name=response_data["model_name"],
                    model_version=response_data.get("model_version"),
                    temperature=response_data.get("temperature"),
                    top_p=response_data.get("top_p"),
                    seed=response_data.get("seed"),
                )

                timestamp = self._parse_timestamp(response_data["created_at"])

                metadata = dict(response_data.get("metadata", {}))
                metadata["response_id"] = response_id
                metadata["prompt_hash"] = self._prompt_hash

                model_response = ModelResponse(
                    model_info=model_info,
                    response_text=response_data["response_text"],
                    metrics=metrics,
                    timestamp=timestamp,
                    metadata=metadata,
                )

            except (TypeError, ValueError, OverflowError) as error:
                raise InvalidFixtureError(
                    f"Failed to load response variant '{response_id}': {error}"
                ) from error

            self._responses[response_id] = model_response

    def generate_response(self, prompt: str) -> ModelResponse:
        """Return a prepared response after validating the exact prompt text."""

        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")

        try:
            prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        except UnicodeEncodeError as error:
            raise InvalidPromptError("Prompt cannot be encoded as UTF-8") from error

        if prompt_hash != self._prompt_hash:
            raise PromptHashMismatchError(
                f"Prompt hash mismatch. Expected: {self._prompt_hash}, "
                f"got: {prompt_hash}"
            )

        if self.config.response_id is None:
            if len(self._responses) > 1:
                available = list(self._responses)

                raise AmbiguousResponseError(
                    f"Multiple response variants available: {available}. "
                    "Specify response_id in ManualProviderConfig."
                )

            response_id = next(iter(self._responses))

        else:
            response_id = self.config.response_id

        if response_id not in self._responses:
            available = list(self._responses)

            raise ResponseNotFoundError(
                f"Response variant '{response_id}' not found. "
                f"Available variants: {available}"
            )

        return self._responses[response_id]
