Kugl
====

Explore Kubernetes resources using SQLite.

Example
-------

Find the top users of a GPU pool, based on instance type and a
team-specific pod label.

With Kugl (and a bit of configuration for owner and instance type)

.. code:: shell

   kugl -a "select owner, sum(gpu_req), sum(cpu_req)
            from pods join nodes on pods.node_name = nodes.name
            where instance_type like 'g5.%large' and pods.phase in ('Running', 'Pending')
            group by 1 order by 2 desc limit 10"

With ``kubectl`` and ``jq``, that's a little more work:

.. code:: shell

   kubectl get pods -o json --all | 
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

Installing
----------

Kugl requires Python 3.9 or later, and kubectl.

**This is an alpha release.** Please expect bugs and
`backward-incompatible changes <docs/breaking.rst>`__

If you don't mind Kugl cluttering your Python with its
`dependencies <./reqs_public.txt>`__:

.. code:: shell

   pip install kugl

If you do mind, there's a Docker image; ``mkdir ~/.kugl`` and use this
Bash alias.

.. code:: shell

   kugl() {
       docker run \
           -v ~/.kube:/root/.kube \
           -v ~/.kugl:/root/.kugl \
           jonross/kugl:0.7.0 python3 -m kugl.main "$@"
   }

If neither of those suits you, it's easy to set up from source:

.. code:: shell

   git clone https://github.com/jonross/kugl.git
   cd kugl

   # Install UV if you don't have it
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Set up development environment
   uv sync

   # Run kugl directly
   uv run kugl --help
   # or put kugl's bin directory in your PATH
   PATH=${PATH}:$(pwd)/bin

Test it
~~~~~~~

Find the pods using the most memory:

.. code:: shell

   kugl -a "select namespace, name, to_size(mem_req) from pods order by mem_req desc limit 15"

If this query is helpful, `save it <docs/shortcuts.rst>`__, then
you can run ``kugl hi-mem``.

Please also see the `recommended
configuration <docs/recommended.rst>`__.

How it works (important)
------------------------

Kugl is just a thin wrapper on Kubectl and SQLite. It turns
``SELECT ... FROM pods`` into ``kubectl get pods -o json``, then maps
fields from the response to columns in SQLite. If you ``JOIN`` to other
resource tables like ``nodes`` it calls ``kubectl get`` for those too.
If you need more columns or tables than are built in as of this release,
there's a config file for that.

Because Kugl always fetches all resources from a namespace (or
everything, if ``-a/--all`` is used), it tries to ease Kubernetes API
Server load by **caching responses for two minutes**. This is why it
often prints "Data delayed up to ..." messages.

Depending on your cluster activity, the cache can be a help or a
hindrance. You can suppress the "delayed" messages with the ``-r`` /
``--reckless`` option, or always update data using the ``-u`` /
``--update`` option. These behaviors, and the cache expiration time, can
be set in the config file as well.

In any case, please be mindful of stale data and server load.

.. BEGIN_LEARN_MORE

Learn more
----------

- `Command-line syntax <docs/syntax.rst>`__
- `Recommended configuration <docs/recommended.rst>`__
- `Settings <docs/settings.rst>`__
- `Shortcuts <docs/shortcuts.rst>`__
- `Built-in tables and functions <docs/builtins.rst>`__
- `Configuring new columns and tables <docs/extending.rst>`__
- `Troubleshooting and feedback <docs/trouble.rst>`__
- Beyond Kubernetes and kubectl

  - `Other resource types <docs/resources.rst>`__
  - `Additional schemas <docs/multi.rst>`__

- `Release notes <./CHANGELOG.md>`__
- `Breaking changes <docs/breaking.rst>`__
- `License <./LICENSE>`__

.. END_LEARN_MORE

Pronunciation
~~~~~~~~~~~~~

Like "cudgel", so, a blunt instrument for convincing data to be
row-shaped.

Or "koo-jull", if you prefer something less combative.

"Kugel" is a casserole with varying degrees of cultural significance,
and sounds too much like "Google".

Rationale
~~~~~~~~~

Kugl won't replace everyday use of ``kubectl``; it's more for ad-hoc
queries and reports, where the cognitive overhead of ``kubectl | jq`` is
an obstacle. In that context, full SQL support and user-defined tables
are essential, and it is where Kugl hopes to go a step further than
prior art.

Some other implementations of SQL-on-Kubernetes:

- `ksql <https://github.com/brendandburns/ksql>`__ is built on Node.js
  and AlaSQL; last commit November 2016.
- `kubeql <https://github.com/saracen/kubeql>`__ is a SQL-like query
  language for Kubernetes; last commit October 2017.
- `kube-query <https://github.com/aquasecurity/kube-query>`__ is an
  `osquery <https://osquery.io/>`__ extension; last commit July 2020.

Contributors
------------

- `Elliot Miller <https://github.com/bitoffdev>`__
