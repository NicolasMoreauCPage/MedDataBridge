import logging

from app.routers.interop import mllp_status


def test_mllp_status_logs_a_socket_unavailable_during_reload(caplog):
    class Manager:
        servers = {42: object()}

        @staticmethod
        def running_ids():
            return [42]

    request = type("Request", (), {"app": type("App", (), {"state": type("State", (), {"mllp_manager": Manager()})()})()})()

    with caplog.at_level(logging.DEBUG):
        result = mllp_status(request)

    assert result == {"running_ids": [42], "bindings": []}
    assert "MLLP binding unavailable endpoint_id=42" in caplog.text
