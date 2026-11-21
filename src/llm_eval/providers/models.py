"""Data models for providers."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from llm_eval.results.models import (
    Metrics,
    ModelInfo,
    _deep_serialize,
    _freeze_value,
)


def _deserialize_value(value: Any) -> Any:
    """Restore special values and nested containers from serialized data."""

    if isinstance(value, dict):
        if value.get("$type") == "float" and set(value) == {"$type", "value"}:
            special_value = value["value"]

            if special_value == "nan":
                return float("nan")
            if special_value == "inf":
                return float("inf")
            if special_value == "-inf":
                return float("-inf")

            raise ValueError("Invalid serialized special float value")

        return {key: _deserialize_value(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_deserialize_value(item) for item in value]

    return value


def _parse_timestamp(value: Any) -> datetime:
    """Parse a timezone-aware ISO 8601 timestamp."""

    if not isinstance(value, str):
        raise TypeError("timestamp must be a string")

    normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    timestamp = datetime.fromisoformat(normalized)

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")

    return timestamp


@dataclass(frozen=True)
class ModelResponse:
    """Raw response returned by a provider."""

    model_info: ModelInfo
    response_text: str
    metrics: Metrics
    timestamp: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    SCHEMA_VERSION = "1.0"

    def __post_init__(self) -> None:
        """Validate fields and deeply freeze metadata."""

        if not isinstance(self.model_info, ModelInfo):
            raise TypeError(
                f"model_info must be ModelInfo, got {type(self.model_info)}"
            )

        if not isinstance(self.response_text, str):
            raise TypeError(
                f"response_text must be str, got {type(self.response_text)}"
            )

        if not isinstance(self.metrics, Metrics):
            raise TypeError(f"metrics must be Metrics, got {type(self.metrics)}")

        if not isinstance(self.timestamp, datetime):
            raise TypeError(f"timestamp must be datetime, got {type(self.timestamp)}")

        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        if not isinstance(self.metadata, Mapping):
            raise TypeError(f"metadata must be a Mapping, got {type(self.metadata)}")

        frozen_metadata = _freeze_value(dict(self.metadata))
        object.__setattr__(self, "metadata", frozen_metadata)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the response into a JSON-compatible dictionary."""

        return {
            "schema_version": self.SCHEMA_VERSION,
            "model_info": self.model_info.to_dict(),
            "response_text": self.response_text,
            "metrics": self.metrics.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "metadata": _deep_serialize(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelResponse":
        """Restore a ModelResponse from its serialized dictionary."""

        if not isinstance(data, Mapping):
            raise TypeError("data must be a Mapping")

        if data.get("schema_version") != cls.SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported ModelResponse schema version: "
                f"{data.get('schema_version')}"
            )

        required_fields = (
            "model_info",
            "response_text",
            "metrics",
            "timestamp",
            "metadata",
        )

        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")

        model_data = data["model_info"]
        metrics_data = data["metrics"]

        if not isinstance(model_data, Mapping):
            raise TypeError("model_info must be a Mapping")

        if not isinstance(metrics_data, Mapping):
            raise TypeError("metrics must be a Mapping")

        model_info = ModelInfo(
            provider=model_data["provider"],
            name=model_data["name"],
            model_version=model_data.get("model_version"),
            temperature=model_data.get("temperature"),
            top_p=model_data.get("top_p"),
            seed=model_data.get("seed"),
        )

        metrics = Metrics(
            latency_ms=metrics_data.get("latency_ms"),
            input_tokens=metrics_data.get("input_tokens"),
            output_tokens=metrics_data.get("output_tokens"),
            total_tokens=metrics_data.get("total_tokens"),
            estimated_cost=metrics_data.get("estimated_cost"),
            cost_currency=metrics_data.get("cost_currency"),
        )

        metadata = data["metadata"]

        if not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a Mapping")

        return cls(
            model_info=model_info,
            response_text=data["response_text"],
            metrics=metrics,
            timestamp=_parse_timestamp(data["timestamp"]),
            metadata=_deserialize_value(dict(metadata)),
        )
