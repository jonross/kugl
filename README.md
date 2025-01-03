# Kugl

Explore Kubernetes resources using SQLite.

## Example

Find the top users of a GPU pool, based on instance type and a team-specific pod label.

With Kugl (and a little configuration)

```shell
kugl -a "select owner, sum(gpu_req), sum(cpu_req)
         from pods join nodes on pods.node_name = nodes.name
         where instance_type like 'g5.%large' and pods.phase in ('Running', 'Pending')
         group by 1 order by 2 desc limit 10"
```

With `kubectl` and `jq`

```shell
kubectl get pods -o json --all-namespaces | 
jq -r --argjson nodes "$(kubectl get nodes -o json | jq '[.items[] 
        | select((.metadata.labels["node.kubernetes.io/instance-type"] // "") | test("g5.*large")) 
        | .metadata.name]')" \
  '[ .items[]
    | select(.spec.nodeName as $node | $nodes | index($node))
    | select(.status.phase == "Running" or .status.phase == "Pending")
    | . as $pod | $pod.spec.containers[]
    | select(.resources.requests["nvidia.com/gpu"] != null)
    | {owner: $pod.metadata.labels["com.mycompany/job-owner"], 
       gpu: .resources.requests["nvidia.com/gpu"], 
       cpu: .resources.requests["cpu"]}
  ] | group_by(.owner) 
  | map({owner: .[0].owner, 
         gpu: map(.gpu | tonumber) | add, 
         cpu: map(.cpu | if test("m$") then (sub("m$"; "") | tonumber / 1000) else tonumber end) | add})
  | sort_by(-.gpu) | .[:10] | .[]
  | "\(.owner) \(.gpu) \(.cpu)"'
```

## Installing

Kugl requires Python 3.9 or later, and kubectl.

**This is an alpha release.**  Please expect bugs and backward-incompatible changes.

If you don't mind Kugl cluttering your Python with its [dependencies](./reqs_public.txt):

```shell
pip install kugl
```

If you do mind, there's a Docker image; `mkdir ~/.kugl` and use this Bash alias.  (Sorry, this is an x86 image,
I don't have multiarch working yet.)

```shell
kugl() {
    docker run \
        -v ~/.kube:/root/.kube \
        -v ~/.kugl:/root/.kugl \
        jonross/kugl:0.3.2 python3 -m kugl.main "$@"
}
```

If neither of those suits you, it's easy to set up from source.  (This will build a virtualenv in the
directory where you clone it.)

```shell
git clone https://github.com/jonross/kugl.git
cd kugl
make deps
# put kugl's bin directory in your PATH
PATH=${PATH}:$(pwd)/bin
```

### Test it

Find the pods using the most memory:

```shell
kugl -a "select name, to_size(mem_req) from pods order by mem_req desc limit 15"
```

If this query is helpful, [save it](./docs-tmp/shortcuts.md), then you can run `kugl hi-mem`.

Please also see the [recommended configuration](./docs-tmp/recommended.md).

## How it works (important)

Kugl is just a thin wrapper on Kubectl and SQLite.  It turns `SELECT ... FROM pods` into 
`kubectl get pods -o json`, then maps fields from the response to columns
in SQLite.  If you `JOIN` to other resource tables like `nodes` it calls `kubectl get`
for those too.  If you need more columns or tables than are built in as of this release,
there's a config file for that.

Because Kugl always fetches all resources from a namespace (or everything, if 
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
* [Recommended configuration](./docs-tmp/recommended.md)
* [Settings](./docs-tmp/settings.md)
* [Built-in tables and functions](./docs-tmp/builtins.md)
* [Configuring new columns and tables](./docs-tmp/extending.md)
* [Troubleshooting and feedback](./docs-tmp/trouble.md)
* [Beyond Kubernetes](./docs-tmp/beyond.md)
* [License](./LICENSE)

### Pronunciation

Like "cudgel", so, a blunt instrument for convincing data to be row-shaped.

Or "koo-jull", if you prefer something less combative.

"Kugel" is a casserole with varying degrees of cultural significance, and sounds too much like "Google".

### Rationale

Kugl won't replace everyday use of `kubectl`; it's more for ad-hoc queries and reports, where the
cognitive overhead of `kubectl | jq` is an obstacle.  In that context, full SQL support and user-defined
tables are essential, and it is where Kugl hopes to go a step further than prior art.

Some other implementations of SQL-on-Kubernetes:

* [ksql](https://github.com/brendandburns/ksql) is built on Node.js and AlaSQL; last commit November 2016.
* [kubeql](https://github.com/saracen/kubeql) is a SQL-like query language for Kubernetes; last commit October 2017.
* [kube-query](https://github.com/aquasecurity/kube-query) is an [osquery](https://osquery.io/) extension; last commit July 2020.

## Contributors

* [Elliot Miller](https://github.com/bitoffdev)