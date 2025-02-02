
VERSION = 0.4.2
IMAGE = jonross/kugl:$(VERSION)

venv:
	python3 -m venv venv

# Build virtualenv for development and install dependencies
deps: venv
	(cd venv && . bin/activate && pip install -r ../requirements.txt)

# Test with current requirements
test:
	@bin/tester

# Test with low end of requirements
lotest:
	@bin/tester --lo

# Test with high end of requirements
hitest:
	@bin/tester --hi

# Test with dev requirements
pintest:
	@bin/tester --pin

# Build distribution for PyPI
dist: setup.py MANIFEST.in
	python3 setup.py sdist bdist_wheel

# Upload distribution to PyPI
pypi:
	twine upload dist/*

# Build Docker image
docker: Makefile setup.py
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

clean:
	rm -rf build dist kugl.egg-info

pristine: clean
	rm -rf venv
