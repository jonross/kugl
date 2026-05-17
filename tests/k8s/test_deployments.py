"""
Tests for the deployments table.
"""

from .k8s_mocks import make_deployment, kubectl_response
from ..testing import assert_query


def test_deployment_replicas(test_home):
    kubectl_response(
        "deployments",
        {
            "items": [
                make_deployment("deploy-1"),
                make_deployment("deploy-2", replicas=5, ready=3, available=3, updated=5),
                make_deployment("deploy-3", replicas=2, strategy="Recreate"),
            ]
        },
    )
    assert_query(
        "SELECT name, replicas, ready, available, updated, strategy FROM deployments ORDER BY 1",
        """
        name        replicas    ready    available    updated  strategy
        deploy-1           3        3            3          3  RollingUpdate
        deploy-2           5        3            3          5  RollingUpdate
        deploy-3           2        2            2          2  Recreate
        """,
    )


def test_deployment_labels(test_home):
    kubectl_response(
        "deployments",
        {
            "items": [
                make_deployment("deploy-1", labels=dict(app="web", env="prod")),
                make_deployment("deploy-2", labels=dict(app="api")),
                make_deployment("deploy-3", labels=dict()),
            ]
        },
    )
    assert_query(
        "SELECT deployment_uid, key, value FROM deployment_labels ORDER BY 2, 3, 1",
        """
        deployment_uid    key    value
        uid-deploy-2      app    api
        uid-deploy-1      app    web
        uid-deploy-1      env    prod
        """,
    )
