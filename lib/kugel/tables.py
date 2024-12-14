from typing import Optional

from .config import Config, EMPTY_EXTENSION, ColumnDef, ExtendTable, CreateTable
from .helpers import Resources, ItemHelper, PodHelper, JobHelper
from .api import parse_utc, table


class TableBuilder:

    def __init__(self, name, creator: CreateTable, extender: Optional[ExtendTable], schema: Optional[str] = None):
        """
        :param name: The name of the table
        :param creator: The configuration for creating the table
        :param extender: The configuration for extending the table, if any
        :param schema: If present, the schema defining built-in columns, and the subclass must
            also define a make_rows method.
        """
        self.name = name
        self.creator = creator
        self.extender = extender
        self.schema = schema

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        """
        Convert the JSON output of "kubectl get {resource} -o json" into a list of rows
        matching the columns provided in the built-in schema.  For tables without a built-in
        schema, this returns an empty row per item.
        """
        return [tuple()] * len(kube_data)

    def build(self, db, kube_data: dict):
        schema = self.schema or ""
        columns = {**self.creator.columns}
        if self.extender:
            columns.update(self.extender.columns)
        if columns:
            schema += ", " if schema else ""
            schema += ", ".join(f"{name} {column._sqltype}" for name, column in columns.items())
        db.execute(f"CREATE TABLE {self.name} ({schema})")
        rows = self.make_rows(kube_data["items"])
        if rows:
            if columns:
                rows = [row + tuple(column.extract(item) for column in columns.values())
                        for item, row in zip(kube_data["items"], rows)]
            placeholders = ", ".join("?" * len(rows[0]))
            db.execute(f"INSERT INTO {self.name} VALUES({placeholders})", rows)


@table(domain="kubernetes", name="nodes", resource="nodes")
class NodesTable(TableBuilder):

    def __init__(self, **kwargs):
        super().__init__(**kwargs, schema="""
            name TEXT,
            instance_type TEXT,
            cpu_alloc REAL,
            gpu_alloc REAL,
            mem_alloc INTEGER,
            cpu_cap REAL,
            gpu_cap REAL,
            mem_cap INTEGER
        """)

    def make_rows(self, kube_data: list[dict]) -> list[tuple]:
        return [(
            node.name,
            node.label("node.kubernetes.io/instance-type") or node.label("beta.kubernetes.io/instance-type"),
            *Resources.extract(node["status"]["allocatable"]).as_tuple(),
            *Resources.extract(node["status"]["capacity"]).as_tuple(),
        ) for node in map(ItemHelper, kube_data)]


@table(domain="kubernetes", name="taints", resource="nodes")
class TaintsTable(TableBuilder):

    def __init__(self, **kwargs):
        super().__init__(**kwargs, schema="""
            node_name TEXT,
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


@table(domain="kubernetes", name="pods", resource="pods")
class PodsTable(TableBuilder):

    def __init__(self, **kwargs):
        super().__init__(**kwargs, schema="""
            name TEXT,
            is_daemon INTEGER,
            namespace TEXT,
            node_name TEXT,
            creation_ts INTEGER,
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
            parse_utc(pod.metadata["creationTimestamp"]),
            pod.command,
            pod["kubectl_status"],
            *pod.resources("requests").as_tuple(),
            *pod.resources("limits").as_tuple(),
        ) for pod in map(PodHelper, kube_data)]


@table(domain="kubernetes", name="jobs", resource="jobs")
class JobsTable(TableBuilder):

    def __init__(self, **kwargs):
        super().__init__(**kwargs, schema="""
            name TEXT,
            namespace TEXT,
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
            job.name,
            job.namespace,
            job.status,
            *job.resources("requests").as_tuple(),
            *job.resources("limits").as_tuple(),
        ) for job in map(JobHelper, kube_data)]