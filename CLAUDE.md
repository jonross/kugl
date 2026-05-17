# Kugl — Claude Seed Context

> **Note to Claude:** Please keep this file current as the project evolves.

Kugl lets you query Kubernetes (and other) resources using SQL. It fetches JSON via `kubectl get`
(or other sources), loads it into an in-memory SQLite database, runs the query, and formats results.

## Package Layout

```
kugl/
  api.py              # Public decorators: @table, @resource_type, @column
  main.py             # CLI entry point; shortcut expansion occurs here when args.sql contains no spaces
  impl/
    engine.py         # Engine (query execution), DataCache, ResourceRef
    registry.py       # Registry (singleton), Schema, Resource base class
    tables.py         # Table, TableFromCode, TableFromConfig, TableDef, RowContext, Itemizer
    config.py         # Pydantic models: Settings, UserConfig, Column, UserColumn,
                      #   ResourceDef, CreateTable, ExtendTable, Shortcut
    extract.py        # PathExtractor, LabelExtractor, Extractor base, FieldRef, type maps
  builtins/
    resources.py      # Built-in resource families (kubernetes, file, folder, exec, data)
    schemas/
      kubernetes.py   # Built-in @table classes for pods, nodes, jobs, etc.
  util/               # Helpers: Age, KPath, SqliteDb, Query, clock, debugging, etc.
tests/
  k8s/               # Kubernetes table tests
  config/            # Config parsing and merge tests
  resource/          # Per-resource-type tests (cache, exec, file, folder, etc.)
docs/                # RST documentation (syntax, builtins, extending, resources, multi, settings)
kugl/builtins/schemas/ # Built-in YAML schema configs (kubernetes.yaml, etc.)
```

## Core Concepts

### Schema
A named group of tables and resources. The default schema is `"kubernetes"`. Multi-schema queries
attach each schema as a separate in-memory SQLite database and require explicit `schema.table`
qualification in SQL.

### Resource (family)
Where data comes from. The **resource family** is the type (e.g., `kubernetes`, `file`, `folder`,
`exec`, `data`); a **resource** is a specific instance with a name and family-specific config.

Built-in families:
- `kubernetes` — runs `kubectl get <resource> -o json`; supports `-n`/`-a` namespace flags
- `file` — reads a local file (YAML or JSON); `file: ~/.kube/config`
- `folder` — globs files in a tree, presents each as `{match: {...}, content: {...}}`
- `exec` — runs any shell command producing JSON/YAML; optionally cacheable with `cache_key`
- `data` — static inline data

### Registry (singleton)
`Registry.get()` is the process-wide singleton. It maps:
- resource family name → Resource subclass (`resources_by_family`)
- schema name → default Resource subclass (`resources_by_schema`)
- schema name → `Schema` object (`schemas`)

Populated at import time by `@table` and `@resource_type` decorators.

### Schema object
`Schema` holds:
- `builtin`: `{name: TableDef}` — tables defined in Python via `@table`
- `_create`: tables defined in user config `create:` sections
- `_extend`: column extensions from `extend:` sections
- `_resources`: resource instances from config `resources:` sections

`Schema.read_configs()` merges config files from (in order): builtin schemas package,
any `init_path` folders, then `~/.kugl/`.

### Table hierarchy
- `Table` — base; holds column lists, implements `build()` (CREATE TABLE + INSERT)
- `TableFromCode` — wraps a `@table`-decorated class; delegates `make_rows()` to it
- `TableFromConfig` — built from a `create:` config block; uses `Itemizer` for row generation

### ResourceRef
A `(schema, resource)` pair used as a hashable set member for cache tracking.
Name property is `"schema_name.resource_name"`.

### Engine
`Engine.query()` orchestrates:
1. Identify schemas from the SQL query; attach them as SQLite databases
2. `Schema.read_configs()` for each schema
3. Build `Table` and `ResourceRef` objects for each named table
4. `DataCache.advise_refresh()` to decide what to fetch vs read from cache
5. Parallel fetch using ThreadPoolExecutor
6. `Table.build()` to CREATE TABLE and INSERT rows
7. Execute the SQL query and return rows + column names

### DataCache
Stores JSON responses under `~/.kugl/cache/<schema>/<resource_cache_path>.json`.
Cache age is based on file mtime. Three cache flags:
- `ALWAYS_UPDATE` (`-u`) — fetch everything, no stale warning
- `CHECK` (default) — fetch expired/missing, warn about stale data
- `NEVER_UPDATE` (`-c`) — only fetch missing, never update existing cache

## Config Files

### `~/.kugl/init.yaml`
Top-level settings and shortcuts. Only this file may contain `settings:`.

```yaml
settings:
  cache_timeout: 5m    # default 2m
  quiet: true          # suppress stale-data warnings
  init_path:           # extra config folders, applied before ~/.kugl/
    - ~/team-kugl

shortcuts:
  - name: mypods
    args: ["select name, status from pods where namespace = 'default'"]
  - name: pods-by-image
    args: ["select pod_name, namespace from containers where image like '%{{img}}%'"]
    params:
      - img
```

