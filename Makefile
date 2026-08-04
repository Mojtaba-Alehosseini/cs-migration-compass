# CS Migration Compass
# One command reruns the whole data pipeline from scratch; one command builds the site.

PY ?= python
NPM ?= npm

.PHONY: help setup pipeline pipeline-fresh validate docs site-dev site-build site-preview clean all

help:
	@echo "CS Migration Compass"
	@echo ""
	@echo "  make setup           install Python + Node dependencies"
	@echo "  make pipeline        run every data source (cached downloads reused)"
	@echo "  make pipeline-fresh  clear data/raw and re-download everything"
	@echo "  make validate        run the data validation gate (CI runs this)"
	@echo "  make docs            regenerate docs/SOURCES.md from data/provenance.json"
	@echo "  make site-dev        start the Vite dev server"
	@echo "  make site-build      production build of the site"
	@echo "  make all             pipeline + validate + docs + site-build"
	@echo ""
	@echo "  Run one source:      $(PY) scripts/pipeline.py world_bank"
	@echo "  List sources:        $(PY) scripts/pipeline.py --list"

setup:
	$(PY) -m pip install -r scripts/requirements.txt
	cd site && $(NPM) install

pipeline:
	$(PY) scripts/pipeline.py

pipeline-fresh:
	rm -rf data/raw
	$(PY) scripts/pipeline.py

validate:
	$(PY) scripts/validate_data.py

docs:
	$(PY) scripts/generate_sources_doc.py

site-dev:
	cd site && $(NPM) run dev

site-build:
	cd site && $(NPM) run build

site-preview:
	cd site && $(NPM) run preview

clean:
	rm -rf site/dist site/node_modules

all: pipeline validate docs site-build
