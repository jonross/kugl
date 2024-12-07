
## Saving queries

The `alias` section in `~/.kugel/init.yaml` is a map from query names to lists of command-line arguments.

Example, to save the node query in Kugel's README, add this to `~/.kugel/init.yaml` and run `kugel nodes`.

```yaml
alias:
  
  # Count nodes by instance type and scheduling taint
  nodes:
    - -a
    - |
      WITH t AS (SELECT name, group_concat(key) AS noschedule FROM taints
                 WHERE effect = 'NoSchedule' GROUP BY 1)
      SELECT instance_type, count(1), noschedule
      FROM nodes LEFT OUTER JOIN t ON t.node_name = nodes.name
      GROUP BY 1, 3 ORDER BY 1, 2 DESC
```

Kugel offers this feature so you can keep all your extensions in one place.
Simple parameter substitution might be offered in the future, but if you
need more powerful templates, your own wrapper script is the short-term answer.