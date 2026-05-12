Settings
--------

.. warning::
   Configuration files should be protected to the same degree as your shell
   scripts and anything on your ``PYTHONPATH.`` Kugl will refuse to read a
   configuration file that is world-writable.

The ``settings`` section in ``~/.kugl/init.yaml`` can be used to specify
cache behaviors once, rather than on every usage from the command line.
Example:

.. code:: yaml

   settings:
     cache_timeout: 5m
     reckless: true

The ``init_path`` section of ``settings`` can be used to specify
multiple configuration folders. This is useful for team configuration
files. `Shortcuts <./shortcuts.rst>`__ in ``init.yaml`` and schema
configurations in those folders will be applied before entries in
``~/.kugl``.

NOTE: other ``init.yaml`` fils can contain only shortcuts; the
``settings`` section of ``init.yaml`` is valid only in
``~/.kugl/init.yaml``.
