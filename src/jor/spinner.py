"""Threaded braille-dot spinner for visual feedback."""

from __future__ import annotations

import sys
import threading
from typing import IO

BRAILLE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class Spinner:
    """A context-manager spinner that runs in a daemon thread."""

    def __init__(self, message: str, stream: IO[str] | None = None, interval: float = 0.08) -> None:
        self._message = message
        self._stream = stream or sys.stderr
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Spinner:
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
        # Clear the spinner line
        self._stream.write("\r" + " " * (len(self._message) + 4) + "\r")
        self._stream.flush()

    def _spin(self) -> None:
        i = 0
        while not self._stop.is_set():
            frame = BRAILLE[i % len(BRAILLE)]
            self._stream.write(f"\r{frame} {self._message}")
            self._stream.flush()
            i += 1
            self._stop.wait(self._interval)
