"""Ensure client-controlled GHT test cookies are never accepted in production."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.middleware import ght_context


def _request(*, testing: bool, cookies: dict[str, str]):
    return SimpleNamespace(
        session={},
        cookies=cookies,
        app=SimpleNamespace(
            state=SimpleNamespace(settings=SimpleNamespace(testing=testing)),
        ),
    )


@pytest.mark.asyncio
async def test_unsigned_test_cookie_is_ignored_outside_test_mode(monkeypatch):
    request = _request(
        testing=False,
        cookies={"medbridge_test_data": '{"ght_id": 42}'},
    )
    monkeypatch.setattr(
        ght_context,
        "session_factory",
        lambda: pytest.fail("Database access must not occur for an unsigned cookie"),
    )

    assert await ght_context.get_active_ght_context(request) is None
    assert request.session == {}


@pytest.mark.asyncio
async def test_unsigned_test_cookie_remains_available_in_test_mode(monkeypatch):
    context = Mock()
    session = Mock()
    session.get.return_value = context
    monkeypatch.setattr(ght_context, "session_factory", lambda: nullcontext(session))
    request = _request(
        testing=True,
        cookies={"medbridge_test_data": '{"ght_id": 42, "ej_id": 7}'},
    )

    assert await ght_context.get_active_ght_context(request) is context
    assert request.session["ght_context_id"] == 42
    assert request.session["ej_context_id"] == 7


@pytest.mark.asyncio
async def test_signed_context_uses_the_application_session_factory(monkeypatch):
    context = Mock()
    session = Mock()
    session.get.return_value = context
    request = _request(testing=False, cookies={})
    request.session["ght_context_id"] = 42
    request.app.state.session_factory = lambda: nullcontext(session)
    monkeypatch.setattr(
        ght_context,
        "session_factory",
        lambda: pytest.fail("Global session factory must not be used"),
    )

    assert await ght_context.get_active_ght_context(request) is context
    session.get.assert_called_once_with(ght_context.GHTContext, 42)
