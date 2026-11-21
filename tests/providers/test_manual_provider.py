"""Tests for the manual provider."""

import hashlib
import json

import pytest

from llm_eval.providers.exceptions import (
    AmbiguousResponseError,
    InvalidFixtureError,
    PromptHashMismatchError,
    ResponseNotFoundError,
)
from llm_eval.providers.manual import ManualProvider, ManualProviderConfig

PROMPT = "Write a function to calculate average"
PROMPT_ID = "CG-001-v1.2"
PROMPT_HASH = hashlib.sha256(PROMPT.encode("utf-8")).hexdigest()


def make_response(
    response_id="correct",
    model_name="test-model",
    response_text="def calculate_average(numbers):\n    return sum(numbers) / len(numbers)",
    created_at="2026-11-22T10:00:00Z",
    **extra,
):
    return {
        "response_id": response_id,
        "model_name": model_name,
        "response_text": response_text,
        "created_at": created_at,
        **extra,
    }


def make_fixture(
    responses=None,
    prompt_id=PROMPT_ID,
    prompt_hash=PROMPT_HASH,
    schema_version="1.0",
):
    return {
        "schema_version": schema_version,
        "prompt_id": prompt_id,
        "prompt_hash": prompt_hash,
        "responses": responses if responses is not None else [make_response()],
    }


@pytest.fixture
def fixture_file(tmp_path):
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(
        json.dumps(make_fixture()),
        encoding="utf-8",
    )
    return fixture_path


@pytest.fixture
def valid_config(fixture_file):
    return ManualProviderConfig(
        fixture_path=fixture_file,
        prompt_id=PROMPT_ID,
        response_id="correct",
    )


class TestManualProviderLoading:
    def test_loads_valid_fixture(self, valid_config):
        provider = ManualProvider(valid_config)

        response = provider.generate_response(PROMPT)

        assert response.response_text.startswith("def calculate_average")
        assert response.model_info.provider == "manual"
        assert response.model_info.name == "test-model"

    def test_raises_error_for_missing_file(self, tmp_path):
        config = ManualProviderConfig(
            fixture_path=tmp_path / "missing.json",
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="does not exist"):
            ManualProvider(config)

    def test_raises_error_for_invalid_json(self, tmp_path):
        fixture_path = tmp_path / "invalid.json"
        fixture_path.write_text("{invalid json", encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="Invalid JSON"):
            ManualProvider(config)

    def test_raises_error_for_root_not_object(self, tmp_path):
        fixture_path = tmp_path / "array.json"
        fixture_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="JSON object"):
            ManualProvider(config)

    @pytest.mark.parametrize(
        "missing_field",
        ["schema_version", "prompt_id", "prompt_hash", "responses"],
    )
    def test_raises_error_for_missing_required_field(
        self,
        tmp_path,
        missing_field,
    ):
        data = make_fixture()
        del data[missing_field]

        fixture_path = tmp_path / "missing-field.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="Missing required field"):
            ManualProvider(config)

    def test_rejects_unsupported_schema_version(self, tmp_path):
        data = make_fixture(schema_version="2.0")
        fixture_path = tmp_path / "unsupported.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="Unsupported schema"):
            ManualProvider(config)

    def test_rejects_invalid_prompt_hash(self, tmp_path):
        data = make_fixture(prompt_hash="invalid")
        fixture_path = tmp_path / "bad-hash.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="SHA-256"):
            ManualProvider(config)

    def test_rejects_prompt_id_mismatch(self, tmp_path):
        data = make_fixture(prompt_id="OTHER-PROMPT")
        fixture_path = tmp_path / "wrong-prompt.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="Prompt ID mismatch"):
            ManualProvider(config)

    def test_rejects_empty_prompt_id(self, tmp_path):
        data = make_fixture(prompt_id="   ")
        fixture_path = tmp_path / "empty-prompt-id.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="prompt_id"):
            ManualProvider(config)

    def test_rejects_responses_not_list(self, tmp_path):
        data = make_fixture(responses={"response": "invalid"})
        fixture_path = tmp_path / "bad-responses.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="responses must be a list"):
            ManualProvider(config)

    def test_rejects_empty_responses(self, tmp_path):
        data = make_fixture(responses=[])
        fixture_path = tmp_path / "empty-responses.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(
            InvalidFixtureError,
            match="non-empty list",
        ):
            ManualProvider(config)

    def test_rejects_response_not_object(self, tmp_path):
        data = make_fixture(responses=["not-an-object"])
        fixture_path = tmp_path / "bad-variant.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="JSON object"):
            ManualProvider(config)

    @pytest.mark.parametrize(
        "response",
        [
            make_response(response_id=123),
            make_response(response_id=""),
            make_response(response_id="   "),
        ],
    )
    def test_rejects_invalid_response_id(self, tmp_path, response):
        fixture_path = tmp_path / "bad-id.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="response_id"):
            ManualProvider(config)

    def test_rejects_empty_model_name(self, tmp_path):
        response = make_response(model_name="")

        fixture_path = tmp_path / "empty-model.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="model_name"):
            ManualProvider(config)

    def test_rejects_whitespace_only_response_text(self, tmp_path):
        response = make_response(response_text="   ")

        fixture_path = tmp_path / "empty-response.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="response_text"):
            ManualProvider(config)

    def test_rejects_created_at_without_timezone(self, tmp_path):
        response = make_response(created_at="2026-11-22T10:00:00")

        fixture_path = tmp_path / "no-timezone.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="include timezone"):
            ManualProvider(config)

    def test_rejects_invalid_created_at(self, tmp_path):
        response = make_response(created_at="not-a-date")

        fixture_path = tmp_path / "invalid-date.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="invalid created_at"):
            ManualProvider(config)

    def test_rejects_metadata_not_object(self, tmp_path):
        response = make_response(metadata=[1, 2, 3])

        fixture_path = tmp_path / "bad-metadata.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="metadata"):
            ManualProvider(config)

    @pytest.mark.parametrize(
        "field_name,value",
        [
            ("latency_ms", -1.0),
            ("latency_ms", True),
            ("latency_ms", float("nan")),
            ("latency_ms", float("inf")),
            ("estimated_cost", -1.0),
            ("estimated_cost", True),
            ("estimated_cost", float("nan")),
            ("estimated_cost", float("inf")),
        ],
    )
    def test_rejects_invalid_numeric_metrics(
        self,
        tmp_path,
        field_name,
        value,
    ):
        response = make_response(**{field_name: value})

        fixture_path = tmp_path / "bad-metric.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError):
            ManualProvider(config)

    def test_rejects_duplicate_response_ids(self, tmp_path):
        data = make_fixture(
            responses=[
                make_response(response_id="duplicate"),
                make_response(response_id="duplicate"),
            ]
        )

        fixture_path = tmp_path / "duplicates.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="unique"):
            ManualProvider(config)

    def test_wraps_invalid_metrics_model_error(self, tmp_path):
        response = make_response(input_tokens=-1)

        fixture_path = tmp_path / "invalid-model-metrics.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        with pytest.raises(InvalidFixtureError, match="Failed to load"):
            ManualProvider(config)


