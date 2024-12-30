
## Adding columns to an existing table

To extend a table, use the `extend:` section in `~/.kugl/init.yaml`.  This is a list of table names,
each with a list of new columns.  An extension column specifies the column name, its
SQLite type (one of `int`, `real`, `text`) and a [JMESPath](https://jmespath.org/)
expression showing how to extract the column value from the JSON form of the resource.

Example

```yaml
extend:
  
  # Add the "owner" column to the pods table as shown in the Kugl README
  
- table: pods
  columns:
  - name: owner
    type: text
    path: metadata.labels."com.mycompany/ml-job-owner"
        
  # Using Karpenter on AWS?  Add the Karpenter node pool and AWS provider ID
  # to the nodes table.
  
- table: nodes
  columns:
  - name: node_pool
    type: text
    path: metadata.labels."karpenter.sh/nodepool"
  - name: provider_id
    type: text
    path: spec.providerID
```

## Adding a new table

This works just like extending a table, with these differences
* Use the `create:` section rather than `extend:`
* Provide the name of the resource argument to `kubectl get`
* If the resource isn't built in (like `pods` or `nodes`), declare the resource and indicate whether it's namespaced.

Example: this defines a new resource type and table for Argo workflows.

```yaml
resources:
- name: workflows
  namespaced: true

create:
- table: workflows
  resource: workflows
  columns:
  - name: name
    type: text
    path: metadata.name
  - name: namespace
    type: text
    path: metadata.namespace
  - name: status
    type: text
    path: metadata.labels."workflows.argoproj.io/phase"
```

## Column extractors and defaults

You've seen how the `path` extractor works, using JMESPath to identify an element in
the response JSON.  You can also use the `label` extractor, which is a shortcut to
`metadata.labels`.

In addition, resources are namespaced by default, and the default column type is `text`.
Here's a more concise way of defining the `workflows` table, above

```yaml
resources:
  - name: workflows
  
create:
  - table: workflows
    resource: workflows
    columns:
      - name: name
        path: metadata.name
      - name: namespace
        path: metadata.namespace
      - name: status
        label: workflows.argoproj.io/phase
```

## Parsing data into numeric columns

`kubectl` response values like `50Mi` (of memory) are pretty useless in queries, since you can't treat 
them numerically.  Kugl fixes this, offering additional data types that can be used in the `type` field 
of a column definition and automatically convert response values.

| Kugl type | SQLite type  | Description                                                                 |
|------------|--------------|-----------------------------------------------------------------------------|
| `size`     | `INTEGER`    | Memory size in bytes; accepts values like `50Mi`                            |
| `age`      | `INTEGER`    | Time delta in seconds; accepts values like `5d` or `4h30m`                  |
| `cpu`      | `REAL`       | CPU limit or request; accepts values like `0.5` or `300m`                   |
| `date`     | `INTEGER`    | Unix epoch timestamp in seconds; accepts values like `2021-01-01T12:34:56Z` |

## Generating multiple rows per respone item

It's rare for a `kubectl get` response item to map directly to a single row in a table.  For example,
a node can have multiple taints, and a pod can have multiple containers.  Kugl handles this using
the `row_source` field in a column definition.  Here's how the `node_taints` built-in table is defined.

```yaml
create:
  - table: node_taints
    resource: nodes
    row_source:
      - items
      - spec.taints
    columns:
      - name: node_name
        path: ^metadata.name
      - name: key
        path: key
      - name: effect
        path: effect
```

Each element in `row_source` is a JMESPath expression that selects items relative to the prior selector.
Only the last element in the list is used to generate a row, but `path`s can refer to any part of the chain.
Each `"^"` at the start of a `path` refers to the part of the response one level higher than the bottom
`row_source` element.  In this case

* `^metadata.name` means the `.metadata.name` in each element of the response `items` array
* `key` and `effect` refer to each taint in the `spec.taints` array

## Coming soon

Write column extractors and table generators in Python.