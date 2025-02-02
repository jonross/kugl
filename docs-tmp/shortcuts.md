
## Saving queries

The `shortcuts` section in `~/.kugl/init.yaml` is a map from query names to lists of command-line arguments.

Example, to save the queries shown in the [README](../README.md) and in 
[recommended configuration](./recommended.md), add this to `~/.kugl/init.yaml`:

```yaml
shortcuts:
  
  - name: hi-mem
    args:
      - |
        SELECT name, to_size(mem_req) FROM pods 
        WHERE phase = 'Running'
        ORDER BY mem_req DESC LIMIT 15

  - name: nodes
    # Comment field is optional
    comment: Schedulable vs unschedulable capacity
    args:
      - |
        WITH t AS (
          SELECT node_uid, group_concat(key) AS taints FROM node_taints
          WHERE effect IN ('NoSchedule', 'NoExecute') GROUP BY 1
        )
        SELECT instance_type, count(1) AS count, sum(cpu_alloc) AS cpu, sum(gpu_alloc) AS gpu, t.taints
        FROM nodes LEFT OUTER JOIN t ON t.node_uid = nodes.uid
        GROUP BY 1, 5 ORDER BY 1, 5
```

To run, type `kugl hi-mem` or `kugl nodes`.

Simple parameter substitution might be offered in the future, but if you
need more powerful templates, your own wrapper script is the short-term answer.