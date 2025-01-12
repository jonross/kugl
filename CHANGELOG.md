## 0.4.0

- Support multiple schemas & join across them
- Allow environment variables in `file` resource paths
- Resource cache paths and file formats have changed, old `~/.kugl/cache` files are not compatible
- `rm -r ~/.kugl/cache` is recommended before installing

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
