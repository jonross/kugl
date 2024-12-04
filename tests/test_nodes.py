from .testing import make_node, kubectl_response, assert_query


def test_node_query(test_home):
    kubectl_response("nodes", {
        "items": [
            make_node()
        ]
    })
    assert_query("SELECT * FROM nodes", """
        name           instance_type      cpu_alloc    gpu_alloc     mem_alloc    cpu_cap    gpu_cap       mem_cap
        sample-node-1  a40                       93            4  807771639808         96          4  810023981056
    """)

