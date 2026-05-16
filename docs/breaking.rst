Breaking changes
----------------

Kugl is still in alpha.
Please expect bugs and backward-incompatible changes.

.. _080:

0.8.0
~~~~~

CLI changes:

- Added ``-c``/``--context`` option to specify a Kubernetes context
- Renamed ``-a`` option to ``-A`` for consistency with ``kubectl``
- Renamed ``-c``/``--cache`` to ``-s``/``--stale``
- Renamed ``-u``/``--update`` to ``-r``/``--refresh``
- Renamed ``-r``/``--reckless`` to ``-q``/``--quiet`` (and ``reckless:`` in settings to ``quiet:``)

.. _050:

0.5.0
~~~~~

- Shortcut syntax in ``init.yaml`` has changed, but old syntax is still
  supported (a warning will be printed)

.. _042:

0.4.2
~~~~~

- The ``namespaced`` field in a Kubernetes resource definition is now
  required.
