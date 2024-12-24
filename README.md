# Kugel

Stop noodling with `jq`.  Explore Kubernetes resources using SQLite.

## Example

Find the top users of a GPU pool, based on instance type and a team-specific pod label.

With Kugel this could be

```shell
kugel -a "select owner, sum(gpu_req), sum(cpu_req)
          from pods join nodes on pods.node_name = nodes.name
          where instance_type = 'a40' and pods.status in ('Running', 'Terminating')
          group by 1 order by 2 desc limit 10"
```

Without Kugel

```shell
nodes=$(kubectl get nodes -o json | jq '[.items[] 
        | select(.metadata.labels["beta.kubernetes.io/instance-type"] == "a40") | .metadata.name]')
kubectl get pods -o json --all-namespaces | jq -r --argjson nodes "$nodes" '
  [ .items[]
    | select(.spec.nodeName as $node | $nodes | index($node))
    | select(.status.phase == "Running" or 
             (.metadata.deletionTimestamp != null and .status.phase != "Succeeded" and .status.phase != "Failed"))
    | . as $pod | $pod.spec.containers[]
    | select(.resources.requests["nvidia.com/gpu"] != null)
    | {owner: $pod.metadata.labels["com.mycompany/job-owner"], 
       gpu: .resources.requests["nvidia.com/gpu"], 
       cpu: .resources.requests["cpu"]}
  ] | group_by(.owner) 
  | map({owner: .[0].owner, 
         gpu: map(.gpu | tonumber) | add, 
         cpu: map(.cpu | if test("m$") then (sub("m$"; "") | tonumber / 1000) else tonumber end) | add})
  | sort_by(-.gpu) | .[:10]
  | "\(.gpu) \(.cpu) \(.owner)"'

```

## Installing

Kugel requires Python 3.9 or later, and kubectl.

**This is an alpha release.**  Please expect bugs, lackluster performance, and backward-incompatible changes.

To install with `pip`:

```shell
pip install kugel
```

To use via docker, `mkdir ~/.kugel` then use this Bash alias.  (Sorry, this is an x86 image, I don't have
multiarch working yet.)

```shell
kugel() {
    docker run \
        -v ~/.kube:/root/.kube \
        -v ~/.kugel:/root/.kugel \
        jonross/kugel:0.2.0 python3 -m kugel.main "$@"
}
```

If neither of those suits you, it's easy to set up from source.  (This will build a virtualenv in the
source directory.)

```shell
git clone https://github.com/jonross/kugel.git
cd kugel
make deps
# put kugel's bin directory in your PATH
PATH=${PATH}:$(pwd)/bin
```

### Test it

Find the pods using the most memory:

```shell
kg -a "select name, to_size(mem_req) from pods order by mem_req desc limit 15"
```

If this query is helpful, [save it](./docs-tmp/shortcuts.md), then you can run `kugel hi-mem`.

## How it works (important)

Kugel is just a thin wrapper on Kubectl and SQLite.  It turns `SELECT ... FROM pods` into 
`kubectl get pods -o json`, then maps fields from the response to columns
in SQLite.  If you `JOIN` to other resource tables like `nodes` it calls `kubectl get`
for those too.  If you need more columns or tables than are built in as of this release,
there's a config file for that.

Because Kugel always fetches all resources from a namespace (or everything, if 
`-a/--all-namespaces` is used), it tries
to ease Kubernetes API Server load by **caching responses for 
two minutes**.  This is why it often prints "Data delayed up to ..." messages.

Depending on your cluster activity, the cache can be a help or a hindrance.
You can suppress the "delayed" messages with the `-r` / `--reckless` option, or
always update data using the `-u` / `--update` option.  These behaviors, and
the cache expiration time, can be set in the config file as well.

In any case, please be mindful of stale data and server load.

## Learn more

* [Command-line syntax](./docs-tmp/syntax.md)
* [Settings](./docs-tmp/settings.md)
* [Built-in tables and functions](./docs-tmp/builtins.md)
* [Configuring new columns and tables](./docs-tmp/extending.md)
* Adding columns and tables from Python (coming soon)
* Adding views (coming soon)
* [Troubleshooting and feedback](./docs-tmp/trouble.md)
* [License](./LICENSE)

## Rationale

`jq` is awesome, but... can you join and group without looking at the manual? Can you do math on non-numeric
data like "500Mi" of memory or "200m" CPUs or "2024-11-01T12:34:56Z"?  Can you determine the STATUS of a pod
the way `kubectl get pods` does?

Probably not.  Kugel can help.

Prior art:

* [ksql](https://github.com/brendandburns/ksql) is built on Node.js and AlaSQL.  It appears unmaintained (last commit November 2016.)
* [kubeql](https://github.com/saracen/kubeql) is a SQL-like query language for Kubernetes. It appears unmaintained (last commit October 2017.)
* [kube-query](https://github.com/aquasecurity/kube-query) is an [osquery](https://osquery.io/) extension. It appears unmaintained (last commit July 2020) and requires recompilation to add columns or tables.
* [cyphernetes](https://github.com/AvitalTamir/cyphernetes) is in active development and looks viable, but it uses Cypher (a graph query language) and I'd like SQL.

Kugel hopes to be minimalist and immediately familiar.
SQLite ships with Python, and if you're reading this you have `kubectl`, so let's build on those.