
from .dbmodel import Table
from .utils import K8SObjectHelper, Resources, MyConfig


class NodesTable(Table):

    NAME = "nodes"
    RESOURCE_KIND = "nodes"
    SCHEMA = """
        name TEXT,
        provider TEXT,
        node_family TEXT,
        amp_type TEXT,
        cpu_alloc REAL,
        gpu_alloc REAL,
        mem_alloc INTEGER,
        cpu_cap REAL,
        gpu_cap REAL,
        mem_cap INTEGER,
        ns_taints TEXT
    """

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        return [(
            node.name,
            node.obj.get("spec", {}).get("providerID"),
            node.label("pathai.com/node-family") or node.label("mle.pathai.com/node-family"),
            node.label("amp.pathai.com/node-type"),
            *Resources.extract(node["status"]["allocatable"]).as_tuple(),
            *Resources.extract(node["status"]["capacity"]).as_tuple(),
            ",".join(taint["key"] for taint in node.obj.get("spec", {}).get("taints", [])
                     if taint["effect"] == "NoSchedule")
        ) for node in map(NodeHelper, kube_data)]


class NodeTaintsTable(Table):

    NAME = "node_taints"
    RESOURCE_KIND = "nodes"
    SCHEMA = """
        name TEXT,
        key TEXT,
        effect TEXT
    """

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        nodes = map(NodeHelper, kube_data)
        return [(
            node.name,
            taint["key"],
            taint["effect"],
        ) for node in nodes for taint in node.obj.get("spec", {}).get("taints", [])]


class NodeHelper(K8SObjectHelper):
    pass