
It's easy to add columns to built-in tables, or define new tables.
This is done in your configuration file (`~/.kugel/init.yaml`)

## Adding columns to an existing table

To extend a table, use the `extend:` section.  This is a dictionary of table names,
each with a list of new columns.  An extension column specifies the column name, its
SQLite type (one of `int`, `real`, `text`) and a [JMESPath](https://jmespath.org/)
expression showing how to extract the column value from the JSON form of the resource.

Example

```yaml
extend:
  
  # Add the "owner" column to the pods table as shown in the Kugel README
  
  pods:
    columns:
      owner:
        type: text
        path: metadata.labels."com.mycompany/ml-job-owner"
        
  # Using Karpenter on AWS?  Add the Karpenter node pool and AWS provider ID
  # to the nodes table.
  
  nodes:
    columns:
      node_pool:
        type: text
        path: metadata.labels."karpenter.sh/nodepool"
      provider_id:
        type: text
        path: spec.providerID
```

## Adding a new table

This works just like extending a table, with these differences
* Use the `create:` section rather than `extend:`
* Provide the name of the resource argument to `kubectl get`
* Indicate whether resource is namespaced

Example

```yaml
create:
  
  # Add a table to capture Argo workflows
  
  workflows:
    resource: workflows
    namespaced: true
    columns:
      name:
        type: text
        path: metadata.name
      namespace:
        type: text
        path: metadata.namespace
      status:
        type: text
        path: metadata.labels."workflows.argoproj.io/phase"
```

## Column extractors and defaults

You've seen how the `path` extractor works, using JMESPath to identify an element in
the response JSON.  You can also use the `label` extractor, which is a shortcut to
`metadata.labels`.

In addition, there are obvious defaults for some fields.
* The default resource name is the name of the table
* The default for the `namespaced` field is `true`
* The default column type is `text`

Here's a more concise way of defining the `workflows` table, above

```yaml
  workflows:
    columns:
      name:
        path: metadata.name
      namespace:
        path: metadata.namespace
      status:
        label: workflows.argoproj.io/phase
```

## Features planned

Generate multiple rows from one `kubectl get` response item.
(We do this internally for taints, but it's not available for extensions.)

Write column extractors in Python (warning: security hole.)