Kugl
====

Explore Kubernetes resources using SQLite.

Example
-------

Report memory pressure by node — how much memory is requested by running and initializing
pods, versus what each node can allocate.  Kugl understands Kubernetes memory and CPU
units natively, and offers ``kubectl``'s human-friendly status string as a column:

.. code:: shell

   kugl -a "select n.name, to_size(sum(p.mem_req)) as requested, to_size(n.mem_alloc) as allocatable
            from nodes n join pods p on p.node_name = n.name
            where p.phase = 'Running' or p.status like 'Init:%'
            group by n.name order by sum(p.mem_req) desc"

Result:

.. code:: text

   name                                         requested    allocatable
   ip-10-12-18-252.us-east-2.compute.internal   42Gi         59Gi
   ip-10-12-188-56.us-east-2.compute.internal   36Gi         120Gi
   ...

With ``kubectl -o json`` and ``jq``, that's rather more work.  Parsing units is your problem,
status is derived from multiple fields, joins are awkward, and this doesn't yet cover
output formatting:

.. code:: shell

   { kubectl get nodes -o json; kubectl get pods -A -o json; } | jq -rn '
     def membytes:
       if test("Ki$") then (gsub("Ki$"; "") | tonumber * 1024)
       elif test("Mi$") then (gsub("Mi$"; "") | tonumber * 1048576)
       elif test("Gi$") then (gsub("Gi$"; "") | tonumber * 1073741824)
       elif test("K$")  then (gsub("K$";  "") | tonumber * 1000)
       elif test("M$")  then (gsub("M$";  "") | tonumber * 1000000)
       elif test("G$")  then (gsub("G$";  "") | tonumber * 1000000000)
       else tonumber end;
     (input | .items | map({
       name: .metadata.name,
       alloc: (.status.allocatable.memory | membytes)
     }) | INDEX(.name)) as $nodeMap |
     [input | .items[] |
       select(
         .status.phase == "Running" or
         (((.spec.initContainers // []) | length) > 0 and
          ((.status.initContainerStatuses // []) | map(select(.ready)) | length) <
          ((.spec.initContainers // []) | length))
       ) |
       select(.spec.nodeName) |
       {
         node: .spec.nodeName,
         mem: ([.spec.containers[].resources.requests.memory // "0"] | map(membytes) | add)
       }
     ] |
     group_by(.node) |
     map({node: .[0].node, requested: (map(.mem) | add), allocatable: $nodeMap[.[0].node].alloc}) |
     sort_by(-.requested)[] |
     [.node, .requested, .allocatable] | @tsv'

Installing
----------

Kugl requires Python 3.9 or later, and kubectl.

**This is an alpha release.** Please expect bugs and
`backward-incompatible changes <docs/breaking.rst>`__

If you don't mind Kugl's dependencies in your Python env:

.. code:: shell

   pip install kugl

If you do mind, there's a Docker image; ``mkdir ~/.kugl`` and use this
Bash alias.

.. code:: shell

   kugl() {
       docker run \
           -v ~/.kube:/root/.kube \
           -v ~/.kugl:/root/.kugl \
           jonross/kugl:0.8 python3 -m kugl.main "$@"
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
everything, if ``-A/--all-namespaces`` is used), it tries to ease Kubernetes API
Server load by **caching responses for two minutes**. This is why it
often prints "Data delayed up to ..." messages.

Depending on your cluster activity, the cache can be a help or a
hindrance. You can suppress the "delayed" messages with the ``-q`` /
``--quiet`` option, or always fetch fresh data using the ``-r`` /
``--refresh`` option. These behaviors, and the cache expiration time, can
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
