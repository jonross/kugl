"""
Tests for the nodes and taints tables.
"""

import yaml

from kugl.impl.config import parse_model, UserConfig
from kugl.util import fail
from .testing import make_node, kubectl_response, assert_query, Taint


def test_node_query(test_home):
    (test_home / "kubernetes.yaml").write_text("""
        extend:
          - table: nodes
            columns:
              - name: instance_type
                label:
                  - node.kubernetes.io/instance-type
                  - beta.kubernetes.io/instance-type
            
    """)
    kubectl_response("nodes", {
        "items": [
            make_node("node-1", labels={"node.kubernetes.io/instance-type": "a40"}),
            make_node("node-2", labels={"beta.kubernetes.io/instance-type": "a40"}),
        ]
    })
    assert_query("SELECT * FROM nodes ORDER BY name", """
        name    uid           cpu_alloc    gpu_alloc     mem_alloc    cpu_cap    gpu_cap       mem_cap  instance_type
        node-1  uid-node-1           93            4  807771639808         96          4  810023981056  a40
        node-2  uid-node-2           93            4  807771639808         96          4  810023981056  a40
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
    assert_query("""
        SELECT n.name, nt.key, nt.effect
        FROM nodes n join node_taints nt on nt.node_uid = n.uid
        ORDER BY 1, 2
    """, """
        name    key                               effect
        node-2  node.kubernetes.io/unreachable    NoExecute
        node-2  node.kubernetes.io/unschedulable  NoSchedule
        node-3  mycompany.com/priority            NoSchedule
    """)


def test_node_labels(test_home):
    kubectl_response("nodes", {
        "items": [
            make_node("node-1", labels=dict(foo="bar")),
            make_node("node-2", labels=dict(a="b", c="d", e="f")),
            make_node("node-3", labels=dict()),
            make_node("node-4", labels=dict(one="two", three="four")),
        ]
    })
    assert_query("SELECT node_uid, key, value FROM node_labels ORDER BY 2, 1", """
        node_uid    key    value
        uid-node-2  a      b
        uid-node-2  c      d
        uid-node-2  e      f
        uid-node-1  foo    bar
        uid-node-4  one    two
        uid-node-4  three  four
    """)
