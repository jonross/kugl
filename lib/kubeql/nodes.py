
from .utils import K8SObjectHelper, Resources, MyConfig


def add_nodes(db, config: MyConfig, objects):
    db.execute("""
        CREATE TABLE nodes (
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
        )
    """)
    nodes = [NodeHelper(node) for node in objects["nodes"]["items"]]
    data = [(
        node.name,
        node.obj.get("spec", {}).get("providerID"),
        node.label("pathai.com/node-family") or node.label("mle.pathai.com/node-family"),
        node.label("amp.pathai.com/node-type"),
        *Resources.extract(node["status"]["allocatable"]).as_tuple(),
        *Resources.extract(node["status"]["capacity"]).as_tuple(),
        ",".join(taint["key"] for taint in node.obj.get("spec", {}).get("taints", [])
                 if taint["effect"] == "NoSchedule")
    ) for node in nodes]
    if not data:
        return
    placeholders = ", ".join("?" * len(data[0]))
    db.execute(f"INSERT INTO nodes VALUES({placeholders})", data)


def add_node_taints(db, objects):
    db.execute("""
        CREATE TABLE node_taints (
            name TEXT,
            key TEXT,
            effect TEXT
        )
    """)
    nodes = [NodeHelper(node) for node in objects["nodes"]["items"]]
    data = [(
        node.name,
        taint["key"],
        taint["effect"],
    ) for node in nodes for taint in node.obj.get("spec", {}).get("taints", [])]
    if not data:
        return
    placeholders = ", ".join("?" * len(data[0]))
    db.execute(f"INSERT INTO node_taints VALUES({placeholders})", data)


class NodeHelper(K8SObjectHelper):
    pass