class TestManualProviderGenerateResponse:
    def test_returns_selected_response(self, valid_config):
        provider = ManualProvider(valid_config)

        response = provider.generate_response(PROMPT)

        assert response.response_text.startswith("def calculate_average")
        assert response.model_info.provider == "manual"
        assert response.metrics.latency_ms is None
        assert response.metrics.estimated_cost == 0.0

    def test_raises_hash_mismatch_for_different_prompt(self, valid_config):
        provider = ManualProvider(valid_config)

        with pytest.raises(PromptHashMismatchError):
            provider.generate_response("A different prompt")

    def test_validates_hash_on_each_call(self, valid_config):
        provider = ManualProvider(valid_config)

        first_response = provider.generate_response(PROMPT)

        assert first_response.response_text.startswith("def calculate_average")

        with pytest.raises(PromptHashMismatchError):
            provider.generate_response("A different prompt")

    def test_rejects_non_string_prompt(self, valid_config):
        provider = ManualProvider(valid_config)

        with pytest.raises(TypeError, match="prompt must be a string"):
            provider.generate_response(None)

    def test_raises_value_error_for_multiple_variants_without_response_id(
        self,
        tmp_path,
    ):
        data = make_fixture(
            responses=[
                make_response(response_id="variant-a"),
                make_response(response_id="variant-b"),
            ]
        )

        fixture_path = tmp_path / "multiple.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        provider = ManualProvider(config)

        with pytest.raises(AmbiguousResponseError, match="Multiple response variants"):
            provider.generate_response(PROMPT)

    def test_automatically_selects_single_variant(self, valid_config):
        config = ManualProviderConfig(
            fixture_path=valid_config.fixture_path,
            prompt_id=PROMPT_ID,
        )

        provider = ManualProvider(config)
        response = provider.generate_response(PROMPT)

        assert response.response_text.startswith("def calculate_average")

    def test_raises_response_not_found_for_unknown_id(self, fixture_file):
        config = ManualProviderConfig(
            fixture_path=fixture_file,
            prompt_id=PROMPT_ID,
            response_id="unknown",
        )

        provider = ManualProvider(config)

        with pytest.raises(ResponseNotFoundError, match="not found"):
            provider.generate_response(PROMPT)

    def test_returns_requested_variant(self, tmp_path):
        data = make_fixture(
            responses=[
                make_response(
                    response_id="variant-a",
                    response_text="response A",
                ),
                make_response(
                    response_id="variant-b",
                    response_text="response B",
                ),
            ]
        )

        fixture_path = tmp_path / "variants.json"
        fixture_path.write_text(json.dumps(data), encoding="utf-8")

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
            response_id="variant-b",
        )

        provider = ManualProvider(config)
        response = provider.generate_response(PROMPT)

        assert response.response_text == "response B"

    def test_metadata_is_immutable(self, valid_config):
        provider = ManualProvider(valid_config)
        response = provider.generate_response(PROMPT)

        with pytest.raises(TypeError):
            response.metadata["new_key"] = "new_value"

    def test_metadata_preserves_mapping_access(self, tmp_path):
        response_data = make_response(
            metadata={"source": "manual", "nested": {"key": "value"}}
        )

        fixture_path = tmp_path / "metadata.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response_data])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        provider = ManualProvider(config)
        response = provider.generate_response(PROMPT)

        assert response.metadata["source"] == "manual"
        assert response.metadata["nested"]["key"] == "value"

    def test_metadata_nested_containers_are_immutable(self, tmp_path):
        response_data = make_response(
            metadata={
                "nested": {"key": "value"},
                "items": [1, 2, 3],
            }
        )

        fixture_path = tmp_path / "nested-metadata.json"
        fixture_path.write_text(
            json.dumps(make_fixture(responses=[response_data])),
            encoding="utf-8",
        )

        config = ManualProviderConfig(
            fixture_path=fixture_path,
            prompt_id=PROMPT_ID,
        )

        provider = ManualProvider(config)
        response = provider.generate_response(PROMPT)

        with pytest.raises(TypeError):
            response.metadata["nested"]["new_key"] = "value"

        with pytest.raises(TypeError):
            response.metadata["items"][0] = 999
