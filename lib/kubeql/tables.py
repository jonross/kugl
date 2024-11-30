from abc import abstractmethod
from typing import Optional

from .config import Config, EMPTY_EXTENSION, ColumnDef
from .helpers import Resources, ItemHelper, PodHelper, JobHelper


class TableBuilder:

    def __init__(self, name: str, resource: str, namespaced: bool, schema: Optional[str] = None):
        """
        :param name: The table name
        :param resource: The Kubernetes resource type, e.g. "pods", "nodes", "jobs"
        :param namespaced: True if the resource is namespaced
        :param schema: If present, the schema defining built-in columns, and the subclass must
            also define a make_rows method.
        """
        self.name = name
        self.resource = resource
        self.namespaced = namespaced
        self.schema = schema

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        """
        Convert the JSON output of "kubectl get {resource} -o json" into a list of rows
        matching the columns provided in the built-in schema.
        """
        return []

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


class NodesTable(TableBuilder):

    def __init__(self, **kwargs):
        super().__init__(**kwargs, schema="""
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


class TaintsTable(TableBuilder):

    def __init__(self, **kwargs):
        super().__init__(**kwargs, schema="""
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


class PodsTable(TableBuilder):

    def __init__(self, **kwargs):
        super().__init__(**kwargs, schema="""
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


class JobsTable(TableBuilder):

    def __init__(self, **kwargs):
        super().__init__(**kwargs, schema="""
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


class WorkflowsTable(TableBuilder):

    def __init__(self, **kwargs):
        super().__init__(**kwargs, schema="""
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
