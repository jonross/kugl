"""
More assorted tests, should these be combined with test_misc.py?
"""

import jmespath
import pytest

from kugl.util import Age, parse_size, to_size, dprint, debug, parse_cpu


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


@pytest.mark.parametrize("size_str, expected_result", [
    ("", "Can't translate '' to bytes"),
    ("1n", "Can't translate '1n' to bytes"),
    ("15", 15.0),
    ("15K", 15.0 * 10 ** 3),
    ("15Ki", 15.0 * 2 ** 10),
    ("15M", 15.0 * 10 ** 6),
    ("15Mi", 15.0 * 2 ** 20),
    ("15G", 15.0 * 10 ** 9),
    ("15Gi", 15.0 * 2 ** 30),
])
def test_parse_size(size_str, expected_result):
    if isinstance(expected_result, str):
        with pytest.raises(ValueError, match=expected_result):
            parse_size(size_str)
    else:
        assert parse_size(size_str) == expected_result


@pytest.mark.parametrize("cpu_str, expected_result", [
    (None, None),
    (2, 2),
    (2.0, 2.0),
    ("1.5", 1.5),
    ("300m", 0.3),
    ("50x", "could not convert string to float"),
])
def test_parse_cpu(cpu_str, expected_result):
    if isinstance(expected_result, str):
        with pytest.raises(ValueError, match=expected_result):
            parse_cpu(cpu_str)
    else:
        assert parse_cpu(cpu_str) == expected_result


@pytest.mark.parametrize("args,result", [
    ((0,), "0"),
    ((1,), "1"),
    ((999,), "999"),
    ((1023, True), "1023"),
    ((1000,), "1.0K"),
    ((1024, True), "1.0Ki"),
    ((1000 ** 2 - 1000,), "999K"),
    ((1024 ** 2 - 1024, True), "1023Ki"),
    ((1000 ** 2,), "1.0M"),
    ((1024 ** 2, True), "1.0Mi"),
    ((1000 ** 3 - 1000 ** 2,), "999M"),
    ((1024 ** 3 - 1024 ** 2, True), "1023Mi"),
    ((1000 ** 3,), "1.0G"),
    ((1024 ** 3, True), "1.0Gi"),
    ((1000 ** 4 - 1000 ** 3,), "999G"),
    ((1024 ** 4 - 1024 ** 3, True), "1023Gi"),
    ((1000 ** 4,), "1.0T"),
    ((1024 ** 4, True), "1.0Ti"),
])
def test_to_size(args: tuple, result: str):
    assert to_size(*args) == result


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
