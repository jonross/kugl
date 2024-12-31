## Defining tables on any JSON data

(This is a random experiment and guaranteed to change.)

You can define tables against source of JSON, not just Kubernetes resources. 
Example: if `~/.kugl/iam.yaml` contains

```yaml
resources:
  - name: groups
    exec: aws iam list-groups

create:
  - table: groups
    resource: groups
    row_source:
      - Groups
    columns:
      - name: arn
        path: Arn
      - name: created
        type: date
        path: CreateDate
```

you can write (matching the table prefix to the config file)

```shell
kugl "select arn, to_utc(created) from iam.groups"
```

Obviously this has limited utility, since there's no way to filter the data before it's returned.
For example, you can't add an argument to a resource `exec` command based on the query terms.