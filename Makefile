clean:
	rm -rf dist

sdist: clean
	python setup.py sdist

pylint: 
	pylint masnet/*.py

upload:
	twine upload dist/*
