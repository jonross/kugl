# kubeql
View Kubernetes resources through the lens of SQLite

## Rationale

Filtering and summarizing Kubernetes resources at the command line is a pain.
KubeQL can help.  Compare

```shell
kubeql -a "select sum(gpu_req), owner
          from pods join nodes on pods.node_name = node.name
          where nodes.instance_type = 'a40' and pods.status in ('Running', 'Terminating')
          group by owner"
```

with the equivalent kubectl / jq pipeline

```shell
nodes=$(kubectl get nodes -o json | jq -r '.items[] 
        | select(.metadata.labels["beta.kubernetes.io/instance-type"] == "a40") | .metadata.name')
kubectl get pods -o json --all-namespaces | jq -r --argjson nodes "$nodes" '
  .items[]
  | select(.spec.nodeName as $node | $nodes | index($node))
  | select(.status.phase == "Running")
  | . as $pod | $pod.spec.containers[]
  | select(.resources.requests["nvidia.com/gpu"] != null)
  | {owner: $pod.metadata.labels["com.mycompany/job-owner"], 
     gpu: .resources.requests["nvidia.com/gpu"], 
     cpu: .resources.requests["cpu"]}
  | group_by(.owner) 
  | map({owner: .[0].owner, 
         gpu: map(.gpu | tonumber) | add, 
         cpu: map(.cpu | sub("m$"; "") | tonumber / (if test("m$") then 1000 else 1 end)) | add})
  | .[] | "\(.owner) \(.gpu) \(.cpu)"'
```

## Installing

If you don't mind KubeQL cluttering your Python with its [dependencies](./requirements.txt), run

```
pip install ...
```

If you do, here's a shell alias to use the Docker image

```shell
kubeql() {
    docker run \
        -v $HOME/.kube:/root/.kube 
        -v $HOME/.kubeql:/root/.kubeql \
        "$@"
}
```

## How it works (important)

KubeQL is simple-minded.  It knows `SELECT ... FROM pods` really means 
`kubectl get pods -o json`, and it maps fields from the response to columns
in SQLite.  If you `JOIN` to other resource tables like `nodes` it calls `kubectl get`
for those too.  If you need more columns or tables than are built in, there's a config file for that.

Because KubeQL always fetches all resources from a namespace (or everything, if 
`-a/--all-namespaces` is used), it tries
to ease Kubernetes API Server load by **caching responses for 
two minutes**.  This is why it often prints "Data delayed up to ..." messages.

Depending on your cluster size, the cache can be a help or a hindrance.
You can suppress the "delayed" messages with the `-r` / `--reckless` option, or
always update data using the `-u` / `--update` option.  These behaviors, and
the cache expiration time, can be set in the config file as well.

In any case, please be mindful of stale data and server load.

## Learn more

(coming soon)

* Command-line syntax
* Settings
* [Built-in tables and functions](./docs/builtins.md)
* Canned queries and views
* Adding columns to built-in tables
* Adding tables for other resources

