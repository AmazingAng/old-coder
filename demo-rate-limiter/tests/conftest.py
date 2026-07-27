from collections.abc import Iterator

import pytest


class FakeClock:
    """Injected clock: the mock boundary. No real time in tests."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Iterator[FakeClock]:
    yield FakeClock()
