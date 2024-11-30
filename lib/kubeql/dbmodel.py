
from .config import Config, EMPTY_EXTENSION


class Table:
    """
    Turn 'kubectl get ... -o json" output into a database table.  Subclasses define
        NAME        the table name
        SCHEMA      chunk of DDL with column names and types
        make_rows   method to convert kubectl output into rows
    """

    def create(self, db, config: Config, kube_data: dict):
        schema = self.SCHEMA
        extra_columns = config.extend.get(self.NAME, EMPTY_EXTENSION).columns
        if extra_columns:
            schema += " ".join(f", {name} {column._sqltype}"
                               for name, column in extra_columns.items())
        db.execute(f"CREATE TABLE {self.NAME} ({schema})")
        rows = self.make_rows(kube_data["items"])
        if rows:
            if extra_columns:
                rows = [row + tuple(column.extract(item) for column in extra_columns.values())
                        for item, row in zip(kube_data["items"], rows)]
            placeholders = ", ".join("?" * len(rows[0]))
            db.execute(f"INSERT INTO {self.NAME} VALUES({placeholders})", rows)
