################################
#    Makefile for pyavtools    #
################################
SHELL := /bin/bash


##################################### I N I T   T A R G E T S #####################################
venv:
	python3 -m venv venv
	source venv/bin/activate
	pip install --upgrade pip
	pip install black
	pip install pytest
	echo "\nRun:\nsource venv/bin/activate"

.PHONY: venv

init.marker: pyproject.toml
	pip install -e .[install]
	touch init.marker
init: init.marker
.PHONY: init

#################################### W H E E L   T A R G E T S ####################################
init-build.marker: init
	pip install -e .[build]
	touch init-build.marker

init-build: init-build.marker
.PHONY: init-build

wheel: init-build
	python -m build --wheel


test:
	pip install pytest
	pip install pytest-qt
	pytest

.PHONY: test

