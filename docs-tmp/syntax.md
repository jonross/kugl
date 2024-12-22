
## Usage

```shell
kugel [options] [sql | shortcut]
```

Kubernetes options (these are given to `kubectl`)

* `-a, --all-namespaces` - Look in all namespaces for Kubernetes resources.  May not be combine with `-n`.
* `-n, --namespace NS` - Look in namespace `NS` for Kubernetes resources.  May not be combined with `-a`.

Cache control

* `-c, --cache` - Always use cached data, if available, regardless of its age
* `-r, --reckless` - Don't print stale data warnings
* `-t, --timeout AGE` - Change the expiration time for cached data, e.g. `5m`, `1h`; the default is `2m` (two minutes)
* `-u, --update` - Always updated from `kubectl`, regardless of data age
