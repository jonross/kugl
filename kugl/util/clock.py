"""
A wrapper on the system clock that can be replaced for unit testing.
"""

import time
from abc import abstractmethod
from typing import Optional

# For use with simulated clock
UNIT_TEST_TIMEBASE = 1733798942


class Clock:

    @abstractmethod
    def set(self, epoch: int):
        ...

    @abstractmethod
    def now(self) -> int:
        ...

    @abstractmethod
    def sleep(self, seconds: int):
        ...

    @property
    @abstractmethod
    def is_simulated(self) -> bool:
        ...


class RealClock(Clock):

    def set(self, epoch: int):
        pass

    def now(self) -> int:
        return int(time.time())

    def sleep(self, seconds: int):
        time.sleep(seconds)

    @property
    def is_simulated(self) -> bool:
        return False


CLOCK = RealClock()


def simulate_time():
    global CLOCK
    CLOCK = FakeClock()


class FakeClock(Clock):

    def __init__(self, epoch: Optional[int] = None):
        self._epoch = epoch or int(time.time())

    def set(self, epoch: int):
        self._epoch = epoch

    def now(self) -> int:
        return self._epoch

    def sleep(self, seconds: int):
        self._epoch += seconds

    @property
    def is_simulated(self) -> bool:
        return True