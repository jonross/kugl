"""
Tests for the services table.
"""

from .k8s_mocks import make_service, kubectl_response
from ..testing import assert_query


def test_service_types(test_home):
    kubectl_response(
        "services",
        {
            "items": [
                make_service("svc-1"),
                make_service("svc-2", svc_type="NodePort", cluster_ip="10.96.0.2"),
                make_service(
                    "svc-3",
                    svc_type="LoadBalancer",
                    cluster_ip="10.96.0.3",
                    external_ip="203.0.113.5",
                ),
                make_service("svc-4", svc_type="ExternalName", cluster_ip="None"),
            ]
        },
    )
    assert_query(
        "SELECT name, type, cluster_ip, external_ip FROM services ORDER BY 1",
        """
        name    type          cluster_ip    external_ip
        svc-1   ClusterIP     10.96.0.1
        svc-2   NodePort      10.96.0.2
        svc-3   LoadBalancer  10.96.0.3     203.0.113.5
        svc-4   ExternalName
        """,
    )


def test_service_labels(test_home):
    kubectl_response(
        "services",
        {
            "items": [
                make_service("svc-1", labels=dict(foo="bar")),
                make_service("svc-2", labels=dict(a="b", c="d")),
                make_service("svc-3", labels=dict()),
            ]
        },
    )
    assert_query(
        "SELECT service_uid, key, value FROM service_labels ORDER BY 2, 1",
        """
        service_uid    key    value
        uid-svc-2      a      b
        uid-svc-2      c      d
        uid-svc-1      foo    bar
        """,
    )
