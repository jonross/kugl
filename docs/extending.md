
## Adding columns to an existing table

To extend a table, use the `extend:` section in `~/.kugel/init.yaml`.  This is a list of table names,
each with a list of new columns.  An extension column specifies the column name, its
SQLite type (one of `int`, `real`, `text`) and a [JMESPath](https://jmespath.org/)
expression showing how to extract the column value from the JSON form of the resource.

Example

```yaml
extend:
  
  # Add the "owner" column to the pods table as shown in the Kugel README
  
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
* Indicate whether resource is namespaced

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

## Coming very soon

Generate multiple rows from one `kubectl get` response item.
(This is done internally for the taints table, but it's not available to extensions.)

Write column extractors and table generators in Python.