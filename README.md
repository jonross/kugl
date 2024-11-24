# kubeql
Examine Kubernetes resources via SQLite

## Installation

```shell
pip install git+...
```

You should be good to go.  Try

```shell
kubeql "select name, cpu_req, command from pods where namespace = 'kube-system'"
```

## How it works (important)

KubeQL is pretty dumb.  It knows `SELECT ... FROM pods` really means 
`kubectl get pods` and then maps fields from the response JSON to columns
in SQLite.  If you `JOIN` to other resource tables like `nodes` it calls `kubectl get`
for those too.  If you need more columns than are offered out of the box,
there's a config file for that.

Because KubeQL always uses the `--all-namespaces` option to `kubectl`, it tries
to reduce strain on the Kubernetes API Server by caching responses for up to
two minutes.  This is why it often prints "Data delayed up to ..." messages.
You can suppress that warning with the `-r` / `--reckless` option, or force it
to always update the cache with the `-u` / `--update` option.  In any case, please
be cognizant of stale data and server load.

