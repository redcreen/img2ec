import sys
from unittest.mock import patch

from img2ec.infra.reveal import reveal_in_finder


@patch("img2ec.infra.reveal.subprocess.run")
def test_reveal_macos(mock_run, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    reveal_in_finder("/tmp/foo")
    mock_run.assert_called_once_with(["open", "-R", "/tmp/foo"], check=False)


@patch("img2ec.infra.reveal.subprocess.run")
def test_reveal_windows(mock_run, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    reveal_in_finder("C:\\foo")
    mock_run.assert_called_once_with(["explorer.exe", "/select,", "C:\\foo"], check=False)


@patch("img2ec.infra.reveal.subprocess.run")
def test_reveal_linux(mock_run, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    reveal_in_finder("/tmp/foo")
    mock_run.assert_called_once_with(["xdg-open", "/tmp/foo"], check=False)
