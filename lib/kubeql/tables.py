from abc import abstractmethod

from .config import Config, EMPTY_EXTENSION, ColumnDef
from .helpers import Resources, ItemHelper, PodHelper, JobHelper


class Table:
    """
    Turn 'kubectl get ... -o json" output into a database table.  Subclasses define
        make_rows   method to convert kubectl output into rows
    """

    def __init__(self, name, resource_kind, schema=None):
        """
        :param name: The table name
        :param resource_kind: The Kubernetes resource kind, e.g. "pods", "nodes", "jobs"
        :param schema: If present, the schema defining built-in columns
        """
        self.name = name
        self.resource_kind = resource_kind
        self.schema = schema

    @abstractmethod
    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        pass

    def create(self, db, config: Config, kube_data: dict):
        schema = self.schema or ""
        extra_columns = config.extend.get(self.name, EMPTY_EXTENSION).columns
        if extra_columns:
            schema += ", " if schema else ""
            schema += ", ".join(f"{name} {column._sqltype}"
                               for name, column in extra_columns.items())
        db.execute(f"CREATE TABLE {self.name} ({schema})")
        rows = self.make_rows(kube_data["items"])
        if rows:
            if extra_columns:
                rows = [row + tuple(self._convert(item, column) for column in extra_columns.values())
                        for item, row in zip(kube_data["items"], rows)]
            placeholders = ", ".join("?" * len(rows[0]))
            db.execute(f"INSERT INTO {self.name} VALUES({placeholders})", rows)

    def _convert(self, obj: object, column: ColumnDef) -> object:
        value = column._finder(obj)
        return None if value is None else column._pytype(value)


class NodesTable(Table):

    def __init__(self):
        super().__init__("nodes", "nodes", """
            name TEXT,
            provider TEXT,
            cpu_alloc REAL,
            gpu_alloc REAL,
            mem_alloc INTEGER,
            cpu_cap REAL,
            gpu_cap REAL,
            mem_cap INTEGER,
            ns_taints TEXT
        """)

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        return [(
            node.name,
            node.obj.get("spec", {}).get("providerID"),
            *Resources.extract(node["status"]["allocatable"]).as_tuple(),
            *Resources.extract(node["status"]["capacity"]).as_tuple(),
            ",".join(taint["key"] for taint in node.obj.get("spec", {}).get("taints", [])
                     if taint["effect"] == "NoSchedule")
        ) for node in map(ItemHelper, kube_data)]


class NodeTaintsTable(Table):

    def __init__(self):
        super().__init__("taints", "nodes", """
            name TEXT,
            key TEXT,
            effect TEXT
        """)

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        nodes = map(ItemHelper, kube_data)
        return [(
            node.name,
            taint["key"],
            taint["effect"],
        ) for node in nodes for taint in node.obj.get("spec", {}).get("taints", [])]


class PodsTable(Table):

    def __init__(self):
        super().__init__("pods", "pods", """
            name TEXT,
            is_daemon INTEGER,
            namespace TEXT,
            node_name TEXT,
            command TEXT,
            status TEXT,
            cpu_req REAL,
            gpu_req REAL,
            mem_req INTEGER,
            cpu_lim REAL,
            gpu_lim REAL,
            mem_lim INTEGER
        """)

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        return [(
            pod.name,
            1 if pod.is_daemon else 0,
            pod.namespace,
            pod["spec"].get("nodeName"),
            pod.command,
            pod["kubectl_status"],
            *pod.resources("requests").as_tuple(),
            *pod.resources("limits").as_tuple(),
        ) for pod in map(PodHelper, kube_data)]


class JobsTable(Table):

    def __init__(self):
        super().__init__("jobs", "jobs", """
            name TEXT,
            namespace TEXT,
            status TEXT
        """)

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        return [(
            job.name,
            job.namespace,
            job.status,
        ) for job in map(JobHelper, kube_data)]


class WorkflowsTable(Table):

    def __init__(self):
        super().__init__("workflows", "workflows", """
            name TEXT,
            namespace TEXT,
            phase TEXT
        """)

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        return [(
            w.name,
            w.namespace,
            w.label("workflows.argoproj.io/phase"),
        ) for w in map(ItemHelper, kube_data)]
