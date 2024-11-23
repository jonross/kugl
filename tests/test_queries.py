
import pytest

from kubeql.main import KubeData
from kubeql.utils import MyConfig

from .testing import make_pod, make_job


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
        "pod_statuses": {f"pod-{i}": f"Init:{i}" for i in range(1, 5)},
        "jobs": {
            "items": [
                make_job("job-1"),
                make_job("job-2", active_count=1),
                make_job("job-3", condition=("Failed", "False", None)),
                make_job("job-4", condition=("Failed", "True", None)),
                make_job("job-5", condition=("Failed", "True", "DeadlineExceeded")),
                make_job("job-6", condition=("Suspended", "True", None)),
                make_job("job-7", condition=("Complete", "True", None)),
                make_job("job-8", condition=("FailureTarget", "False", None)),
                make_job("job-9", condition=("SuccessCriteriaMet", "False", None)),
            ]
        }
    })


def test_by_cpu(kd):
    verify(kd, "SELECT name, status FROM pods WHERE cpu_req > 1 ORDER BY name",
           [
               ("pod-3", "Init:3"),
               ("pod-4", "Init:4"),
           ])


def test_job_status(kd):
    verify(kd, "SELECT name, status FROM jobs ORDER BY 1",
           [
               ("job-1", "Unknown"),
               ("job-2", "Running"),
               ("job-3", "Unknown"),
               ("job-4", "Failed"),
               ("job-5", "DeadlineExceeded"),
               ("job-6", "Suspended"),
               ("job-7", "Complete"),
               ("job-8", "Failed"),
               ("job-9", "Complete"),
           ])

def verify(kd, kql, expected):
    actual, _ = kd.query(MyConfig(), kql)
    assert actual == expected
