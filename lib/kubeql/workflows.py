
from .utils import MyConfig

def add_workflows(db, config: MyConfig, objects):
    db.execute("""
        CREATE TABLE workflows (
            name TEXT,
            namespace TEXT,
            partition TEXT,
            id TEXT,
            url TEXT,
            phase TEXT,
            env_name TEXT
        )
    """)
    workflows = objects["workflows"]["items"]
    data = [(
        w["metadata"]["name"],
        w["metadata"]["namespace"],
        w["metadata"]["labels"].get("jabba.pathai.com/partition-name"),
        w["metadata"]["labels"].get("jabba.pathai.com/workflow-id"),
        f'http://app.mle.pathai.com/jabba/workflows/view/{w["metadata"]["labels"].get("jabba.pathai.com/workflow-id")}',
        w["metadata"]["labels"].get("workflows.argoproj.io/phase"),
        w["spec"]["templates"][0]["metadata"]["labels"].get("mle.pathai.com/mle-env-name"),
        ) for w in workflows]
    if not data:
        return
    placeholders = ", ".join("?" * len(data[0]))
    db.execute(f"INSERT INTO workflows VALUES({placeholders})", data)

