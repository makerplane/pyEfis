################################
#    Makefile for pyavtools    #
################################
SHELL := /bin/bash


##################################### I N I T   T A R G E T S #####################################
venv.marker:
	python3 -m venv venv
	source venv/bin/activate ; pip install --upgrade pip
	source venv/bin/activate ; pip install black
	source venv/bin/activate ; pip install pytest
	source venv/bin/activate ; pip install pytest-qt
	source venv/bin/activate ; pip install pytest-env
	source venv/bin/activate ; pip install pytest-cov
	touch venv.marker
	echo -e "\nRun:\nsource venv/bin/activate"
venv: venv.marker
.PHONY: venv

init.marker: pyproject.toml
	source venv/bin/activate ; pip install -e .[install]
	touch init.marker
init: venv.marker init.marker
.PHONY: init

#################################### W H E E L   T A R G E T S ####################################
init-build.marker: init
	source venv/bin/activate ; pip install -e .[build]
	touch init-build.marker

init-build: init-build.marker
.PHONY: init-build

wheel: init-build
	source venv/bin/activate ; python -m build --wheel


test: init
	source venv/bin/activate ; pytest

.PHONY: test

clean:
	rm -rfI venv || true
	rm -fI extras/extras/test_results/*.html || true
	rm -fI extras/extras/test_results/*.png || true
	rm -rfI extras/extras/test_results/htmlcov/ || true
	rm -f init-build.marker || true
	rm -f init.marker || true
	rm -f venv.marker || true
.PHONY: clean
