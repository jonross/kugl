import pytest
from kubeql.utils import pretty_size

@pytest.mark.parametrize("nbytes,expected", [
    (0, "0B"),
    (1, "1B"),
    (1023, "1023B"),
    (1024, "1.0KB"),
    (1024 ** 2 - 1, "1023.9KB"),
    (1024 ** 2, "1.0MB"),
    (1024 ** 3 - 1, "1023.9MB"),
    (1024 ** 3, "1.0GB"),
    (1024 ** 4 - 1, "1023.9GB"),
    (1024 ** 4, "1.0TB"),
])
def test_pretty_size(nbytes: int, result: str):
    assert pretty_size(nbytes) == result

