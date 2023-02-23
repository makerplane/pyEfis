################################
#    Makefile for pyavtools    #
################################
SHELL := /bin/bash


##################################### I N I T   T A R G E T S #####################################
venv:
	python3 -m venv venv
.PHONY: venv

init.marker: requirements.txt
	pip install -r requirements.txt
	touch init.marker
init: init.marker
.PHONY: init
