"""Tests for provider exceptions."""

import pytest

from llm_eval.providers.exceptions import (
    ProviderConnectionError,
    ProviderError,
    ProviderHTTPError,
    ProviderTimeoutError,
)


class TestProviderExceptionsHierarchy:
    def test_http_error_inherits_provider_error(self):
        assert issubclass(ProviderHTTPError, ProviderError)

    def test_connection_error_inherits_provider_error(self):
        assert issubclass(ProviderConnectionError, ProviderError)

    def test_timeout_error_inherits_provider_error(self):
        assert issubclass(ProviderTimeoutError, ProviderError)


class TestProviderHTTPError:
    def test_stores_status_code(self):
        error = ProviderHTTPError("Not found", status_code=404)

        assert error.status_code == 404
        assert str(error) == "Not found"

    def test_status_code_is_required(self):
        with pytest.raises(TypeError):
            ProviderHTTPError("Not found")
