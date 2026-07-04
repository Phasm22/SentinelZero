"""Unit tests for notifications service."""
import os
from unittest.mock import MagicMock, patch

import pytest

from src.models import Alert
from src.services.notifications import send_pushover_alert


def test_send_pushover_alert_skips_without_credentials(app):
    with app.app_context():
        with patch.dict(os.environ, {}, clear=True):
            send_pushover_alert("test message", level="info")
        assert Alert.query.count() == 0


def test_send_pushover_alert_posts_and_logs(app):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_socket = MagicMock()

    with app.app_context():
        with patch.dict(
            os.environ,
            {"PUSHOVER_API_TOKEN": "token", "PUSHOVER_USER_KEY": "user"},
        ):
            with patch("src.services.notifications.requests.post", return_value=mock_response) as post:
                send_pushover_alert("hello", level="danger", scan_id=None, socketio=mock_socket)

        post.assert_called_once()
        assert Alert.query.count() == 1
        alert = Alert.query.first()
        assert alert.message == "hello"
        assert alert.severity == "danger"
        mock_socket.emit.assert_called()
