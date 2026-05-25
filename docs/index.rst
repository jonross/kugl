.. include:: ../README.rst
   :end-before: END_INCLUDE

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

Learn more
----------

- :doc:`Command-line syntax <syntax>`
- :doc:`Recommended configuration <recommended>`
- :doc:`Settings <settings>`
- :doc:`Shortcuts <shortcuts>`
- :doc:`Built-in tables & functions <builtins>`
- :doc:`Adding columns and tables <extending>`
- Beyond Kubernetes and kubectl

  - :doc:`Other resource types <resources>`
  - :doc:`Additional schemas <multi>`

- `Release notes <https://github.com/jonross/kugl/blob/main/CHANGELOG.md>`__
- :doc:`Breaking changes <breaking>`
- :doc:`Troubleshooting and feedback <trouble>`
- `License <https://github.com/jonross/kugl/blob/main/LICENSE>`__


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
 
.. toctree::
   :hidden:
   :maxdepth: 1
   :caption: Contents:

   Command-line syntax <syntax>
   Recommended configuration <recommended>
   Settings <settings>
   Shortcuts <shortcuts>
   Built-in tables & functions <builtins>
   Adding columns & tables <extending>
   Other resource types <resources>
   Multi-schema queries <multi>
   Breaking changes <breaking>
   Troubleshooting & feedback <trouble>
