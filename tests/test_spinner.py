"""Tests for the braille-dot spinner."""

import io
import time

from jor.spinner import Spinner


def test_spinner_context_manager():
    """Spinner starts and stops cleanly as a context manager."""
    output = io.StringIO()
    with Spinner("Working...", stream=output):
        time.sleep(0.15)  # let at least one frame render

    text = output.getvalue()
    assert "Working..." in text


def test_spinner_clears_on_exit():
    """Spinner clears its line on exit."""
    output = io.StringIO()
    with Spinner("Working...", stream=output):
        time.sleep(0.05)

    # Last write should contain \r to clear the line
    text = output.getvalue()
    assert "\r" in text
