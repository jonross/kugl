Breaking changes
----------------

Kugl is still in alpha.
Please expect bugs and backward-incompatible changes.

.. _080:

0.8.0
~~~~~

Breaking changes are significant, gearing up for a 1.0 release.

The new `from:` syntax alternative to `path:` and `label:` is backwards compatible, but
the old syntax is deprecated and will be removed in a future release.

Python 3.10 is required, since 3.9 is EOL.

Extending tables:

- Named scope syntax for multi-step ``row_source``: each entry takes ``as <name>`` and
  columns reference ancestor objects with ``in <name>`` suffix (e.g. ``metadata.uid in node``);
  the old ``^`` parent-hop syntax is removed

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
