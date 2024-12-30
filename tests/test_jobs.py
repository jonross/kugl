"""
Tests for the jobs table.
"""

from .testing import make_job, kubectl_response, assert_query


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
    assert_query("SELECT name, uid, namespace, status FROM jobs ORDER BY 1", """
        name    uid        namespace    status
        job-1   uid-job-1  example      Unknown
        job-2   uid-job-2  example      Running
        job-3   uid-job-3  xyz          Unknown
        job-4   uid-job-4  xyz          Failed
        job-5   uid-job-5  example      DeadlineExceeded
        job-6   uid-job-6  example      Suspended
        job-7   uid-job-7  example      Complete
        job-8   uid-job-8  example      Failed
        job-9   uid-job-9  example      Complete
    """)


def test_job_labels(test_home):
    kubectl_response("jobs", {
        "items": [
            make_job("job-1", labels=dict(foo="bar")),
            make_job("job-2", labels=dict(a="b", c="d", e="f")),
            make_job("job-3", labels=dict()),
            make_job("job-4", labels=dict(one="two", three="four")),
        ]
    })
    assert_query("SELECT job_uid, key, value FROM job_labels ORDER BY 2, 1", """
        job_uid    key    value
        uid-job-2  a      b
        uid-job-2  c      d
        uid-job-2  e      f
        uid-job-1  foo    bar
        uid-job-4  one    two
        uid-job-4  three  four
    """)
