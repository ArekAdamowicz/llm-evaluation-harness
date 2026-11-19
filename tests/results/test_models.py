"""Unit tests for llm_eval.results.models."""

import json
import math
from collections import UserDict
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from llm_eval.results.models import (
    ErrorInfo,
    EvaluationRun,
    ExceptionInfo,
    Metrics,
    ModelInfo,
    TestResult,
    TestStatus,
    _deep_serialize,
    _freeze_value,
    _serialize_number,
    _thaw_value,
)

NAN = float("nan")
INF = float("inf")
NINF = float("-inf")


# --------------------------------------------------------------------------
# deep immutability
# --------------------------------------------------------------------------


class TestDeepImmutability:
    def test_dict_is_read_only(self):
        frozen = _freeze_value({"key": "value"})
        with pytest.raises(TypeError):
            frozen["key"] = "other"

    def test_list_becomes_tuple(self):
        frozen = _freeze_value([1, 2, 3])
        assert frozen == (1, 2, 3)
        assert isinstance(frozen, tuple)

    def test_dict_inside_tuple_is_frozen(self):
        """Regression: tuples used to be returned untouched."""
        frozen = _freeze_value({"values": ({"number": 10},)})
        with pytest.raises(TypeError):
            frozen["values"][0]["number"] = 20

    def test_dict_inside_list_inside_tuple(self):
        frozen = _freeze_value(({"a": [{"b": 1}]},))
        with pytest.raises(TypeError):
            frozen[0]["a"][0]["b"] = 2

    def test_mapping_proxy_input_is_refrozen_deeply(self):
        source = MappingProxyType({"inner": {"n": 1}})
        frozen = _freeze_value(source)
        with pytest.raises(TypeError):
            frozen["inner"]["n"] = 2

    def test_custom_mapping_is_supported(self):
        frozen = _freeze_value(UserDict({"inner": {"n": 1}}))
        with pytest.raises(TypeError):
            frozen["inner"]["n"] = 2

    def test_set_and_frozenset(self):
        assert _freeze_value({1, 2}) == frozenset({1, 2})
        assert _freeze_value(frozenset({1, 2})) == frozenset({1, 2})

    def test_source_mutation_does_not_leak_into_result(self):
        source = {"numbers": [1, 2, 3], "nested": {"n": 1}}
        result = TestResult(input_data=source)

        source["numbers"].append(4)
        source["nested"]["n"] = 999
        source["new"] = "x"

        assert result.input_data["numbers"] == (1, 2, 3)
        assert result.input_data["nested"]["n"] == 1
        assert "new" not in result.input_data

    def test_all_nested_fields_are_frozen(self):
        payload = {"deep": [{"n": 1}]}
        result = TestResult(
            input_data=payload,
            expected_output=payload,
            extracted_output=payload,
            actual_result=payload,
            metadata=payload,
        )
        for value in (
            result.input_data,
            result.expected_output,
            result.extracted_output,
            result.actual_result,
            result.metadata,
        ):
            with pytest.raises(TypeError):
                value["deep"][0]["n"] = 2

    def test_dataclass_is_frozen(self):
        result = TestResult()
        with pytest.raises(FrozenInstanceError):
            result.status = TestStatus.PASS

    def test_run_metadata_is_frozen(self):
        run = EvaluationRun(metadata={"config": {"temperature": 0.7}})
        with pytest.raises(TypeError):
            run.metadata["config"]["temperature"] = 1.0


# --------------------------------------------------------------------------
# freeze value allowlist
# --------------------------------------------------------------------------


class TestFreezeValueAllowlist:
    def test_none_accepted(self):
        assert _freeze_value(None) is None

    def test_bool_accepted(self):
        assert _freeze_value(True) is True
        assert _freeze_value(False) is False

    def test_int_accepted(self):
        assert _freeze_value(42) == 42

    def test_float_accepted(self):
        assert _freeze_value(3.14) == 3.14

    def test_str_accepted(self):
        assert _freeze_value("test") == "test"

    def test_mapping_accepted(self):
        frozen = _freeze_value({"key": "value"})
        assert isinstance(frozen, MappingProxyType)

    def test_list_accepted(self):
        frozen = _freeze_value([1, 2, 3])
        assert frozen == (1, 2, 3)

    def test_tuple_accepted(self):
        frozen = _freeze_value((1, 2, 3))
        assert frozen == (1, 2, 3)

    def test_set_accepted(self):
        frozen = _freeze_value({1, 2})
        assert frozen == frozenset({1, 2})

    def test_frozenset_accepted(self):
        frozen = _freeze_value(frozenset({1, 2}))
        assert frozen == frozenset({1, 2})

    def test_datetime_rejected(self):
        with pytest.raises(TypeError, match="Unsupported data type"):
            _freeze_value(datetime.now())

    def test_decimal_rejected(self):
        from decimal import Decimal
        with pytest.raises(TypeError, match="Unsupported data type"):
            _freeze_value(Decimal("1.5"))

    def test_custom_class_rejected(self):
        class Custom:
            pass
        with pytest.raises(TypeError, match="Unsupported data type"):
            _freeze_value(Custom())

    def test_bytes_rejected(self):
        with pytest.raises(TypeError, match="Unsupported data type"):
            _freeze_value(b"data")

    def test_complex_rejected(self):
        with pytest.raises(TypeError, match="Unsupported data type"):
            _freeze_value(1 + 2j)


