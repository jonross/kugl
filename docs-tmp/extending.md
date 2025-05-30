
## Note

Configuration files should be protected to the same degree as your shell scripts and anything
on your `PYTHONPATH.`  Kugl will refuse to read a configuration file that is world-writable.

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
    # Comments are optional; you can see these with 'kugl --schema'
    comment: ML team member who submitted the work
        
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
      - name: uid
        type: text
        path: metadata.uid
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
`metadata.labels`, and can either be a single string or a list of labels to check in order

There are some useful defaults as well:
* resources are namespaced by default
* resources in `kubernetes.yaml` default to type `kubernetes`
* the default column type is `text`

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
      - name: uid
        path: metadata.uid
      - name: namespace
        path: metadata.namespace
      - name: status
        label: workflows.argoproj.io/phase
```

## Parsing data into numeric columns

`kubectl` response values like `50Mi` (of memory) are unhelpful in queries, since you can't treat 
them numerically.  Kugl fixes this, offering additional data types that can be used in the `type` field 
of a column definition and automatically convert response values.

| Kugl type | SQLite type  | Description                                                                 |
|------------|--------------|-----------------------------------------------------------------------------|
| `size`     | `INTEGER`    | Memory size in bytes; accepts values like `50Mi`                            |
| `age`      | `INTEGER`    | Time delta in seconds; accepts values like `5d` or `4h30m`                  |
| `cpu`      | `REAL`       | CPU limit or request; accepts values like `0.5` or `300m`                   |
| `date`     | `INTEGER`    | Unix epoch timestamp in seconds; accepts values like `2021-01-01T12:34:56Z` |

## Generating multiple rows per response item

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
      - name: node_uid
        path: ^metadata.uid
      - name: key
        path: key
      - name: effect
        path: effect
```

Each element in `row_source` is a JMESPath expression that selects items relative to the prior selector.
Only the last element in the list is used to generate a row, but `path`s can refer to any part of the chain.
Each `"^"` at the start of a `path` refers to the part of the response one level higher than the bottom
`row_source` element.  In this case

* `^metadata.uid` means the `.metadata.uid` in each element of the response `items` array
* `key` and `effect` refer to each taint in the `spec.taints` array

The default `row_source` is just `items`, which is why the example `workflows` table shown earlier doesn't
need to specify it.

This syntax also applies to the `label` extractor.  For example, if the `row_source` of a table needs to
address Job metadata but also metadata from the Job pod template, you can write this:

```yaml
  ...
  resource: jobs
  row_source:
    - items
    - spec.template
  columns:
    - name: label_from_job
      label: ^a-job-label
    - name: label_from_pod
      label: a-pod-label
```

### More about row_source

In detail, here's how `row_source` is handled.
* Begin with a list containing a single element, which is the entire response JSON.
* Apply the first `row_source` expression to each element of this list to build a new list
    * If the expression yields a non-list result, add it to the new list
    * If the expression yields a list, add each item (not the whole list) to the new list
    * In either case, establish a parent / child relationship between the old and new items
* Repeat with each successive `row_source` entry.

This can produce surprising results if one step in the `row_source` list tries to do too much.
Let's say the `node_taints` table didn't need a `^metadata.uid` reference, so only requires the
taint lists.  This source list would not work, because `.spec` is not a child of `.items`.

```yaml
row_source:
  - items.spec.taints
```

Addressing each element in `items` requires a JMESpath [projection](https://jmespath.org/tutorial.html#projections),
in this case `items[*].spec`.  Continuing this with `.taints` in a single expression will then create a list of lists
that must be flattened:

```yaml
row_source:
  - items[*].spec.taints[]
```

Although the multi-step `row_source` is incrementally slower for large lists, it's clearly less error-prone than
projecting and flattening, so is the recommended approach.

As noted in [Troubleshooting](./trouble.md), running with `--debug itemize` will show the intermediate results of
`row_source` processing.

### Extracting from dicts

JMESPath lacks adequate support for addressing dictionaries.  For example, if you want to build a table of
keys and values from environmet settings in YAML, there is no construct that will give you key-value pairs
from the fragment below.  You can get the keys, or the values, but not both.

```yaml
...
env:
  AWS_BUCKET_NAME: my_budket
  AWS_REGION: us-east-1
  ...
```

Kugl has a simple workaround for this.  A `row_source` entry can have additional processing options, and for any row 
source entry that addresses a dictionary, you can add the option `"kv"` to get key-value pairs.  For example, if you
have adressed the above YAML data with

```yaml
row_source:
 - env
```

Change this to

```yaml
row_source:
  - env; kv
```

and Kugl will present the dictionary as if the data source originally looked like this:

```yaml
env:
  - key: AWS_BUCKET_NAME
    value: my_bucket
  - key: AWS_REGION
    value: us-east-1
```

It's then straightforward to take columns from these items with

```yaml
columns:
  - name: variable
    path: key
  - name: value
    path: value
```

## Tips

If creating multiple tables from a resource, you should use the `uid` column (sourced from `metadata.uid`)
as a join key, since this is a guaranteed unique key.

The `utils:` section of `~/.kugl/init.yaml` is ignored during configuration parsing, so you can use it to store
reusable bits of YAML.