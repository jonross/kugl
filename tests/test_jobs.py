"""
Tests for the jobs table.
"""

from .testing import make_pod, make_job, kubectl_response, assert_query, Container, CGM


def test_job_status(test_home):
    kubectl_response("jobs", {
        "items": [
            make_job("job-1"),
            make_job("job-2", active_count=1),
            make_job("job-3", namespace="xyz", condition=("Failed", "False", None)),
            make_job("job-4", namespace="xyz", condition=("Failed", "True", None)),
            make_job("job-5", condition=("Failed", "True", "DeadlineExceeded")),
            make_job("job-6", condition=("Suspended", "True", None)),
            make_job("job-7", condition=("Complete", "True", None)),
            make_job("job-8", condition=("FailureTarget", "False", None)),
            make_job("job-9", condition=("SuccessCriteriaMet", "False", None)),
        ]
    })
    assert_query("SELECT name, namespace, status FROM jobs ORDER BY 1", """
        name    namespace    status
        job-1   example      Unknown
        job-2   example      Running
        job-3   xyz          Unknown
        job-4   xyz          Failed
        job-5   example      DeadlineExceeded
        job-6   example      Suspended
        job-7   example      Complete
        job-8   example      Failed
        job-9   example      Complete
    """)