class TestMappingKeysValidation:
    def test_string_keys_accepted(self):
        frozen = _freeze_value({"key1": 1, "key2": 2})
        assert frozen["key1"] == 1

    def test_int_key_rejected(self):
        with pytest.raises(TypeError, match="Mapping keys must be strings"):
            _freeze_value({1: "value"})

    def test_mixed_keys_rejected(self):
        with pytest.raises(TypeError, match="Mapping keys must be strings"):
            _freeze_value({"valid": 1, 2: "invalid"})

    def test_none_key_rejected(self):
        with pytest.raises(TypeError, match="Mapping keys must be strings"):
            _freeze_value({None: "value"})

    def test_nested_mapping_keys_validated(self):
        with pytest.raises(TypeError, match="Mapping keys must be strings"):
            _freeze_value({"outer": {1: "inner"}})

    def test_mapping_in_list_keys_validated(self):
        with pytest.raises(TypeError, match="Mapping keys must be strings"):
            _freeze_value([{"valid": 1}, {2: "invalid"}])


# --------------------------------------------------------------------------
# serialization
# --------------------------------------------------------------------------


class TestSerialization:
    @pytest.mark.parametrize(
        "value, tag",
        [(NAN, "nan"), (INF, "inf"), (NINF, "-inf")],
    )
    def test_special_floats_are_tagged(self, value, tag):
        assert _deep_serialize(value) == {"$type": "float", "value": tag}

    def test_finite_float_untouched(self):
        assert _deep_serialize(3.14) == 3.14

    @pytest.mark.parametrize(
        "value, expected",
        [(None, None), (5, 5), (1.5, 1.5)],
    )
    def test_serialize_number_scalars(self, value, expected):
        assert _serialize_number(value) == expected

    def test_serialize_number_tags_nan(self):
        assert _serialize_number(NAN) == {"$type": "float", "value": "nan"}

    def test_nested_special_floats(self):
        data = _freeze_value({"values": [1.0, NAN, INF], "n": {"v": NINF}})
        result = _deep_serialize(data)
        assert result["values"][1] == {"$type": "float", "value": "nan"}
        assert result["values"][2] == {"$type": "float", "value": "inf"}
        assert result["n"]["v"] == {"$type": "float", "value": "-inf"}

    def test_full_result_is_strict_json(self):
        result = TestResult(
            test_case_id="CG-001-F10",
            input_data={"numbers": [1.0, NAN]},
            expected_output={"type": "exception", "message": "NaN"},
            metadata={"debug": {"seen": INF}},
            actual_result=NINF,
            score=0.5,
            status=TestStatus.FAIL,
            metrics=Metrics(latency_ms=12.5, input_tokens=10),
            model_info=ModelInfo(provider="local", name="reference"),
        )
        payload = json.dumps(result.to_dict(), allow_nan=False)
        assert "Infinity" not in payload

    def test_full_run_is_strict_json(self):
        run = EvaluationRun(
            dataset_id="CG-001",
            metadata={"limits": {"max": INF}},
            model_info=ModelInfo(provider="local", name="reference"),
        )
        payload = json.dumps(run.to_dict(), allow_nan=False)
        assert "Infinity" not in payload

    def test_status_serialized_as_plain_string(self):
        payload = TestResult(status=TestStatus.PASS).to_dict()
        assert payload["status"] == "PASS"
        assert type(payload["status"]) is str

    def test_thaw_roundtrip_for_json_safe_data(self):
        original = {"numbers": [1, 2, 3], "nested": {"key": "value"}}
        restored = _thaw_value(_deep_serialize(_freeze_value(original)))
        assert restored == original

    def test_thaw_is_lossy_for_tuples_documented(self):
        """Known limitation v1.0: list and tuple are indistinguishable
        after freezing. Replay must use the dataset, not TestResult.

        This is documented in the module docstring and _freeze_value().
        """
        from_list = _deep_serialize(_freeze_value([1, 2]))
        from_tuple = _deep_serialize(_freeze_value((1, 2)))
        assert from_list == from_tuple == [1, 2]


# --------------------------------------------------------------------------
# validation: metrics
# --------------------------------------------------------------------------


class TestMetricsValidation:
    @pytest.mark.parametrize("value", [NAN, INF, NINF, 10**400])
    @pytest.mark.parametrize("field", ["latency_ms", "estimated_cost"])
    def test_non_finite_rejected(self, value, field):
        with pytest.raises(ValueError, match=f"{field} must be finite"):
            Metrics(**{field: value})

    @pytest.mark.parametrize("value", [True, False, "10", [], {}])
    def test_non_numbers_rejected(self, value):
        with pytest.raises(TypeError, match="latency_ms must be a number"):
            Metrics(latency_ms=value)

    @pytest.mark.parametrize("value", [-1, -0.5])
    def test_negative_rejected(self, value):
        with pytest.raises(ValueError, match="must be non-negative"):
            Metrics(latency_ms=value)

    @pytest.mark.parametrize(
        "field", ["input_tokens", "output_tokens", "total_tokens"]
    )
    @pytest.mark.parametrize("value", [True, 1.5, "10"])
    def test_tokens_must_be_int(self, field, value):
        with pytest.raises(TypeError, match=f"{field} must be an integer"):
            Metrics(**{field: value})

    def test_negative_tokens_rejected(self):
        with pytest.raises(ValueError, match="input_tokens must be non-negative"):
            Metrics(input_tokens=-1)

    def test_all_none_is_valid(self):
        assert Metrics().to_dict()["latency_ms"] is None

    def test_zero_is_valid(self):
        assert Metrics(latency_ms=0, input_tokens=0).latency_ms == 0


# --------------------------------------------------------------------------
# validation: model info
# --------------------------------------------------------------------------


class TestModelInfoValidation:
    def test_temperature_must_be_non_negative(self):
        with pytest.raises(ValueError, match="temperature must be non-negative"):
            ModelInfo(provider="p", name="m", temperature=-0.1)

    @pytest.mark.parametrize("value", [NAN, INF])
    def test_temperature_non_finite(self, value):
        with pytest.raises(ValueError, match="temperature must be finite"):
            ModelInfo(provider="p", name="m", temperature=value)

    def test_temperature_bool_rejected(self):
        with pytest.raises(TypeError, match="temperature must be a number"):
            ModelInfo(provider="p", name="m", temperature=True)

    def test_temperature_large_value_accepted(self):
        """No upper bound - provider-specific limits checked later."""
        model = ModelInfo(provider="p", name="m", temperature=100.0)
        assert model.temperature == 100.0

    @pytest.mark.parametrize("value", [-0.1, 1.1])
    def test_top_p_range(self, value):
        with pytest.raises(ValueError, match="top_p must be between"):
            ModelInfo(provider="p", name="m", top_p=value)

    @pytest.mark.parametrize("value", ["", "   ", None])
    def test_provider_must_be_non_empty(self, value):
        with pytest.raises(ValueError, match="provider must be a non-empty"):
            ModelInfo(provider=value, name="m")

    def test_seed_must_be_int(self):
        with pytest.raises(TypeError, match="seed must be an integer"):
            ModelInfo(provider="p", name="m", seed=True)


# --------------------------------------------------------------------------
# validation: types and tags
# --------------------------------------------------------------------------


class TestTypeValidation:
    def test_status_must_be_enum(self):
        with pytest.raises(TypeError, match="status must be a TestStatus"):
            TestResult(status="PASS")

    def test_metrics_must_be_metrics(self):
        with pytest.raises(TypeError, match="metrics must be a Metrics"):
            TestResult(metrics={"latency_ms": 1})

    def test_error_must_be_error_info(self):
        with pytest.raises(TypeError, match="error must be a ErrorInfo"):
            TestResult(status=TestStatus.ERROR, error={"error_type": "X"})

    def test_actual_exception_must_be_exception_info(self):
        with pytest.raises(
            TypeError, match="actual_exception must be a ExceptionInfo"
        ):
            TestResult(status=TestStatus.FAIL, actual_exception="ValueError")

    def test_model_info_type_checked(self):
        with pytest.raises(TypeError, match="model_info must be a ModelInfo"):
            TestResult(model_info={"provider": "p"})

    def test_naive_timestamp_rejected(self):
        with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
            TestResult(timestamp=datetime.now())

    def test_timestamp_must_be_datetime(self):
        with pytest.raises(TypeError, match="timestamp must be a datetime"):
            TestResult(timestamp="2026-11-20T10:00:00Z")

    def test_default_timestamp_is_utc_aware(self):
        result = TestResult()
        assert result.timestamp.tzinfo is not None
        assert result.timestamp.utcoffset() == timedelta(0)

    @pytest.mark.parametrize("score", [NAN, INF])
    def test_non_finite_score_rejected(self, score):
        with pytest.raises(ValueError, match="score must be finite"):
            TestResult(score=score)

    def test_bool_score_rejected(self):
        with pytest.raises(TypeError, match="score must be a number"):
            TestResult(score=True)