Shortcuts support positional parameters via `{{name}}` tokens in `args`. Declare param names in
`params:`; supply values at invocation time as trailing positional arguments:

```
kugl pods-by-image nginx
kugl -H pods-by-image nginx   # flags before the shortcut name still work
```

Config validation fails at parse time if a `{{token}}` appears in `args` but is not listed in
`params`. Invocation fails with a clear error if the wrong number of arguments is supplied.

### `~/.kugl/<schema>.yaml` (e.g. `kubernetes.yaml`)
Defines resources and tables for a schema.

```yaml
resources:
  - name: workflows        # resource name used by create: tables
    namespaced: true       # for kubernetes family; default true

create:
  - table: workflows
    resource: workflows
    row_source:            # default is ["items"]
      - items
    columns:
      - name: name
        path: metadata.name
      - name: status
        label: workflows.argoproj.io/phase

extend:
  - table: pods
    columns:
      - name: owner
        type: text
        label: com.mycompany/owner
        comment: ML team owner
```

## Column Extractors

Three extractor keys, specified in a column definition:

**`path:`** — JMESPath expression into the current row item  
**`label:`** — shortcut to `metadata.labels`; can be a list to try in order  
**`from:`** — unified key that auto-detects label vs path: values matching `domain/key` (e.g. `karpenter.sh/nodepool`) use `LabelExtractor`; everything else uses `PathExtractor`

**Named scope navigation** — in multi-step `row_source`, each entry must carry `as <name>`, and every column expression must end with `in <name>` to identify which scope to resolve against:
- `metadata.uid in node` extracts `metadata.uid` from the object named `node` at a higher level
- All named scopes from ancestor levels are available at each step

## Column Types

Kugl types (used in config `type:`) → SQLite storage type:

| Kugl type | SQLite | Accepts |
|-----------|--------|---------|
| `text`    | TEXT   | strings |
| `integer` | INTEGER | ints |
| `real`    | REAL   | floats |
| `size`    | INTEGER | `50Mi`, bytes |
| `age`     | INTEGER | `5d`, `4h30m`, seconds |
| `cpu`     | REAL   | `0.5`, `300m` |
| `date`    | INTEGER | `2021-01-01T12:34:56Z`, epoch secs |

Built-in SQL functions: `now()`, `to_utc(ts)`, `to_age(secs)`, `to_size(bytes)`

## row_source

Multi-step JMESPath iteration for generating multiple rows per API response item.

```yaml
row_source:
  - items as node       # step 1: each element of the top-level items array, named "node"
  - spec.taints as taint  # step 2: each taint within each node, named "taint"
columns:
  - name: node_uid
    path: metadata.uid in node   # "in node" suffix resolves to the step-1 object
  - name: taint_key
    path: key in taint           # "in taint" suffix resolves to the step-2 object
```

- Each step applies to results of the prior step
- Multi-step tables require `as <name>` on every entry; all column paths/labels must end with `in <name>`
- Single-step tables use bare JMESPath paths with no scope qualifier
- Dict sources can be unpacked to key/value pairs with `; kv` suffix: `- env; kv`
- Default `row_source` is `["items"]`

## Decorators (kugl/api.py)

```python
from kugl.api import resource_type, table, column, Resource

@resource_type(type="myfamily", schema_defaults=["myschema"])
class MyResource(Resource):
    def get_objects(self): ...
    def cache_path(self): ...

@table(schema="kubernetes", name="pods", resource="pods")
class PodsTable:
    def columns(self) -> list[Column]: ...
    def make_rows(self, context: RowContext) -> list[tuple[dict, tuple]]: ...
```

`make_rows` returns `[(item_dict, row_tuple), ...]` where `row_tuple` contains one value per
builtin column (non-builtin/extension columns are appended by `Table.build()`).

## Multi-Schema Queries

When a query references `schema.table`, each schema gets an `ATTACH DATABASE ':memory:' AS schema`
and all table names must be fully qualified.

```sql
SELECT k.name, e.zone
FROM kubernetes.nodes k
JOIN ec2.instances e ON k.name = e.hostname
```

The `ec2` schema is defined in `~/.kugl/ec2.yaml` with an `exec:` resource.

## Debugging

Set `KUGL_DEBUG` env var to a comma-separated list of topics:
- `cache` — cache hit/miss decisions
- `extract` — column value extraction
- `itemize` — row_source iteration steps

## Testing Notes

- The Registry is a process singleton; tests use `Schema.read_configs()` to reset non-builtin state
- `clock.CLOCK` is patched in tests to control time (for cache age calculations)
- Tests use actual in-memory SQLite; no mocking of the DB layer
- Kubernetes tests mock `kubectl` via fixtures in `tests/k8s/k8s_mocks.py`
- Shortcut and config merge tests live in `tests/config/test_merge_init.py`

## Running Tests

```bash
uv run pytest tests/          # full suite
uv run pytest tests/ -k foo   # filter by name
```

**Important:** always run from the project root with `tests/` as the target, not an individual file.
The Registry is populated by decorator side-effects at import time; running a single test module in
isolation skips those imports and causes "Resource family X is not registered" errors.
