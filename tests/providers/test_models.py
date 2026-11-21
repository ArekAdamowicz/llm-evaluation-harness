"""Tests for provider response models."""

from datetime import datetime, timezone, tzinfo

import pytest

from llm_eval.providers.models import ModelResponse
from llm_eval.results.models import Metrics, ModelInfo


@pytest.fixture
def valid_model_info():
    return ModelInfo(provider="test", name="test-model")


@pytest.fixture
def valid_metrics():
    return Metrics(latency_ms=100.0)


@pytest.fixture
def valid_timestamp():
    return datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)


class TestModelResponse:
    def test_creates_valid_response(
        self,
        valid_model_info,
        valid_metrics,
        valid_timestamp,
    ):
        response = ModelResponse(
            model_info=valid_model_info,
            response_text="test response",
            metrics=valid_metrics,
            timestamp=valid_timestamp,
            metadata={"key": "value"},
        )

        assert response.model_info == valid_model_info
        assert response.response_text == "test response"
        assert response.metrics == valid_metrics
        assert response.timestamp == valid_timestamp
        assert response.metadata["key"] == "value"

    def test_rejects_naive_timestamp(
        self,
        valid_model_info,
        valid_metrics,
    ):
        naive_timestamp = datetime(2026, 11, 22, 10, 0, 0)

        with pytest.raises(ValueError, match="timezone-aware"):
            ModelResponse(
                model_info=valid_model_info,
                response_text="test",
                metrics=valid_metrics,
                timestamp=naive_timestamp,
            )

    def test_rejects_timestamp_with_tzinfo_but_no_offset(
        self,
        valid_model_info,
        valid_metrics,
    ):
        class FakeTZ(tzinfo):
            def utcoffset(self, dt):
                return None

        bad_timestamp = datetime(
            2026,
            11,
            22,
            10,
            0,
            0,
            tzinfo=FakeTZ(),
        )

        with pytest.raises(ValueError, match="timezone-aware"):
            ModelResponse(
                model_info=valid_model_info,
                response_text="test",
                metrics=valid_metrics,
                timestamp=bad_timestamp,
            )

    def test_metadata_preserves_mapping_access(
        self,
        valid_model_info,
        valid_metrics,
        valid_timestamp,
    ):
        response = ModelResponse(
            model_info=valid_model_info,
            response_text="test",
            metrics=valid_metrics,
            timestamp=valid_timestamp,
            metadata={"key1": "value1", "key2": "value2"},
        )

        assert response.metadata["key1"] == "value1"
        assert response.metadata["key2"] == "value2"
        assert len(response.metadata) == 2

    def test_metadata_is_immutable(
        self,
        valid_model_info,
        valid_metrics,
        valid_timestamp,
    ):
        response = ModelResponse(
            model_info=valid_model_info,
            response_text="test",
            metrics=valid_metrics,
            timestamp=valid_timestamp,
            metadata={"key": "value"},
        )

        with pytest.raises(TypeError):
            response.metadata["new_key"] = "new_value"

    def test_metadata_nested_containers_are_immutable(
        self,
        valid_model_info,
        valid_metrics,
        valid_timestamp,
    ):
        response = ModelResponse(
            model_info=valid_model_info,
            response_text="test",
            metrics=valid_metrics,
            timestamp=valid_timestamp,
            metadata={
                "nested_dict": {"inner": "value"},
                "nested_list": [1, 2, 3],
            },
        )

        with pytest.raises(TypeError):
            response.metadata["nested_dict"]["new_key"] = "new_value"

        with pytest.raises(TypeError):
            response.metadata["nested_list"][0] = 999

    def test_metadata_freezing_does_not_mutate_original_input(
        self,
        valid_model_info,
        valid_metrics,
        valid_timestamp,
    ):
        original_metadata = {
            "nested": {
                "items": [1, 2, 3],
            },
        }

        ModelResponse(
            model_info=valid_model_info,
            response_text="test",
            metrics=valid_metrics,
            timestamp=valid_timestamp,
            metadata=original_metadata,
        )

        original_metadata["nested"]["items"].append(4)

        assert original_metadata["nested"]["items"] == [1, 2, 3, 4]

    def test_rejects_invalid_model_info_type(
        self,
        valid_metrics,
        valid_timestamp,
    ):
        with pytest.raises(TypeError, match="model_info must be ModelInfo"):
            ModelResponse(
                model_info="not-a-model-info",
                response_text="test",
                metrics=valid_metrics,
                timestamp=valid_timestamp,
            )

    def test_rejects_invalid_response_text_type(
        self,
        valid_model_info,
        valid_metrics,
        valid_timestamp,
    ):
        with pytest.raises(TypeError, match="response_text must be str"):
            ModelResponse(
                model_info=valid_model_info,
                response_text=123,
                metrics=valid_metrics,
                timestamp=valid_timestamp,
            )

    def test_rejects_invalid_metrics_type(
        self,
        valid_model_info,
        valid_timestamp,
    ):
        with pytest.raises(TypeError, match="metrics must be Metrics"):
            ModelResponse(
                model_info=valid_model_info,
                response_text="test",
                metrics="not-metrics",
                timestamp=valid_timestamp,
            )

    def test_rejects_invalid_metadata_type(
        self,
        valid_model_info,
        valid_metrics,
        valid_timestamp,
    ):
        with pytest.raises(TypeError, match="metadata must be a Mapping"):
            ModelResponse(
                model_info=valid_model_info,
                response_text="test",
                metrics=valid_metrics,
                timestamp=valid_timestamp,
                metadata=[1, 2, 3],
            )
