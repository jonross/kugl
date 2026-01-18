
VERSION = 0.6.0
IMAGE = jonross/kugl:$(VERSION)

# Quick test with current dependencies
test:
	uv run pytest

# Comprehensive regression test (Python 3.9 with low/high deps, Python 3.13 with high deps)
# Note: Python 3.13 with lowest resolution is not tested because old pydantic versions don't support it
test-all:
	@echo "=== Testing Python 3.9 with lowest dependencies ==="
	@uv run --python 3.9 --resolution lowest pytest
	@echo ""
	@echo "=== Testing Python 3.9 with highest dependencies ==="
	@uv run --python 3.9 --resolution highest pytest
	@echo ""
	@echo "=== Testing Python 3.13 with highest dependencies ==="
	@uv run --python 3.13 --resolution highest pytest
	@echo ""
	@echo "✓ All regression tests passed!"

# Individual test targets (for debugging)
test-py39-lo:
	uv run --python 3.9 --resolution lowest pytest

test-py39-hi:
	uv run --python 3.9 --resolution highest pytest

test-py13-lo:
	uv run --python 3.13 --resolution lowest pytest

test-py13-hi:
	uv run --python 3.13 --resolution highest pytest

# Build distribution for PyPI
dist:
	rm -rf dist/
	uv build

# Upload distribution to PyPI
pypi: dist
	uv run twine upload dist/*

# Build Docker image
docker: Makefile pyproject.toml
	docker build --no-cache -t $(IMAGE) .

# Upload Docker image
push: docker
	docker push $(IMAGE)

# Manually test Docker image
dshell: docker
	docker run -it -v ~/.kube:/root/.kube $(IMAGE) /bin/sh

# Manually test PyPI install
pyshell:
	docker run -it -v ~/.kube:/root/.kube --entrypoint /bin/sh python:3.9-alpine

# Clean build artifacts
clean:
	rm -rf build dist kugl.egg-info .pytest_cache coverage htmlcov

# Full clean including venv
pristine: clean
	rm -rf .venv
