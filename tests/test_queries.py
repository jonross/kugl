
from kubeql.constants import CACHE
from kubeql.main import KubeData
from kubeql.testing import make_pod
from kubeql.utils import MyConfig

import pytest


@pytest.fixture(scope="session")
def kd():
    return KubeData(None, data={
        "pods": {
            "items": [
                make_pod("pod-1"),
                make_pod("pod-2"),
                make_pod("pod-3", cpu_req=2),
                make_pod("pod-4", cpu_req=2),
            ]
        },
        "pod_statuses": {f"pod-{i}": f"Init:{i}" for i in range(1, 5)}
    })


def test_by_cpu(kd):
    verify(kd, "SELECT name, status FROM pods WHERE cpu_req > 1 ORDER BY name",
           [
               ("pod-3", "Init:3"),
               ("pod-4", "Init:4"),
           ])


def verify(kd, kql, expected):
    actual, _ = kd.query(MyConfig(), kql)
    assert actual == expected
