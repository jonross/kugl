"""
Tests for the pods table.
"""

import pytest

from kugl.builtins.helpers import PodHelper
from kugl.util import UNIT_TEST_TIMEBASE

from .testing import make_pod, kubectl_response, Container, CGM, assert_query, make_job


def test_missing_metadata():
    """Verify pod.label() does not fail if metadata is missing"""
    pod = PodHelper(make_pod("noname", no_metadata=True))
    assert pod.label("foo") is None


def test_name():
    """Verify different locations for the pod name, including no name at all."""
    pod = PodHelper(make_pod("mypod-1"))
    assert pod.name == "mypod-1"
    pod = PodHelper(make_pod("mypod-2", name_at_root=True))
    assert pod.name == "mypod-2"
    pod = PodHelper(make_pod("mypod-3", no_name=True))
    assert pod.name is None


def test_no_main_container():
    # Not sure when this would apply; it's here for coverage
    pod = make_pod("pod-1", containers=[])
    assert PodHelper(pod).main is None


def test_by_cpu(test_home):
    kubectl_response("pods", {
        "items": [
            make_pod("pod-1"),
            make_pod("pod-2"),
            make_pod("pod-3", containers=[Container(requests=CGM(cpu=2, mem="10M"))]),
            make_pod("pod-4", containers=[Container(requests=CGM(cpu="2000m", mem="10M"))]),
            # should get dropped because no status available
            make_pod("pod-5", containers=[Container(requests=CGM(cpu=2, mem="10M"))]),
        ]
    })
    kubectl_response("pod_statuses", """
        NAME   STATUS
        pod-1  Init:1
        pod-2  Init:2
        pod-3  Init:3
        pod-4  Init:4
    """)
    assert_query("SELECT name, status FROM pods WHERE cpu_req > 1 ORDER BY name", """
        name    status
        pod-3   Init:3
        pod-4   Init:4
    """)


def test_other_pod_fields(test_home):
    kubectl_response("pods", {
        "items": [
            make_pod("pod-1", namespace="xyz", is_daemon=True, phase="Pending"),
            make_pod("pod-3", node_name="joe", creation_ts=UNIT_TEST_TIMEBASE + 60),
            make_pod("pod-4", containers=[Container(command=["echo", "bye"])]),
        ]
    })
    kubectl_response("pod_statuses", """
        NAMESPACE  NAME   STATUS
        xyz        pod-1  Pending
        default    pod-2  Running
        default    pod-3  Terminating
        default    pod-4  Terminating
    """)
    assert_query("""
        SELECT namespace, phase, uid, is_daemon, node_name, command, to_utc(creation_ts) AS created
        FROM pods ORDER BY name
    """, """
        namespace    phase    uid          is_daemon  node_name    command     created
        xyz          Pending  uid-pod-1            1  worker5      echo hello  2024-12-10T02:49:02Z
        default      Running  uid-pod-3            0  joe          echo hello  2024-12-10T02:50:02Z
        default      Running  uid-pod-4            0  worker5      echo bye    2024-12-10T02:49:02Z
    """, all_ns=True)


@pytest.mark.parametrize("containers,expected", [
    # Typical pod - cpu/mem requests/limits, no GPU
    ([Container(requests=CGM(cpu=1, mem="1Mi"), limits=CGM(cpu=1, mem="1Mi"))],
     [ [1, 1, 1<<20, 1<<20, None, None] ]),
    # Same thing but remove limits
    ([Container(requests=CGM(cpu=1, mem="1Mi"), limits=CGM())],
     [ [1, None, 1<<20, None, None, None] ]),
    # Repeat first example but with two containers; should sum the GPU Nones
    ([Container(requests=CGM(cpu=1, mem="1Mi"), limits=CGM(cpu=1, mem="1Mi")),
      Container(requests=CGM(cpu=1, mem="1Mi"), limits=CGM(cpu=1, mem="1Mi"))],
     [ [2, 2, 2<<20, 2<<20, None, None] ]),
    # Add a GPU request
    ([Container(requests=CGM(cpu=1, mem="1Mi", gpu=3), limits=CGM(cpu=1, mem="1Mi", gpu=3))],
     [ [1, 1, 1<<20, 1<<20, 3, 3] ]),
    # Mixing set and unset limits should result in Nones
    ([Container(requests=CGM(cpu=1, mem="1Mi"), limits=CGM(cpu=1, mem="1Mi")),
      Container(requests=CGM(cpu=1, mem="1Mi"), limits=CGM(cpu=1, mem="1Mi")),
      Container(requests=CGM(cpu=1, mem="1Mi"), limits=CGM())],
     [ [3, 2, 3<<20, 2<<20, None, None] ]),
])
def test_resource_summing(test_home, containers, expected):
    pod = make_pod("pod-1", containers=containers)
    kubectl_response("pods", {"items": [pod]})
    kubectl_response("pod_statuses", "NAME    STATUS\npod-1  Running")
    assert_query("SELECT cpu_req, cpu_lim, mem_req, mem_lim, gpu_req, gpu_lim FROM pods", expected)
    # Try the same thing but with a job
    job = make_job("job-1", pod=pod)
    kubectl_response("jobs", {"items": [job]})
    assert_query("SELECT cpu_req, cpu_lim, mem_req, mem_lim, gpu_req, gpu_lim FROM jobs", expected)


def test_pod_labels(test_home):
    kubectl_response("pods", {
        "items": [
            make_pod("pod-1", labels=dict(foo="bar")),
            make_pod("pod-2", labels=dict(a="b", c="d", e="f")),
            make_pod("pod-3", labels=dict()),
            make_pod("pod-4", labels=dict(one="two", three="four")),
        ]
    })
    kubectl_response("pod_statuses", """
        NAME   STATUS
        pod-1  Init:1
        pod-2  Init:2
        pod-3  Init:3
        pod-4  Init:4
    """)
    assert_query("SELECT pod_uid, key, value FROM pod_labels ORDER BY 2, 1", """
        pod_uid    key    value
        uid-pod-2  a      b
        uid-pod-2  c      d
        uid-pod-2  e      f
        uid-pod-1  foo    bar
        uid-pod-4  one    two
        uid-pod-4  three  four
    """)
