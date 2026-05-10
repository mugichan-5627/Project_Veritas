.PHONY: install db-demo test

install:
	pip install -e .

db-demo:
	python project_veritas/memory/build_vectordb.py --demo

test:
	python test_full_pipeline.py AMZN
