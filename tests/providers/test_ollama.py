"""Tests for Ollama provider configuration."""

import json
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, patch

import pytest

from llm_eval.providers.ollama import OllamaProvider, OllamaProviderConfig


class TestOllamaProviderConfigDefaults:
    def test_uses_expected_default_values(self):
        config = OllamaProviderConfig(model="llama3.2:3b")

        assert config.model == "llama3.2:3b"
        assert config.base_url == "http://localhost:11434"
        assert config.timeout_seconds == 300.0
        assert config.temperature is None
        assert config.top_p is None
        assert config.seed is None

    def test_is_immutable(self):
        config = OllamaProviderConfig(model="llama3.2:3b")

        with pytest.raises(FrozenInstanceError):
            config.model = "another-model"

    def test_accepts_custom_values(self):
        config = OllamaProviderConfig(
            model="mistral:7b",
            base_url="http://127.0.0.1:11434/",
            timeout_seconds=120.0,
            temperature=0.2,
            top_p=0.9,
            seed=42,
        )

        assert config.model == "mistral:7b"
        assert config.base_url == "http://127.0.0.1:11434"
        assert config.timeout_seconds == 120.0
        assert config.temperature == 0.2
        assert config.top_p == 0.9
        assert config.seed == 42


class TestOllamaProviderConfigModel:
    @pytest.mark.parametrize("model", ["", " ", "   "])
    def test_rejects_empty_model_name(self, model):
        with pytest.raises(ValueError, match="model"):
            OllamaProviderConfig(model=model)

    @pytest.mark.parametrize(
        "model",
        [
            "mistral 7b",
            "mistral\t7b",
            "mistral\n7b",
            " mistral7b",
            "mistral7b ",
        ],
    )
    def test_rejects_model_with_whitespace(self, model):
        with pytest.raises(ValueError, match="model"):
            OllamaProviderConfig(model=model)

    @pytest.mark.parametrize("model", [None, 123, True, [], {}])
    def test_rejects_model_with_invalid_type(self, model):
        with pytest.raises(TypeError, match="model"):
            OllamaProviderConfig(model=model)


class TestOllamaProviderConfigBaseUrl:
    @pytest.mark.parametrize(
        "base_url",
        [
            "ftp://localhost:11434",
            "https://",
            "http://",
            "localhost:11434",
            "",
            " ",
            "http://example.com:invalid",
            "http://example.com:99999",
            "http://example.com:0",
            "http://exa mple.com",
            "http://[invalid-ipv6",
            "http://user:pass@localhost:11434",
            "http://localhost:11434?foo=bar",
            "http://localhost:11434#fragment",
            "http://localhost:11434?",
            "http://localhost:11434#",
        ],
    )
    def test_rejects_invalid_base_url(self, base_url):
        with pytest.raises(ValueError, match="base_url"):
            OllamaProviderConfig(
                model="llama3.2:3b",
                base_url=base_url,
            )

    @pytest.mark.parametrize("base_url", [None, 123, True, [], {}])
    def test_rejects_base_url_with_invalid_type(self, base_url):
        with pytest.raises(TypeError, match="base_url"):
            OllamaProviderConfig(
                model="llama3.2:3b",
                base_url=base_url,
            )

    @pytest.mark.parametrize(
        ("base_url", "expected"),
        [
            ("http://localhost:11434/", "http://localhost:11434"),
            ("http://localhost:11434///", "http://localhost:11434"),
            ("https://example.com", "https://example.com"),
        ],
    )
    def test_normalizes_trailing_slashes(self, base_url, expected):
        config = OllamaProviderConfig(
            model="llama3.2:3b",
            base_url=base_url,
        )

        assert config.base_url == expected


class TestOllamaProviderConfigTimeout:
    @pytest.mark.parametrize(
        "timeout",
        [
            0,
            -1,
            0.0,
            -0.1,
            float("nan"),
            float("inf"),
            float("-inf"),
            10**1000,
        ],
    )
    def test_rejects_invalid_timeout_values(self, timeout):
        with pytest.raises(ValueError, match="timeout_seconds"):
            OllamaProviderConfig(
                model="llama3.2:3b",
                timeout_seconds=timeout,
            )

    @pytest.mark.parametrize("timeout", [True, False, "300", None])
    def test_rejects_timeout_with_invalid_type(self, timeout):
        with pytest.raises(TypeError, match="timeout_seconds"):
            OllamaProviderConfig(
                model="llama3.2:3b",
                timeout_seconds=timeout,
            )

    @pytest.mark.parametrize("timeout", [0.1, 1, 30.5, 600])
    def test_accepts_positive_finite_timeout(self, timeout):
        config = OllamaProviderConfig(
            model="llama3.2:3b",
            timeout_seconds=timeout,
        )

        assert config.timeout_seconds == timeout