class TestTagsNormalization:
    def test_list_normalized_to_tuple(self):
        assert TestResult(tags=["a", "b"]).tags == ("a", "b")

    def test_generator_normalized(self):
        assert TestResult(tags=(t for t in ["a"])).tags == ("a",)

    def test_non_string_element_rejected(self):
        with pytest.raises(TypeError, match="tags must contain only strings"):
            TestResult(tags=["a", 1])

    def test_bare_string_rejected(self):
        with pytest.raises(TypeError, match="not a string"):
            TestResult(tags="smoke")

    def test_none_rejected(self):
        with pytest.raises(TypeError, match="tags must be an iterable"):
            TestResult(tags=None)

    def test_run_tags_normalized(self):
        assert EvaluationRun(tags=["a"]).tags == ("a",)
        with pytest.raises(TypeError, match="tags must contain only strings"):
            EvaluationRun(tags=[1])


# --------------------------------------------------------------------------
# status semantics
# --------------------------------------------------------------------------


class TestStatusSemantics:
    def test_pass_with_expected_exception(self):
        """CG-001-F05: expected ValueError is a PASS, not an ERROR."""
        result = TestResult(
            test_case_id="CG-001-F05",
            status=TestStatus.PASS,
            actual_result=None,
            actual_exception=ExceptionInfo(
                exception_type="ValueError",
                message="numbers must not be empty",
            ),
        )
        assert result.status is TestStatus.PASS
        assert result.error is None
        assert result.actual_exception.exception_type == "ValueError"

    def test_fail_with_unexpected_exception(self):
        result = TestResult(
            status=TestStatus.FAIL,
            actual_exception=ExceptionInfo("TypeError", "boom"),
        )
        assert result.error is None

    def test_error_requires_error_field(self):
        with pytest.raises(ValueError, match="ERROR status requires error"):
            TestResult(status=TestStatus.ERROR)

    def test_error_rejects_actual_exception(self):
        with pytest.raises(
            ValueError, match="ERROR status must not contain actual_exception"
        ):
            TestResult(
                status=TestStatus.ERROR,
                error=ErrorInfo("APIError", "429"),
                actual_exception=ExceptionInfo("ValueError", "boom"),
            )

    @pytest.mark.parametrize(
        "status", [TestStatus.PASS, TestStatus.FAIL, TestStatus.SKIPPED]
    )
    def test_error_field_only_for_error_status(self, status):
        with pytest.raises(ValueError, match="error field can only be set"):
            TestResult(status=status, error=ErrorInfo("APIError", "429"))

    @pytest.mark.parametrize(
        "status", [TestStatus.SKIPPED, TestStatus.ERROR]
    )
    def test_actual_exception_only_for_pass_or_fail(self, status):
        kwargs = {}
        if status is TestStatus.ERROR:
            kwargs["error"] = ErrorInfo("APIError", "429")

        with pytest.raises(ValueError, match="actual_exception"):
            TestResult(
                status=status,
                actual_exception=ExceptionInfo("ValueError", "boom"),
                **kwargs,
            )

    def test_skipped_is_clean_default(self):
        result = TestResult()
        assert result.status is TestStatus.SKIPPED
        assert result.error is None
        assert result.actual_exception is None


# --------------------------------------------------------------------------
# identity and lifecycle
# --------------------------------------------------------------------------


class TestIdentityAndLifecycle:
    def test_ids_are_unique(self):
        assert TestResult().result_id != TestResult().result_id
        assert EvaluationRun().run_id != EvaluationRun().run_id

    def test_finished_at_via_replace(self):
        run = EvaluationRun(dataset_id="CG-001")
        assert run.finished_at is None

        finished = replace(run, finished_at=run.started_at + timedelta(seconds=5))

        assert run.finished_at is None
        assert finished.run_id == run.run_id
        assert finished.finished_at is not None

    def test_naive_finished_at_rejected(self):
        with pytest.raises(ValueError, match="finished_at must be timezone-aware"):
            EvaluationRun(finished_at=datetime.now())

    def test_non_utc_timezone_accepted(self):
        tz = timezone(timedelta(hours=1))
        run = EvaluationRun(started_at=datetime.now(tz))
        assert run.started_at.utcoffset() == timedelta(hours=1)

    def test_large_integers_survive_serialization(self):
        big = 10**400
        result = TestResult(input_data={"numbers": [big, -big, 1]})
        payload = json.dumps(result.to_dict(), allow_nan=False)
        assert str(big) in payload

    def test_nan_equality_helper_sanity(self):
        assert math.isnan(NAN)
