"""
More assorted tests, should these be combined with test_misc.py?
"""

import jmespath
import pytest

from kugel.util import Age
from kugel.impl.utils import dprint, debug


@pytest.mark.parametrize("input_args,input_kwargs,expected", [
    ([], {}, ValueError("Must specify positional or keyword arguments")),
    ([1], {"x":1}, ValueError("Cannot specify both positional and keyword arguments")),
    ([1, 1], {}, ValueError("Too many positional arguments")),
    ([""], {}, ValueError("Empty argument")),
    (["xxx"], {}, ValueError("Invalid age syntax: xxx")),
    (["1x"], {}, ValueError("Invalid suffix x, must be one of")),
    ([], {"seconds": 10}, "10s"),
    ([], {"minutes": 5}, "5m"),
    ([], {"hours": 3}, "3h"),
    ([], {"days": 2}, "2d"),
    ([2], {}, "2s"),
    ([2.5], {}, "2s"),
    ([-2], {}, "2s"),
    (["10d9h"], {}, "10d"),
    (["9d9h"], {}, "9d9h"),
    (["9d"], {}, "9d"),
    (["50h"], {}, "2d2h"),
    (["1d9h"], {}, "33h"),
    (["10h40m"], {}, "10h"),
    (["9h40m"], {}, "9h40m"),
    (["9h40m20s"], {}, "9h40m"),
    (["9h20s"], {}, "9h"),
    (["3h"], {}, "3h"),
    (["2h50m"], {}, "170m"),
    (["1h"], {}, "60m"),
    (["1h20s"], {}, "60m"),
    (["80s"], {}, "1m20s"),
    (["10m20s"], {}, "10m"),
    (["9m20s"], {}, "9m20s"),
    (["8m80s"], {}, "9m20s"),
    (["0m40s"], {}, "40s"),
    (["2m"], {}, "2m"),
    (["30s"], {}, "30s"),
    (["0m"], {}, "0s"),
    (["0s"], {}, "0s"),
])
def test_age(input_args, input_kwargs, expected):
    if isinstance(expected, Exception):
        with pytest.raises(expected.__class__, match=str(expected)):
            Age(*input_args, **input_kwargs)
    else:
        assert Age(*input_args, **input_kwargs).render() == expected


def test_jmespath_performance():
    """
    JMESPath performance regression test.  We use JMESPath to filter and transform
    the data returned by the Kubernetes API.
    """
    path = jmespath.compile("pods[?status.phase == 'Running'].metadata.name")
    data = {
        "pods": [
            {"status": {"phase": "Running"}, "metadata": {"name": "pod-1"}},
            {"status": {"phase": "Running"}, "metadata": {"name": "pod-2"}},
            {"status": {"phase": "Pending"}, "metadata": {"name": "pod-3"}},
        ]
    }
    # Use true system time
    import time
    start = time.time()
    for _ in range(10000):
        result = path.search({**data})
    end = time.time()
    assert end - start < 1.0
    assert result == ["pod-1", "pod-2"]


def test_dprint(capsys):
    FEATURE = "afeature"
    dprint(FEATURE, "hello")
    assert capsys.readouterr().out == ""
    debug([FEATURE])
    dprint(FEATURE, "hello")
    assert capsys.readouterr().out == "hello\n"
    debug([FEATURE], False)
    dprint(FEATURE, "hello")
    assert capsys.readouterr().out == ""
