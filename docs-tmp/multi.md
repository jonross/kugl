## Extending Kugl to AWS

(So far this is just an experiment, the functionality is pretty limited.)

Using the `exec` resource type described in [Other resource types](./docs-tmp/resources.md), you can
make AWS data available for query.  For example: if `~/.kugl/ec2.yaml` contains

```yaml
resources:
  - name: instances
    exec: aws ec2 describe-instances

create:
  - table: instances
    resource: instances
    row_source:
      - Reservations
      - Instances
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

you can write

```shell
kugl "select type, zone, launched from ec2.instances where state = 'running'"
```

To make the instance data cacheable, you would need to use a cache key that varies based on your
AWS account settings, referencing something set in the environment.  Kugl will use this to generate
the cache pathname.  Example:

```yaml
resources:
  - name: instances
    exec: aws ec2 describe-instances
    cacheable: true
    cache_key: $AWS_PROFILE
```

Obviously this has limited utility, since there's no way to filter the data before it's returned.
For example, you can't add an argument to a resource `exec` command based on the query terms.
This is still being developed.

## Multi-schema queries

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