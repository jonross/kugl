import time

import jmespath


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
    start = time.time()
    for _ in range(10000):
        result = path.search({**data})
    end = time.time()
    assert end - start < 1.0
    assert result == ["pod-1", "pod-2"]

