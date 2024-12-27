
## Recommended configuration

Instance type is a useful column to have in the `nodes` table. Unfortunately, there is no standard
label for it.  You can fix this with configuration.  In `~/.kugel/kubernetes.yaml`, add

```yaml
extend:
  - table: nodes
    columns:
      - name: instance_type
        label:
          - node.kubernetes.io/instance-type
          - beta.kubernetes.io/instance-type
```

This will handle common cases.  If your cluster uses a different label, add it to the list.
You can use Kugel itself to explore what's available, for example:

```shell
kugel "select distinct key from node_labels where key like '%instance-type%'"
```

Once you've set up the correct labels, here's a handy report that reports available capacity,
partitioning nodes by distinct instance type and `NoSchedule` / `NoExecute` taints:

```shell
kugel "
    WITH t AS (
        SELECT node_uid, group_concat(key) AS taints FROM node_taints
        WHERE effect IN ('NoSchedule', 'NoExecute') GROUP BY 1
    )
    SELECT instance_type, count(1) AS count, sum(cpu_alloc) AS cpu, sum(gpu_alloc) AS gpu, t.taints
    FROM nodes LEFT OUTER JOIN t ON t.node_uid = nodes.uid
    GROUP BY 1, 5 ORDER BY 1, 5
"
```
