import pytest

from .testing import make_pod, make_job, kubectl_response, assert_query, Container, CGM


def test_job_status(test_home):
    kubectl_response("jobs", {
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
    assert_query("SELECT name, status FROM jobs ORDER BY 1", """
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