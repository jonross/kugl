"""
Tests for the cronjobs table.
"""

from kugl.util import UNIT_TEST_TIMEBASE
from .k8s_mocks import make_cronjob, kubectl_response
from ..testing import assert_query


def test_cronjob_fields(test_home):
    kubectl_response(
        "cronjobs",
        {
            "items": [
                make_cronjob("cj-01"),
                make_cronjob("cj-02", schedule="*/5 * * * *", active_count=2,
                             last_schedule_ts=UNIT_TEST_TIMEBASE,
                             last_success_ts=UNIT_TEST_TIMEBASE),
                make_cronjob("cj-03", suspend=True),
                make_cronjob("cj-04", namespace="xyz"),
            ]
        },
    )
    assert_query(
        "SELECT name, uid, namespace, schedule, suspend, active, last_schedule_ts, last_success_ts FROM cronjobs ORDER BY 1",
        f"""
        name    uid        namespace    schedule       suspend    active    last_schedule_ts    last_success_ts
        cj-01   uid-cj-01  example      0 * * * *            0         0
        cj-02   uid-cj-02  example      */5 * * * *          0         2          {UNIT_TEST_TIMEBASE}         {UNIT_TEST_TIMEBASE}
        cj-03   uid-cj-03  example      0 * * * *            1         0
        cj-04   uid-cj-04  xyz          0 * * * *            0         0
        """,
    )


def test_cronjob_labels(test_home):
    kubectl_response(
        "cronjobs",
        {
            "items": [
                make_cronjob("cj-1", labels=dict(foo="bar")),
                make_cronjob("cj-2", labels=dict(a="b", c="d")),
                make_cronjob("cj-3", labels=dict()),
            ]
        },
    )
    assert_query(
        "SELECT cronjob_uid, key, value FROM cronjob_labels ORDER BY 2, 1",
        """
        cronjob_uid    key    value
        uid-cj-2       a      b
        uid-cj-2       c      d
        uid-cj-1       foo    bar
        """,
    )
