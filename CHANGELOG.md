## 0.8.0

New tables in ``kubernetes`` schema:

- ``events``
- ``cronjobs`` and ``cronjob_labels`` 
- ``services`` and ``service_labels``
- ``deployments`` and ``deployment_labels``
- ``containers``

CLI changes (breaking):

- Added ``-c``/``--context`` option to specify a Kubernetes context
- Renamed ``-a`` option to ``-A`` for consistency with ``kubectl``
- Renamed ``-c``/``--cache`` to ``-s``/``--stale``
- Renamed ``-u``/``--update`` to ``-r``/``--refresh``
- Renamed ``-r``/``--reckless`` to ``-q``/``--quiet`` (and ``reckless:`` in settings to ``quiet:``)

CLI changes (non-breaking):

- Added ``-o``/``--output`` option to generate CSV or JSON in addition to tabular format

Extending tables:

- Breaking: Named scope syntax for multi-step ``row_source``: each entry takes ``as <name>`` and
  columns reference ancestor objects with ``in <name>`` suffix (e.g. ``metadata.uid in node``);
  the old ``^`` parent-hop syntax is removed
- New ``from:`` column key that auto-detects label vs JMESPath: values matching
  ``domain/key`` format (e.g. ``karpenter.sh/nodepool``) use label extraction, everything
  else uses JMESPath (``path:`` and ``label:`` to be removed in a future release)

Other:

- Shortcuts now support parameterization
- New masthead example of ``kugl`` vs ``kubectl | jq``


## 0.7.0

- Add `init` subcommand to generate `kubernetes.yaml` per recommended post-install configuration
- Rename `--schema` option to `schema` subcommand, support `--schema` for backward compatibility
- Convert documentation to reStructured Text, for publishing to readthedocs.org
- Support ARM chips via a multi-arch Docker build
- Add `cronjobs` and `cronjob_labels` tables to `kubernetes` schema
- Lint and format with `ruff`

## 0.6.0

- No external changes
- Convert build to `uv`

## 0.5.0

- Shortcut syntax in `init.yaml` has changed, but old syntax is still supported (a warning will be printed)
- Multiple configuration folders are supported via the `init_path` setting in `init.yaml`
- Add the `folder` resource type for collating data from multiple files

## 0.4.2

- Configuration errors now show the offending pathname
- Add `deletion_ts` to `pods` table
- Add `-H` / `--no-headers` option to suppress column headers
- Fix #130 - suspended jobs with no status will show status "Suspended"
- Fix #131 - remove resource type ambiguity by requiring `namespaced` field
- Fix #132 - `label` column extractor works for user-defined tables
- Fix #133 - resource definition errors no longer show a Pydantic stack trace

## 0.4.1

- Fix #127 - `null` protection + better error message for custom SQL functions

## 0.4.0

- Support multiple schemas & join across them
- Allow comments for user-defined columns
- Print schema & table definitions using `--schema` option
- Allow environment variables in `file` resource paths
- Fix the `exec` resource by adding a `cache_key` field; these resources would otherwise experience cache collisions
- Resource cache paths and file formats have changed, and cache now lives in `~/.kuglcache`
- `rm -r ~/.kuglcache` is recommended to clear obsolete files

## 0.3.3

- Add security warning for configuration files
- Improve (and unit test) debug output
- Improve test coverage

## 0.3.2

- Fix severe performance issue, `kubectl` was always called with `--all-namespaces` (#114)
- Make the troubleshooting guide friendlier + document debug options
- `--debug cache` prints name and age of cache filenames
- `--debug extract` logs extraction of requests & limits for containers, and capacity for nodes
- Fix formatting in the PyPI description
- Add this change log

## 0.3.1

First public release
