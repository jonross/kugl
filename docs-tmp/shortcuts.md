
## Saving queries

The `shortcuts` section in `~/.kugel/init.yaml` is a map from query names to lists of command-line arguments.

Example, to save the node query shown in the [README](../README.md), 
add this to `~/.kugel/init.yaml` and run `kugel nodes`.

```yaml
shortcuts:
  
  # Count nodes by instance type and distinct taint set
  nodes:
    - |
      WITH ts AS (SELECT name, group_concat(key) AS taints FROM taints
                  WHERE effect IN ('NoSchedule', 'NoExecute') GROUP BY 1)
      SELECT instance_type, count(1), taints
      FROM nodes LEFT OUTER JOIN ts ON ts.node_name = nodes.name
      GROUP BY 1, 3 ORDER BY 1, 2 DESC
```

Kugel offers this feature so you can keep all your extensions in one place.
Simple parameter substitution might be offered in the future, but if you
need more powerful templates, your own wrapper script is the short-term answer.