"""
Tests for the events table.
"""

from kugl.util import UNIT_TEST_TIMEBASE
from .k8s_mocks import make_event, kubectl_response
from ..testing import assert_query


def test_event_columns(test_home):
    kubectl_response(
        "events",
        {
            "items": [
                make_event("ev1", event_type="Normal", reason="Scheduled", count=1,
                           obj_kind="Pod", obj_name="my-pod", source="default-scheduler"),
                make_event("ev2", event_type="Warning", reason="OOMKilling", count=5,
                           obj_kind="Pod", obj_name="my-pod", source="kubelet"),
                make_event("ev3", event_type="Warning", reason="Failed", count=3,
                           obj_kind="Node", obj_name="node-1", obj_namespace="", source="kubelet"),
            ]
        },
    )
    assert_query(
        "SELECT namespace, `type`, reason, `count`, obj_kind, obj_name, source FROM events ORDER BY reason",
        """
        namespace    type     reason        count  obj_kind    obj_name    source
        default      Warning  Failed            3  Node        node-1      kubelet
        default      Warning  OOMKilling        5  Pod         my-pod      kubelet
        default      Normal   Scheduled         1  Pod         my-pod      default-scheduler
        """,
    )


def test_event_timestamps(test_home):
    kubectl_response(
        "events",
        {
            "items": [
                make_event("ev1", first_ts=UNIT_TEST_TIMEBASE, last_ts=UNIT_TEST_TIMEBASE + 300),
            ]
        },
    )
    assert_query(
        "SELECT first_ts, last_ts, last_ts - first_ts AS elapsed FROM events",
        f"""
        first_ts     last_ts    elapsed
        {UNIT_TEST_TIMEBASE}  {UNIT_TEST_TIMEBASE + 300}        300
        """,
    )
