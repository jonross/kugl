
test:
	PYTHONPATH=lib pytest --cov --cov-report=html:coverage -vv -s --tb=native tests
	
