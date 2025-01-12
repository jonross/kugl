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
      - name: private_dns
        path: PrivateDnsName
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
and then pipe the output of any command to Kugl.  `file:` also works with any pathname, and supports
environment variable subtitution using `Path.expandvars` as described
[here](https://docs.python.org/id/3.5/library/os.path.html#os.path.expandvars).

You can also join across schemas.  For example, given the above `instances` table, report on the
capacity per zone in an EKS cluster:

```shell
kugl "SELECT e.zone, sum(n.cpu_alloc) as cpus, sum(n.gpu_alloc) as gpus
      FROM kubernetes.nodes n
      JOIN ec2.instances e ON n.name = e.hostname
      GROUP BY 1
```

Note the explicit use of a `kubernetes.` schema prefix.  This is required when joining across schemas.
(While `kubernetes` is the default schema, you can't always rely on SQLite's search behavior for
unqualified table names.  It's better to be explicit.)