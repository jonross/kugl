# kubeql
Examine Kubernetes resources via SQLite

**UNDER CONSTRUCTION**

Because why 

```shell
kubectl get jobs -o json --all-namespaces | jq -r ' 
    .items[] 
    | select( (.status.conditions[]? | select(.type == "Suspended" and .status == "True")) ) 
    | select( ([.spec.template.spec.containers[]?.resources.requests.cpu // "0"] 
               | map( if test("m$") then (.[:-1] | tonumber / 1000) else tonumber end ) | add) > 6 ) 
    | "\(.metadata.name) \(.metadata.labels["com.mycompany/job-owner"])"
'
```

when you could

```shell
kubeql "select name, owner from jobs where cpu_req > 6 and status = 'Suspended'"
```

## Installation

**UNDER CONSTRUCTION**

  Try

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
You can suppress that warning with the `-r` / `--reckless` option, or
force a cache update with the `-u` / `--update` option.

In any case, please be cognizant of stale data and server load.