class TestOllamaProviderConfigTemperature:
    @pytest.mark.parametrize(
        "temperature",
        [
            -0.1,
            float("nan"),
            float("inf"),
            float("-inf"),
        ],
    )
    def test_rejects_invalid_temperature_values(self, temperature):
        with pytest.raises(ValueError, match="temperature"):
            OllamaProviderConfig(
                model="llama3.2:3b",
                temperature=temperature,
            )

    @pytest.mark.parametrize("temperature", [True, False, "0.2", []])
    def test_rejects_temperature_with_invalid_type(self, temperature):
        with pytest.raises(TypeError, match="temperature"):
            OllamaProviderConfig(
                model="llama3.2:3b",
                temperature=temperature,
            )

    @pytest.mark.parametrize("temperature", [0, 0.0, 0.2, 0.7, 1.5])
    def test_accepts_non_negative_finite_temperature(self, temperature):
        config = OllamaProviderConfig(
            model="llama3.2:3b",
            temperature=temperature,
        )

        assert config.temperature == temperature

    def test_accepts_none_temperature(self):
        config = OllamaProviderConfig(
            model="llama3.2:3b",
            temperature=None,
        )

        assert config.temperature is None


class TestOllamaProviderConfigTopP:
    @pytest.mark.parametrize(
        "top_p",
        [
            -0.1,
            1.1,
            float("nan"),
            float("inf"),
            float("-inf"),
        ],
    )
    def test_rejects_invalid_top_p_values(self, top_p):
        with pytest.raises(ValueError, match="top_p"):
            OllamaProviderConfig(
                model="llama3.2:3b",
                top_p=top_p,
            )

    @pytest.mark.parametrize("top_p", [True, False, "0.9", []])
    def test_rejects_top_p_with_invalid_type(self, top_p):
        with pytest.raises(TypeError, match="top_p"):
            OllamaProviderConfig(
                model="llama3.2:3b",
                top_p=top_p,
            )

    @pytest.mark.parametrize("top_p", [0, 0.0, 0.5, 0.9, 1, 1.0])
    def test_accepts_top_p_in_valid_range(self, top_p):
        config = OllamaProviderConfig(
            model="llama3.2:3b",
            top_p=top_p,
        )

        assert config.top_p == top_p

    def test_accepts_none_top_p(self):
        config = OllamaProviderConfig(
            model="llama3.2:3b",
            top_p=None,
        )

        assert config.top_p is None


class TestOllamaProviderConfigSeed:
    @pytest.mark.parametrize("seed", [True, False, 1.5, "42"])
    def test_rejects_seed_with_invalid_type(self, seed):
        with pytest.raises(TypeError, match="seed"):
            OllamaProviderConfig(
                model="llama3.2:3b",
                seed=seed,
            )

    @pytest.mark.parametrize("seed", [0, 1, 42, -1, -100])
    def test_accepts_integer_seed(self, seed):
        config = OllamaProviderConfig(
            model="llama3.2:3b",
            seed=seed,
        )

        assert config.seed == seed

    def test_accepts_none_seed(self):
        config = OllamaProviderConfig(
            model="llama3.2:3b",
            seed=None,
        )

        assert config.seed is None


MOCK_OLLAMA_SUCCESS_RESPONSE = {
    "model": "llama3.2:3b",
    "created_at": "2023-11-26T10:00:00Z",
    "response": "Mocked response text",
    "done": True,
    "prompt_eval_count": 10,
    "eval_count": 5,
}


def _create_mock_urlopen_response(response_data=None):
    """Create a mock context-manager response from urllib."""

    if response_data is None:
        response_data = MOCK_OLLAMA_SUCCESS_RESPONSE

    response = MagicMock()
    response.read.return_value = json.dumps(response_data).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = None

    return response


class TestOllamaProviderRequestBuilding:
    @patch("urllib.request.urlopen")
    def test_sends_minimal_generate_request(self, mock_urlopen):
        mock_urlopen.return_value = _create_mock_urlopen_response()

        config = OllamaProviderConfig(model="llama3.2:3b")
        provider = OllamaProvider(config)

        with pytest.raises(NotImplementedError):
            provider.generate_response("What is Python?")

        mock_urlopen.assert_called_once()

        request = mock_urlopen.call_args.args[0]
        timeout = mock_urlopen.call_args.kwargs["timeout"]

        assert request.full_url == "http://localhost:11434/api/generate"
        assert request.get_method() == "POST"
        assert request.get_header("Content-type") == "application/json"
        assert timeout == 300.0

        payload = json.loads(request.data.decode("utf-8"))

        assert payload == {
            "model": "llama3.2:3b",
            "prompt": "What is Python?",
            "stream": False,
        }

    @patch("urllib.request.urlopen")
    def test_includes_all_configured_options(self, mock_urlopen):
        mock_urlopen.return_value = _create_mock_urlopen_response()

        config = OllamaProviderConfig(
            model="llama3.2:3b",
            temperature=0.7,
            top_p=0.9,
            seed=42,
        )
        provider = OllamaProvider(config)

        with pytest.raises(NotImplementedError):
            provider.generate_response("Explain Python.")

        mock_urlopen.assert_called_once()

        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        assert payload == {
            "model": "llama3.2:3b",
            "prompt": "Explain Python.",
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "seed": 42,
            },
        }

    @patch("urllib.request.urlopen")
    def test_includes_only_configured_options(self, mock_urlopen):
        mock_urlopen.return_value = _create_mock_urlopen_response()

        config = OllamaProviderConfig(
            model="llama3.2:3b",
            temperature=0.2,
        )
        provider = OllamaProvider(config)

        with pytest.raises(NotImplementedError):
            provider.generate_response("Explain Python.")

        mock_urlopen.assert_called_once()

        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        assert payload == {
            "model": "llama3.2:3b",
            "prompt": "Explain Python.",
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }
