# Kugl Discussion Summary

## What Kugl Is

Kugl is a Python CLI tool that queries Kubernetes resources using SQL (SQLite). It runs `kubectl get` commands, caches the JSON output, and loads it into an in-memory SQLite database. Users write SQL queries directly on the command line or via saved shortcuts.

Built-in tables: `pods`, `jobs`, `nodes`, `node_labels`, `pod_labels`, `job_labels`, `node_taints`. Resource types, namespaces, and cache TTL are controlled via CLI flags (`-a`, `-n`, `-u`, `-c`, `-t`).

Kugl automatically converts Kubernetes-specific value formats to queryable numerics: `50Mi` → bytes, `100m` CPU → float, ISO8601 timestamps → epoch seconds. Helper functions `to_size()`, `to_age()`, `to_utc()` convert back to human-readable strings for output.

---

## Strengths

- **SQL is better than jq for aggregation.** Queries involving `GROUP BY`, `SUM`, `JOIN`, `ORDER BY`, and CTEs are dramatically more readable in SQL than in jq pipelines. The target use case — "how is compute distributed across node pools and taints?" — is well served.
- **Automatic type coercion.** CPU, memory, and timestamp conversion is handled transparently. Steampipe's Kubernetes plugin likely exposes these as raw strings or JSONB; kugl makes them directly comparable numerically.
- **Built-in caching.** A 2-minute TTL cache avoids hammering the API server during exploratory queries.
- **Declarative extensions require no code.** Adding a label or nested field to an existing table takes 4 lines of YAML, no build step, no Go, no Python. Far more accessible than Steampipe's Go plugin model.
- **Multi-schema queries.** Joining Kubernetes data with other JSON sources (files, exec output) via `kubernetes.nodes JOIN ec2.instances` is architecturally sound, even if the AWS side is experimental.

---

## Weaknesses

### Priority (blocking credibility)

1. **Narrow built-in resource coverage.** Only pods, jobs, and nodes are built in. Deployments, StatefulSets, DaemonSets, CronJobs, Services, Ingresses, Namespaces, PVs/PVCs are absent. Users can add them via YAML config, but requiring setup before querying standard resources is a significant barrier.

2. **No per-container table.** Pod-level resource data aggregates across all containers. For multi-container pods (sidecars, init containers), individual container visibility is lost. A `containers` table (one row per container, joinable to `pods` via pod UID) is needed.

3. **No context selection at invocation time.** Users must `kubectl config use-context` before running kugl. A `--context` flag is table stakes for anyone with more than one cluster.

4. **No structured output.** Output is human-readable tabular text only. Without `--output csv` or `--output json`, kugl cannot participate in pipelines or feed dashboards.

5. **No shortcut parameters.** Shortcuts are static query aliases. The docs acknowledge this gap and suggest wrapper scripts as the workaround. Named parameter substitution (e.g., `{{namespace}}`) is needed for real team adoption.

### Nice-to-Have

- **Events table.** `kubectl get events` is one of the most-used debugging commands; it should be built in.
- **PVs/PVCs.** Important for stateful workloads.
- **RBAC tables.** Roles, RoleBindings, ClusterRoles for security auditing.
- **Metrics integration.** Joining `kubectl top pods` data with resource requests would enable requests-vs-actual-usage analysis.
- **Shell completions,** especially for shortcuts.
- **Richer `--schema` output** (columns, types, source paths).

---

## Comparison to Steampipe (Kubernetes plugin)

| Capability | Kugl | Steampipe |
|---|---|---|
| Built-in resource types | pods, jobs, nodes + labels/taints | All standard K8s types |
| SQL dialect | SQLite | PostgreSQL (full) |
| CPU/memory type handling | Auto-converted to numerics | Likely raw strings/JSONB |
| Adding a label column | 4 lines of YAML | Go code + rebuild + reinstall |
| Adding a new resource type | YAML `create:` block | Go plugin with K8s client call |
| Ecosystem integration | CLI output only | Postgres wire protocol (Grafana, psql, etc.) |
| Multi-cluster | Not supported | Aggregator plugins |
| Cross-source joins | Experimental | Core feature, 100+ plugins |
| Caching | Built-in TTL cache | Plugin-level |
| Maintenance | Personal project | Turbot-backed, active community |

Steampipe's Kubernetes plugin likely does **not** pre-convert CPU/memory strings to numerics — this appears to be a genuine and specific kugl advantage for resource utilization queries.

---

## Extension Mechanism

### Current model

Users add columns via `~/.kugl/init.yaml` or `~/.kugl/kubernetes.yaml`:

```yaml
extend:
  - table: nodes
    columns:
      - name: node_pool
        type: text
        label: karpenter.sh/nodepool      # shortcut for metadata.labels."..."
      - name: provider_id
        type: text
        path: spec.providerID             # JMESPath expression
```

Special kugl types (`size`, `age`, `cpu`, `date`) handle K8s-specific string-to-numeric conversion.

Multi-row-per-resource tables (e.g., one row per container or taint) use `row_source:` — a sequential JMESPath pipeline — with `^` prefix to reference parent-level fields.

### Friction points

1. **Two-vocabulary system (`path:` vs `label:`).** Users who don't know about `label:` write awkward quoted JMESPath: `metadata.labels."karpenter.sh/nodepool"`. The shortcut is useful but invisible until you need it.
2. **`path:` is a required key even when it's the only thing expressed.** Three keys for a conceptually one-line mapping.
3. **`row_source` + `^` parent references** are non-obvious, but affect only the minority of multi-row-per-resource cases.

### Recommended improvement: unified `from:` key

Replace `path:` / `label:` with a single `from:` key that auto-detects the extraction type:
- Value containing `/` with no leading dot-path segment → label name (matches all real K8s labels)
- Otherwise → JMESPath expression

```yaml
extend:
  - table: nodes
    columns:
      - name: node_pool
        type: text
        from: karpenter.sh/nodepool      # auto-detected as label
      - name: provider_id
        type: text
        from: spec.providerID            # auto-detected as JSON path
```

**Implementation:** add `from_` field to `UserColumn` in `config.py`; dispatch to `LabelExtractor` or `PathExtractor` in `gen_extractor` validator. Keep `path:` and `label:` for backward compatibility. Change is small and non-breaking.
