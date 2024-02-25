
from kubeql.config import KConfig
from kubeql.constants import CACHE
from kubeql.main import KubeData
from kubeql.testing import make_pod

import pytest


@pytest.fixture(scope="session")
def kd():
    return KubeData(CACHE, False, "nocontext", data={
        "pods": {
            "items": [
                make_pod("pod-1"),
                make_pod("pod-2"),
                make_pod("pod-3", cpu_req=2),
                make_pod("pod-4", cpu_req=2),
            ]
        }
    })


def test_by_cpu(kd):
    verify(kd, "SELECT name FROM pods WHERE cpu_req > 1 ORDER BY name",
           [
               ("pod-3",),
               ("pod-4",),
           ])


def verify(kd, kql, expected):
    actual, _ = kd.query(KConfig(), kql)
    assert actual == expected
