from .utils import K8SObjectHelper, Resources


def add_nodes(db, objects):
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
            mem_cap INTEGER
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


def add_node_load(db, objects):
    db.execute("""
        CREATE VIEW node_load (
            node_name,
            cpu_req,
            gpu_req,
            mem_req
        )
        AS SELECT node_name, sum(cpu_req), sum(gpu_req), sum(mem_req)
        FROM pods
        WHERE 
          node_name IS NOT NULL
          AND status = 'Running'
        GROUP BY node_name
    """)


class NodeHelper(K8SObjectHelper):
    pass