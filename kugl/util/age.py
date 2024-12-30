import datetime as dt
import re
from typing import Dict

import funcy as fn


class Age(dt.timedelta):
    """
    A specialization of timedelta that handles age strings like "10s", "5m30s", "1h", "2d12h".
    Also, an Age is always non-negative.
    FIXME: Don't subclass timedelta, it's breaking the constructor contract.
    """

    AGE_RE = re.compile(r"(\d+[a-z])+")
    AGE_PART = re.compile(r"\d+[a-z]")

    def __new__(cls, *args, **kwargs):
        """
        Create a new Age object.  Parameters may be one of
        - a string like "10s", "5m30s", "1h", "2d12h"
        - an integer number of seconds
        - kwargs to pass to timedelta
        """
        if args:
            if kwargs:
                raise ValueError("Cannot specify both positional and keyword arguments")
            if len(args) == 3:
                # This is a call from deepcopy, bump it upstairs
                return super().__new__(cls, *args)
            if len(args) > 1:
                raise ValueError(f"Too many positional arguments: {args}")
            arg = args[0]
            if isinstance(arg, str):
                return super().__new__(cls, **Age.parse(arg))
            elif isinstance(arg, int) or isinstance(arg, float):
                return super().__new__(cls, seconds=abs(arg))
            else:
                raise ValueError(f"Invalid argument type: {arg}, {type(arg)}")
        elif not kwargs:
            raise ValueError("Must specify positional or keyword arguments")
        else:
            return super().__new__(cls, **kwargs)

    @classmethod
    def parse(cls, x: str) -> Dict[str, int]:
        """
        Convert a string like "10s", "5m30s", "1h", "2d12h" to Python timedelta dict, using suffixes to
        mean s = seconds, m = minutes, h = hours, d = days.
        """
        x = x.strip()
        if not x:
            raise ValueError("Empty argument")
        if fn.silent(int)(x) is not None:
            return {"seconds": int(x)}
        if not cls.AGE_RE.match(x):
            raise ValueError(f"Invalid age syntax: {x}")
        suffixes = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}

        def _parse(part):
            amount, unit = int(part[:-1]), part[-1]
            if unit not in suffixes:
                raise ValueError(f"Invalid suffix {unit}, must be one of [dhms]")
            return (suffixes[unit], amount)

        return dict(_parse(part) for part in cls.AGE_PART.findall(x))

    def render(self):
        """
        Render the age as a string like "10s", "5m30s", "1h", "2d12h".
        """
        days = self.days
        if days > 9:
            return f"{days}d"
        hours = self.seconds // 3600
        if days > 1:  # kubectl prints hours up to 47
            return f"{days}d{hours}h" if hours else f"{days}d"
        if days > 0 or hours > 9:
            return f"{days * 24 + hours}h"
        minutes = (self.seconds % 3600) // 60
        if hours > 2:  # kubectl prints minutes up to 179
            return f"{hours}h{minutes}m" if minutes else f"{hours}h"
        if hours > 0 or minutes > 9:
            return f"{hours * 60 + minutes}m"
        seconds = int(self.seconds % 60)
        if minutes > 0:
            return f"{minutes}m{seconds}s" if seconds else f"{minutes}m"
        return f"{seconds}s"

    @property
    def value(self) -> int:
        return int(self.total_seconds())


def parse_age(age: str) -> int:
    return Age(age).value


def to_age(seconds: int) -> str:
    return Age(seconds).render()

