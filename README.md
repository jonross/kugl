# Kugel

Stop noodling with `jq`.  Explore Kubernetes resources using SQLite.

Need custom columns and tables?  Ready in minutes.

![](./docs/under-construction.jpg)

## In brief

Filtering and summarizing Kubernetes resources at the command line is a pain.
Kugel can help.

Example: find the top users of a GPU pool, based on instance type and a team-specific pod label.
With Kugel that could be

```shell
kugel -a "select owner, sum(gpu_req), sum(cpu_req)
          from pods join nodes on pods.node_name = nodes.name
          where instance_type = 'a40' and pods.status in ('Running', 'Terminating')
          group by 1 order by 2 desc limit 10"
```

Without Kugel

```shell
nodes=$(kubectl get nodes -o json | jq -r '.items[] 
        | select(.metadata.labels["beta.kubernetes.io/instance-type"] == "a40") | .metadata.name')
kubectl get pods -o json --all-namespaces | jq -r --argjson nodes "$nodes" '
  .items[]
  | select(.spec.nodeName as $node | $nodes | index($node))
  | select(.metadata.deletionTimestamp || .status.phase == "Running")
  | . as $pod | $pod.spec.containers[]
  | select(.resources.requests["nvidia.com/gpu"] != null)
  | {owner: $pod.metadata.labels["com.mycompany/job-owner"], 
     gpu: .resources.requests["nvidia.com/gpu"], 
     cpu: .resources.requests["cpu"]}
  | group_by(.owner) 
  | map({owner: .[0].owner, 
         gpu: map(.gpu | tonumber) | add, 
         cpu: map(.cpu | if test("m$") then (sub("m$"; "") | tonumber / 1000) else tonumber end) | add})
  | .[] | sort_by(-.gpu) | .[:10]'
```

## Installing

Kugel requires Python 3.9 or later, and kubectl.

**This is an alpha release.**  Please expect bugs and backward-incompatible changes.

A `pip` install isn't ready yet, and neither is Docker.  To install from source, do

```shell
git clone https://github.com/jonross/kugel
cd kugel
make reqs
PATH=${PATH}:$(pwd)/bin
```

### Test it

Report available and unavailable node counts, by instance type and taints.

```shell
kugel "with t as (select name, group_concat(key) as taints from taints
                  where effect in ('NoSchedule', 'NoExecute') group by 1)
       select instance_type, count(1), taints
       from nodes left outer join t on t.node_name = nodes.name
       group by 1, 3 order by 1, 2 desc"
```

If this query is helpful, [save it](./docs/aliases.md), then you can just run `kugel nodes`.

## How it works (important)

Kugel is just a thin wrapper on Kubectl and SQLite.  It turns `SELECT ... FROM pods`into 
`kubectl get pods -o json`, then maps fields from the response to columns
in SQLite.  If you `JOIN` to other resource tables like `nodes` it calls `kubectl get`
for those too.  If you need more columns or tables than are built in, there's a config file for that.

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

(coming soon)

* Command-line syntax
* Settings
* [Built-in tables and functions](./docs/builtins.md)
* [Adding columns and tables](./docs/extending.md)
* Adding views

## Rationale

Prior art

* [kubeql](https://github.com/saracen/kubeql) is a SQL-like query language for Kubernetes. It appears unmaintained (last commit October 2017.)
* [kube-query](https://github.com/aquasecurity/kube-query) is an [osquery](https://osquery.io/) extension. It appears unmaintained (last commit July 2020) and requires recompilation to add columns or tables.
* [ksql](https://github.com/brendandburns/ksql) is built on Node.js and AlaSQL.  It appears unmaintained (last commit November 2016.)
* [cyphernetes](https://github.com/AvitalTamir/cyphernetes) is in active development.  It uses Cypher, a graph query language.

Kugel aims to be minimalist and immediately familiar.
SQLite and `kubectl` are ubiquitous, let's build on those.

Kugel is theoretically applicable to any JSON data source, but let's not get ahead of ourselves.  :)
