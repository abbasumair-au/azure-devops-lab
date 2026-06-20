import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
from retry import retry
from azure_session import AzureSession, AzureConnectionError


class TestRetryDecorator:
    def test_success_on_first_try(self):
        mock_fn = MagicMock(return_value="ok")

        @retry(times=3, delay=0)
        def fn():
            return mock_fn()

        assert fn() == "ok"
        assert mock_fn.call_count == 1

    def test_retry_then_success(self):
        mock_fn = MagicMock(side_effect=[ValueError("fail"), ValueError("fail"), "ok"])

        @retry(times=3, delay=0)
        def fn():
            return mock_fn()

        assert fn() == "ok"
        assert mock_fn.call_count == 3

    def test_raises_after_max_retries(self):
        mock_fn = MagicMock(side_effect=ValueError("always fails"))

        @retry(times=3, delay=0)
        def fn():
            return mock_fn()

        with pytest.raises(ValueError, match="always fails"):
            fn()
        assert mock_fn.call_count == 3

    def test_only_catches_specified_exceptions(self):
        mock_fn = MagicMock(side_effect=TypeError("wrong type"))

        @retry(times=3, delay=0, exceptions=(ValueError,))
        def fn():
            return mock_fn()

        with pytest.raises(TypeError):
            fn()
        assert mock_fn.call_count == 1

    @pytest.mark.parametrize("times,expected", [(1, 1), (2, 2), (5, 5)])
    def test_retry_count(self, times, expected):
        mock_fn = MagicMock(side_effect=ValueError("fail"))

        @retry(times=times, delay=0)
        def fn():
            return mock_fn()

        with pytest.raises(ValueError):
            fn()
        assert mock_fn.call_count == expected

    def test_preserves_function_name(self):
        @retry(times=3, delay=0)
        def my_special_function():
            pass

        assert my_special_function.__name__ == "my_special_function"


class TestAzureSession:
    def test_connects_in_context(self):
        with AzureSession(subscription_id="sub-123") as session:
            assert session.is_connected is True

    def test_disconnects_after_exit(self):
        with AzureSession(subscription_id="sub-123") as session:
            pass
        assert session.is_connected is False

    def test_empty_subscription_raises(self):
        with pytest.raises(AzureConnectionError):
            with AzureSession(subscription_id="") as session:
                pass

    def test_get_resources_in_session(self):
        with AzureSession(subscription_id="sub-123") as session:
            resources = session.get_resources()
            assert isinstance(resources, list)
            assert len(resources) > 0

    def test_get_resources_outside_session_raises(self):
        session = AzureSession(subscription_id="sub-123")
        with pytest.raises(RuntimeError):
            session.get_resources()

    def test_exception_propagates_and_session_closes(self):
        with pytest.raises(ZeroDivisionError):
            with AzureSession(subscription_id="sub-123") as session:
                raise ZeroDivisionError("boom")
        assert session.is_connected is False
