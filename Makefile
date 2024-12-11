
venv:
	python3 -m venv venv

reqs: venv
	(cd venv && . bin/activate && pip install -r ../requirements.txt)

test:
	(. venv/bin/activate && PYTHONPATH=lib pytest --cov --cov-report=html:coverage -vv -s --tb=native tests)

clean:
	rm -rf venv
