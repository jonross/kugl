
## Note

Configuration files should be protected to the same degree as your shell scripts and anything
on your `PYTHONPATH.`  Kugl will refuse to read a configuration file that is world-writable.

## Settings

The `settings` section in `~/.kugl/init.yaml` can be used to specify cache behaviors once,
rather than on every usage from the command line.  Example:

```yaml
settings:
  cache_timeout: 5m
  reckless: true
```