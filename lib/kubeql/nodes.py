from .utils import K8SObjectHelper, Resources


def add_nodes(db, nodes):
    db.execute("""
        CREATE TABLE nodes (
            name TEXT,
            node_family TEXT,
            amp_type TEXT,
            cpu_alloc REAL,
            gpu_alloc REAL,
            mem_alloc INTEGER,
            cpu_cap REAL,
            gpu_cap REAL,
            mem_cap INTEGER
        )
    """)
    nodes = [NodeHelper(node) for node in nodes["items"]]
    data = [(
        node.name,
        node.label("pathai.com/node-family") or node.label("mle.pathai.com/node-family"),
        node.label("amp.pathai.com/node-type"),
        *Resources.extract(node["status"]["allocatable"]).as_tuple(),
        *Resources.extract(node["status"]["capacity"]).as_tuple(),
        ) for node in nodes]
    if not data:
        return
    placeholders = ", ".join("?" * len(data[0]))
    db.execute(f"INSERT INTO nodes VALUES({placeholders})", data)


class NodeHelper(K8SObjectHelper):
    pass