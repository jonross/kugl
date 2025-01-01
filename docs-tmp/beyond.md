## Defining tables on any JSON data

(This is just an experiment and guaranteed to change.)

You can define tables against any source of JSON, not just Kubernetes resources. 
Example: if `~/.kugl/ec2.yaml` contains

```yaml
resources:
  - name: instances
    exec: aws ec2 describe-instances

create:
  - table: instances
    resource: instances
    row_source:
      - Reservations[*].Instances[]
    columns:
      - name: type
        path: InstanceType
      - name: zone
        path: Placement.AvailabilityZone
      - name: state
        path: State.Name
      - name: launched
        path: LaunchTime
```

you can write (matching the table prefix to the config file)

```shell
kugl "select type, zone, launched from ec2.instances where state = 'running'"
```

Obviously this has limited utility, since there's no way to filter the data before it's returned.
For example, you can't add an argument to a resource `exec` command based on the query terms.

As an alternative, you can define a resource to use `file: stdin` instead of `exec: some command`,
and then pipe the output of any command to Kugl.