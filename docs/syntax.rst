Usage
-----

.. code:: shell

   kugl [options] [sql | shortcut]

Kubernetes options
~~~~~~~~~~~~~~~~~~

Most invocations of Kugl will need ``-a`` or ``-n namespace``, just like
``kubectl``. If your cluster is small, you could also (for instance)
``alias kg="kugl -a"`` and use ``where namespace = ...`` instead.

- ``-a, --all, --all-namespaces`` - Look in all namespaces for
  Kubernetes resources. May not be combined with ``-n``.
- ``-n, --namespace NS`` - Look in namespace ``NS`` for Kubernetes
  resources. May not be combined with ``-a``.

Cache control
~~~~~~~~~~~~~

- ``-c, --cache`` - Always use cached data, if available, regardless of
  its age
- ``-r, --reckless`` - Don't print stale data warnings
- ``-t, --timeout AGE`` - Change the expiration time for cached data,
  e.g. ``5m``, ``1h``; the default is ``2m`` (two minutes)
- ``-u, --update`` - Always updated from ``kubectl``, regardless of data
  age

Other
~~~~~~~~~~~~~

- ``-H, --no-header`` -- Suppress column headers
