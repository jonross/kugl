Usage
-----

.. code:: shell

   kugl [options] [sql | shortcut]

Kubernetes options
~~~~~~~~~~~~~~~~~~

Most invocations of Kugl will need ``-A`` or ``-n namespace``, just like
``kubectl``. If your cluster is small, you could also (for instance)
``alias kg="kugl -A"`` and use ``where namespace = ...`` instead.

- ``-A, --all-namespaces`` - Look in all namespaces for
  Kubernetes resources. May not be combined with ``-n``.
- ``-n, --namespace NS`` - Look in namespace ``NS`` for Kubernetes
  resources. May not be combined with ``-a``.
- ``-c, --context CONTEXT`` - Use context ``CONTEXT`` for Kubernetes
  resources.  If not specified, the current context is used.

Cache control
~~~~~~~~~~~~~

- ``-s, --stale`` - Always use cached data, if available, regardless of
  its age
- ``-r, --refresh`` - Always fetch fresh data from ``kubectl``,
  regardless of data age
- ``-q, --quiet`` - Don't print stale data warnings
- ``-t, --timeout AGE`` - Change the expiration time for cached data,
  e.g. ``5m``, ``1h``; the default is ``2m`` (two minutes)

Other
~~~~~~~~~~~~~

- ``-H, --no-header`` -- Suppress column headers
- ``-o, --output FORMAT`` -- Output format: ``table`` (default), ``csv``, or ``json``.
  ``csv`` respects ``-H``; ``json`` always includes column names as keys.
