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

Kugl requires Python 3.10 or later, and kubectl.

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

.. END_INCLUDE

Learn more
~~~~~~~~~~

For more (and important) information please see https://kugl.readthedocs.io/
