import textwrap

from kubeql.constants import ALWAYS
from kubeql.main import Engine
from kubeql.utils import MyConfig

from .testing import make_pod, make_job, kubectl_response


def test_by_cpu(mockdir):
    kubectl_response(mockdir, "pods", {
        "items": [
            make_pod("pod-1"),
            make_pod("pod-2"),
            make_pod("pod-3", cpu_req=2),
            make_pod("pod-4", cpu_req=2),
            make_pod("pod-5", cpu_req=2),  # should get dropped because no status available
        ]
    })
    kubectl_response(mockdir, "pod_statuses", """
        NAME   STATUS
        pod-1  Init:1
        pod-2  Init:2
        pod-3  Init:3
        pod-4  Init:4
    """)
    verify(mockdir, "SELECT name, status FROM pods WHERE cpu_req > 1 ORDER BY name", """
        name    status
        pod-3   Init:3
        pod-4   Init:4
    """)


def test_job_status(mockdir):
    kubectl_response(mockdir, "jobs", {
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
    })
    verify(mockdir, "SELECT name, status FROM jobs ORDER BY 1", """
        name    status
        job-1   Unknown
        job-2   Running
        job-3   Unknown
        job-4   Failed
        job-5   DeadlineExceeded
        job-6   Suspended
        job-7   Complete
        job-8   Failed
        job-9   Complete
    """)


def verify(mockdir, kql, expected):
    config = MyConfig(mockdir)
    actual = Engine(config, "nocontext", ALWAYS).query_and_format(kql)
    assert actual.strip() == textwrap.dedent(expected).strip()
