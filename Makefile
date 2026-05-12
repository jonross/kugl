
VERSION = 0.7.0
IMAGE = jonross/kugl:$(VERSION)

.PHONY: lint test test-all test-py39-lo test-py39-hi test-py13-lo test-py13-hi dist pypi docker push dshell pyshell docs clean pristine

# Lint and format check
lint:
	uv run ruff check .
	uv run ruff format --check .

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

# Build Docker image (local platform only, for testing)
docker: Makefile pyproject.toml
	docker build --no-cache -t $(IMAGE) .

# Build and push multi-platform Docker image (linux/amd64 and linux/arm64)
push: Makefile pyproject.toml
	@echo "Setting up buildx builder for multi-platform..."
	@docker buildx create --name multiplatform --use 2>/dev/null || docker buildx use multiplatform
	@echo "Building and pushing multi-platform image: $(IMAGE)"
	docker buildx build --platform linux/amd64,linux/arm64 --no-cache -t $(IMAGE) --push .

# Manually test Docker image
smoke:
	docker run -it -v ~/.kube:/root/.kube $(IMAGE) "select * from nodes"

# Manually test PyPI install
pyshell:
	docker run -it -v ~/.kube:/root/.kube --entrypoint /bin/sh python:3.9-alpine

# Build documentation locally
docs:
	uv run --group docs sphinx-build -b html docs build/docs

# Clean build artifacts
clean:
	rm -rf build dist kugl.egg-info .pytest_cache coverage htmlcov

# Full clean including venv
pristine: clean
	rm -rf .venv
