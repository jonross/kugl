
## Saving queries

The `shortcuts` section in `~/.kugel/init.yaml` is a map from query names to lists of command-line arguments.

Example, to save the node query shown in the [README](../README.md), 
add this to `~/.kugel/init.yaml` and run `kugel hi-mem`.

```yaml
shortcuts:
  
  hi-mem:
    - |
      SELECT name, to_size(mem_req) FROM pods 
      ORDER BY mem_req DESC LIMIT 15
```

Kugl offers this feature so you can keep all your extensions in one place.
Simple parameter substitution might be offered in the future, but if you
need more powerful templates, your own wrapper script is the short-term answer.