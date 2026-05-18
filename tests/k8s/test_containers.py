"""Tests for the containers table."""

from ..testing import assert_query
from .k8s_mocks import kubectl_response, make_pod, Container, CGM


def _setup(pods):
    kubectl_response("pods", {"items": pods})
    statuses = "NAME   STATUS\n" + "\n".join(f"{p['metadata']['name']}  Running" for p in pods)
    kubectl_response("pod_statuses", statuses)


def test_regular_only(test_home):
    """Pod with no init containers produces one row per regular container."""
    _setup(
        [
            make_pod(
                "pod-1",
                containers=[
                    Container(
                        name="main", requests=CGM(cpu=2, mem="20M"), limits=CGM(cpu=2, mem="20M")
                    ),
                    Container(name="sidecar", requests=CGM(cpu=1, mem="10M"), limits=CGM()),
                ],
            ),
        ]
    )
    assert_query(
        "SELECT pod_uid, name, is_init, cpu_req, mem_req FROM containers ORDER BY name",
        [
            ["uid-pod-1", "main", 0, 2, 20_000_000],
            ["uid-pod-1", "sidecar", 0, 1, 10_000_000],
        ],
    )


def test_init_containers(test_home):
    """Init containers appear as separate rows with is_init=1."""
    _setup(
        [
            make_pod(
                "pod-1",
                containers=[
                    Container(
                        name="app", requests=CGM(cpu=2, mem="20M"), limits=CGM(cpu=2, mem="20M")
                    )
                ],
                init_containers=[
                    Container(
                        name="setup", requests=CGM(cpu=1, mem="10M"), limits=CGM(cpu=1, mem="10M")
                    )
                ],
            ),
        ]
    )
    assert_query(
        "SELECT name, is_init, cpu_req FROM containers ORDER BY is_init, name",
        [
            ["app", 0, 2],
            ["setup", 1, 1],
        ],
    )


def test_multi_pod_row_count(test_home):
    """Row count equals total containers across all pods."""
    _setup(
        [
            make_pod(
                "pod-1",
                containers=[Container(name="a"), Container(name="b")],
                init_containers=[Container(name="init")],
            ),
            make_pod("pod-2", containers=[Container(name="only")]),
        ]
    )
    assert_query(
        "SELECT pod_uid, name, is_init FROM containers ORDER BY pod_uid, is_init DESC, name",
        [
            ["uid-pod-1", "init", 1],
            ["uid-pod-1", "a", 0],
            ["uid-pod-1", "b", 0],
            ["uid-pod-2", "only", 0],
        ],
    )


def test_resources_not_summed(test_home):
    """Each container row carries its own resource values, not the pod aggregate."""
    _setup(
        [
            make_pod(
                "pod-1",
                containers=[
                    Container(
                        name="big", requests=CGM(cpu=4, mem="40M"), limits=CGM(cpu=4, mem="40M")
                    ),
                    Container(
                        name="small", requests=CGM(cpu=1, mem="10M"), limits=CGM(cpu=1, mem="10M")
                    ),
                ],
            ),
        ]
    )
    assert_query(
        "SELECT name, cpu_req, mem_req FROM containers ORDER BY name",
        [
            ["big", 4, 40_000_000],
            ["small", 1, 10_000_000],
        ],
    )


def test_image_column(test_home):
    """Image column is populated from the container spec."""
    _setup(
        [
            make_pod(
                "pod-1",
                containers=[
                    Container(name="app", image="myrepo/myapp:v1"),
                ],
            ),
        ]
    )
    assert_query(
        "SELECT name, image FROM containers",
        [["app", "myrepo/myapp:v1"]],
    )
