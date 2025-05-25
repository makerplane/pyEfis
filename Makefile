################################
#    Makefile for pyefis       #
################################
SHELL := /bin/bash


##################################### I N I T   T A R G E T S #####################################
venv.marker:
	@if grep -qi 'Raspberry Pi' /proc/cpuinfo && grep -qi 'bookworm' /etc/os-release; then \
	    echo "Detected Raspberry Pi running Bookworm, will use --system-site-packages"; \
            echo "Checking if PyQt6 is installed system-wide..."; \
            if ! python3 -c 'import PyQt6' >/dev/null 2>&1; then \
                echo >&2 "Error: PyQt6 is not installed. Please run: sudo apt install python3-pyqt6"; \
                exit 1; \
	    else \
	        echo "...PyQt6 is installed system-wide"; \
            fi; \
	    echo "Any WARNINGS related to system-site-packages (eg. send2trash) can be ignored"; \
	    python3 -m venv venv --system-site-packages; \
	else \
	    echo "Standard environment, creating isolated venv, PyQt6 will be installed via pip when running 'make init'"; \
	    python3 -m venv venv; \
	fi
	venv/bin/pip install --upgrade pip
	venv/bin/pip install --upgrade send2trash
	venv/bin/pip install flake8
	venv/bin/pip install black
	venv/bin/pip install pytest
	venv/bin/pip install pytest-qt
	venv/bin/pip install pytest-env
	venv/bin/pip install pytest-cov
	touch venv.marker
	@echo -e "\nRun:\nsource venv/bin/activate"
	@echo -e "\nRun (if any display errors are encountered):\nsource venv/bin/activate;export DISPLAY=:0"
venv: venv.marker
.PHONY: venv

init.marker: pyproject.toml
	@if grep -qi 'Raspberry Pi' /proc/cpuinfo && grep -qi 'bookworm' /etc/os-release; then \
	    echo "Detected Raspberry Pi running Bookworm, will use the system installed PyQt6 version"; \
	    echo "Checking if PyQt6 is installed system-wide..."; \
	    if ! python3 -c 'import PyQt6' >/dev/null 2>&1; then \
		echo >&2 "Error: PyQt6 is not installed. Please run: sudo apt install python3-pyqt6"; \
		exit 1; \
	    else \
		echo "...PyQt6 is installed system-wide"; \
	    fi; \
	    echo "Checking if 'xwininfo' (from x11-utils) is installed..."; \
	    if ! command -v xwininfo >/dev/null 2>&1; then \
		echo >&2 "Error: xwininfo not found. Please run: sudo apt install x11-utils"; \
		exit 1; \
	    else \
		echo "...xwininfo is installed"; \
	    fi; \
	    venv/bin/pip install --extra-index-url https://www.piwheels.org/simple -e .[install]; \
	else \
	    echo "Standard environment found, will install PyQt6 via PyPI"; \
	    venv/bin/pip install --extra-index-url https://www.piwheels.org/simple -e .[qt]; \
	fi
	touch init.marker
init: venv.marker init.marker
.PHONY: init

#################################### W H E E L   T A R G E T S ####################################
init-build.marker: init
	venv/bin/pip install --extra-index-url https://www.piwheels.org/simple -e .[build]
	touch init-build.marker

init-build: init-build.marker
.PHONY: init-build

wheel: init-build
	venv/bin/python -m build --wheel


test: init
	source venv/bin/activate ; flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics
	source venv/bin/activate ; flake8 src tests --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	venv/bin/pytest

.PHONY: test

clean:
	rm -rf venv
	rm -f extras/extras/test_results/*.html
	rm -f extras/extras/test_results/*.png
	rm -rf extras/extras/test_results/htmlcov/
	rm -f init-build.marker
	rm -f init.marker
	rm -f venv.marker
.PHONY: clean
