"""
Tests for the nodes and taints tables.
"""

from .testing import make_node, kubectl_response, assert_query, Taint


def test_node_query(test_home):
    kubectl_response("nodes", {
        "items": [
            make_node("node-1")
        ]
    })
    assert_query("SELECT * FROM nodes", """
        name    instance_type      cpu_alloc    gpu_alloc     mem_alloc    cpu_cap    gpu_cap       mem_cap
        node-1  a40                       93            4  807771639808         96          4  810023981056
    """)


def test_taint_query(test_home):
    kubectl_response("nodes", {
        "items": [
            make_node("node-1"),
            make_node("node-2", taints=[Taint(key="node.kubernetes.io/unschedulable", effect="NoSchedule"),
                                        Taint(key="node.kubernetes.io/unreachable", effect="NoExecute")
                                        ]),
            make_node("node-3", taints=[Taint(key="mycompany.com/priority", effect="NoSchedule", value="true")
                                        ]),
        ]
    })
    assert_query("SELECT * FROM node_taints ORDER BY 1, 2", """
        node_name    key                               effect
        node-2       node.kubernetes.io/unreachable    NoExecute
        node-2       node.kubernetes.io/unschedulable  NoSchedule
        node-3       mycompany.com/priority            NoSchedule
    """)

