## 0.4.1

- Fix #127 - `null` protection + better error message for custom SQL functions

## 0.4.0

- Support multiple schemas & join across them
- Allow comments for user-defined columns
- Print schema & table definitions using `--schema` option
- Allow environment variables in `file` resource paths
- Fix the `exec` resource by adding a `cache_key` field; these resources would otherwise experience cache collisions
- Resource cache paths and file formats have changed, and cache now lives in `~/.kuglcache`
- `rm -r ~/.kugl/cache` is recommended to clear obsolete files

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
